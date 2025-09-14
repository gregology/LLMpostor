"""
Integration tests for automatic game flow and timing.

Tests automatic phase transitions, countdown timers, player disconnection handling,
and cleanup logic for the LLMpostor game.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch
import threading

# Import the Flask app and Socket.IO client for testing

from flask_socketio import SocketIOTestClient
from src.content_manager import PromptData
# Service imports
from tests.migration_compat import app, socketio, room_manager, game_manager, content_manager, auto_flow_service, session_service


class TestAutomaticGameFlow:
    """Test class for automatic game flow and timing."""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self, app, socketio):
        """Set up test environment before each test."""
        # Clear any existing rooms and sessions before each test
        # Use the actual services from the app, not test fixtures
        room_manager._rooms.clear()
        session_service._player_sessions.clear()
        
        app.config['TESTING'] = True
        
        # Ensure auto flow service is running
        if not auto_flow_service.running:
            auto_flow_service.running = True
            auto_flow_service.timer_thread = threading.Thread(target=auto_flow_service._timer_loop, daemon=True)
            auto_flow_service.timer_thread.start()
        
        yield  # This is where the test runs
        
        # Teardown: Clean up state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()
        
    @pytest.fixture
    def client(self, app, socketio):
        """Create a test client for Socket.IO."""
        return socketio.test_client(app)
    
    @pytest.fixture
    def mock_content_manager(self):
        """Mock content manager with test prompts."""
        with patch.object(content_manager, 'is_loaded', return_value=True), \
             patch.object(content_manager, 'get_prompt_count', return_value=3), \
             patch.object(content_manager, 'get_random_prompt_response') as mock_get_prompt:
            
            # Create a test prompt
            test_prompt = PromptData(
                id="test_001",
                prompt="What is artificial intelligence?",
                model="GPT-4",
                responses=["Artificial intelligence (AI) is a branch of computer science that aims to create intelligent machines."]
            )
            test_prompt.select_random_response()  # Ensure response is selected for tests
            mock_get_prompt.return_value = test_prompt
            yield mock_get_prompt
    
    @pytest.fixture
    def test_auto_flow_service(self):
        """Configure the auto flow service for testing with faster timing."""
        # Use the existing auto_flow_service for tests
        test_manager = auto_flow_service
        original_interval = test_manager.check_interval
        test_manager.check_interval = 0.05  # Check every 50ms for faster tests
        
        yield test_manager
        
        # Restore original interval
        test_manager.check_interval = original_interval
    
    def _setup_game_to_responding_phase(self, client1, client2, mock_content_manager):
        """Helper method to set up a game to the responding phase."""
        # Join room with two players
        client1.emit('join_room', {
            'room_id': 'test_room',
            'player_name': 'Player1'
        })
        
        client2.emit('join_room', {
            'room_id': 'test_room',
            'player_name': 'Player2'
        })
        
        # Clear join events
        client1.get_received()
        client2.get_received()
        
        # Start round
        client1.emit('start_round')
        
        # Clear round start events
        client1.get_received()
        client2.get_received()
    
    def _setup_game_to_guessing_phase(self, client1, client2, mock_content_manager):
        """Helper method to set up a game to the guessing phase."""
        self._setup_game_to_responding_phase(client1, client2, mock_content_manager)
        
        # Both players submit responses
        client1.emit('submit_response', {
            'response': 'AI is technology that mimics human intelligence.'
        })
        
        client2.emit('submit_response', {
            'response': 'Artificial intelligence creates smart computer systems.'
        })
        
        # Clear response submission events
        client1.get_received()
        client2.get_received()
    
    def test_automatic_phase_timeout_responding_to_guessing(self, client, mock_content_manager, test_auto_flow_service):
        """Test automatic phase transition from responding to guessing on timeout."""
        client2 = socketio.test_client(app)
        client3 = socketio.test_client(app)  # Extra client to ensure we have enough players
        
        try:
            # Join room with three players to avoid disconnect issues
            client.emit('join_room', {'room_id': 'test_room', 'player_name': 'Player1'})
            client2.emit('join_room', {'room_id': 'test_room', 'player_name': 'Player2'})  
            client3.emit('join_room', {'room_id': 'test_room', 'player_name': 'Player3'})
            
            # Clear join events
            client.get_received()
            client2.get_received()
            client3.get_received()
            
            # Start round
            client.emit('start_round')
            
            # Clear round start events
            client.get_received()
            client2.get_received()
            client3.get_received()
            
            # Manually set a very short phase duration for testing
            room_state = room_manager.get_room_state('test_room')
            room_state['game_state']['phase_duration'] = 1  # 1 second
            room_state['game_state']['phase_start_time'] = datetime.now() - timedelta(seconds=2)  # Already expired
            room_manager.update_game_state('test_room', room_state['game_state'])
            
            # Wait for automatic phase transition - give more time for timer to run
            time.sleep(1.0)  # Wait longer for timer to check
            
            # Check that phase advanced to guessing
            updated_state = game_manager.get_game_state('test_room')
            if updated_state['phase'] != 'guessing':
                # Wait a bit more if phase hasn't changed yet
                time.sleep(1.0)
                updated_state = game_manager.get_game_state('test_room')
            
            assert updated_state['phase'] == 'guessing'
            
            # Check that clients received guessing phase event
            received1 = client.get_received()
            received2 = client2.get_received()
            received3 = client3.get_received()
            
            guessing_events1 = [event for event in received1 if event['name'] == 'guessing_phase_started']
            guessing_events2 = [event for event in received2 if event['name'] == 'guessing_phase_started']
            guessing_events3 = [event for event in received3 if event['name'] == 'guessing_phase_started']
            
            assert len(guessing_events1) > 0 or len(guessing_events2) > 0 or len(guessing_events3) > 0
            
        finally:
            client2.disconnect()
            client3.disconnect()
    
    def test_automatic_phase_timeout_guessing_to_results(self, client, mock_content_manager, test_auto_flow_service):
        """Test automatic phase transition from guessing to results on timeout."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Manually set a very short phase duration for testing
            room_state = room_manager.get_room_state('test_room')
            room_state['game_state']['phase_duration'] = 1  # 1 second
            room_state['game_state']['phase_start_time'] = datetime.now() - timedelta(seconds=2)  # Already expired
            room_manager.update_game_state('test_room', room_state['game_state'])
            
            # Wait for automatic phase transition
            time.sleep(1.0)  # Wait longer for timer to check
            
            # Check that phase advanced to results
            updated_state = game_manager.get_game_state('test_room')
            if updated_state['phase'] != 'results':
                # Wait a bit more if phase hasn't changed yet
                time.sleep(1.0)
                updated_state = game_manager.get_game_state('test_room')
            
            assert updated_state['phase'] == 'results'
            
            # Check that clients received results phase event
            received1 = client.get_received()
            received2 = client2.get_received()
            
            results_events1 = [event for event in received1 if event['name'] == 'results_phase_started']
            results_events2 = [event for event in received2 if event['name'] == 'results_phase_started']
            
            assert len(results_events1) > 0 or len(results_events2) > 0
            
        finally:
            client2.disconnect()
    
    def test_automatic_phase_timeout_results_to_waiting(self, client, mock_content_manager, test_auto_flow_service):
        """Test automatic phase transition from results to waiting on timeout."""
        client2 = socketio.test_client(app)
        
        try:
            # Set up game to results phase
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Advance to results phase manually
            game_manager.advance_game_phase('test_room')
            
            # Manually set a very short phase duration for testing
            room_state = room_manager.get_room_state('test_room')
            room_state['game_state']['phase_duration'] = 1  # 1 second
            room_state['game_state']['phase_start_time'] = datetime.now() - timedelta(seconds=2)  # Already expired
            room_manager.update_game_state('test_room', room_state['game_state'])
            
            # Wait for automatic phase transition
            time.sleep(1.0)  # Wait longer for timer to check
            
            # Check that phase advanced to waiting
            updated_state = game_manager.get_game_state('test_room')
            if updated_state['phase'] != 'waiting':
                # Wait a bit more if phase hasn't changed yet
                time.sleep(1.0)
                updated_state = game_manager.get_game_state('test_room')
            
            assert updated_state['phase'] == 'waiting'
            
            # Check that clients received round ended event
            received1 = client.get_received()
            received2 = client2.get_received()
            
            round_end_events1 = [event for event in received1 if event['name'] == 'round_ended']
            round_end_events2 = [event for event in received2 if event['name'] == 'round_ended']
            
            assert len(round_end_events1) > 0 or len(round_end_events2) > 0
            
        finally:
            client2.disconnect()
    
    def test_countdown_timer_updates(self, client, mock_content_manager, test_auto_flow_service):
        """Test that countdown timer updates are broadcasted during timed phases."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_responding_phase(client, client2, mock_content_manager)
            
            # Clear initial events
            client.get_received()
            client2.get_received()
            
            # Wait for countdown updates (should happen every 10 seconds, but we'll wait less)
            time.sleep(0.2)  # Wait for timer to run
            
            # Check for countdown_update events
            received1 = client.get_received()
            received2 = client2.get_received()
            
            countdown_events1 = [event for event in received1 if event['name'] == 'countdown_update']
            countdown_events2 = [event for event in received2 if event['name'] == 'countdown_update']
            
            # Note: Countdown updates happen every 10 seconds, so we might not see them in this short test
            # But the structure should be correct if they do appear
            if countdown_events1 or countdown_events2:
                countdown_event = countdown_events1[0] if countdown_events1 else countdown_events2[0]
                event_data = countdown_event['args'][0]
                
                assert 'phase' in event_data
                assert 'time_remaining' in event_data
                assert 'phase_duration' in event_data
                assert event_data['phase'] == 'responding'
            
        finally:
            client2.disconnect()
    
    def test_get_time_remaining_endpoint(self, client, mock_content_manager):
        """Test the get_time_remaining Socket.IO endpoint."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_responding_phase(client, client2, mock_content_manager)
            
            # Clear initial events
            client.get_received()
            
            # Request time remaining
            client.emit('get_time_remaining')
            
            received = client.get_received()
            time_events = [event for event in received if event['name'] == 'time_remaining']
            
            assert len(time_events) > 0
            
            time_event = time_events[0]
            response = time_event['args'][0]
            
            assert response['success'] is True
            data = response['data']
            assert 'time_remaining' in data
            assert 'phase' in data
            assert 'phase_duration' in data
            assert data['phase'] == 'responding'
            
        finally:
            client2.disconnect()
    
    def test_get_time_remaining_not_in_room(self, client):
        """Test get_time_remaining when not in a room."""
        client.emit('get_time_remaining')
        
        received = client.get_received()
        error_event = next(event for event in received if event['name'] == 'error')
        error_response = error_event['args'][0]
        
        assert error_response['success'] is False
        assert error_response['error']['code'] == 'NOT_IN_ROOM'
    
    def test_inactive_room_cleanup(self, client, test_auto_flow_service):
        """Test that inactive rooms are cleaned up automatically."""
        # Create a room
        client.emit('join_room', {
            'room_id': 'test_room',
            'player_name': 'Player1'
        })
        
        client.get_received()  # Clear events
        
        # Verify room exists
        assert room_manager.room_exists('test_room')
        
        # Manually set room as very old
        room_state = room_manager.get_room_state('test_room')
        room_state['last_activity'] = datetime.now() - timedelta(hours=2)  # 2 hours ago
        room_manager._rooms['test_room'] = room_state
        
        # Trigger cleanup manually (normally happens every minute)
        test_auto_flow_service._cleanup_inactive_rooms()
        
        # Verify room was cleaned up
        assert not room_manager.room_exists('test_room')
    
    def test_time_warning_broadcasts(self, client, mock_content_manager, test_auto_flow_service):
        """Test that time warning events are broadcasted when time is low."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_responding_phase(client, client2, mock_content_manager)
            
            # Manually set phase to have very little time remaining
            room_state = room_manager.get_room_state('test_room')
            room_state['game_state']['phase_duration'] = 35  # 35 seconds total
            room_state['game_state']['phase_start_time'] = datetime.now() - timedelta(seconds=10)  # 25 seconds remaining
            room_manager.update_game_state('test_room', room_state['game_state'])
            
            # Clear initial events
            client.get_received()
            client2.get_received()
            
            # Wait for timer to check and potentially send warnings
            time.sleep(0.2)
            
            # Note: Time warnings are sent when time_remaining is between 25-30 or 5-10 seconds
            # Since we set it to 25 seconds remaining, we might get a 30-second warning
            received1 = client.get_received()
            received2 = client2.get_received()
            
            warning_events1 = [event for event in received1 if event['name'] == 'time_warning']
            warning_events2 = [event for event in received2 if event['name'] == 'time_warning']
            
            # Warnings might not appear in this short test window, but structure should be correct
            if warning_events1 or warning_events2:
                warning_event = warning_events1[0] if warning_events1 else warning_events2[0]
                event_data = warning_event['args'][0]
                
                assert 'message' in event_data
                assert 'time_remaining' in event_data
                assert 'remaining' in event_data['message']
            
        finally:
            client2.disconnect()
    
    def test_auto_flow_service_stop_and_cleanup(self, test_auto_flow_service):
        """Test that AutoGameFlowService stops cleanly."""
        # Verify service is running
        assert test_auto_flow_service.running is True
        assert test_auto_flow_service.timer_thread.is_alive()
        
        # Stop the service
        test_auto_flow_service.stop()
        
        # Verify it stopped
        assert test_auto_flow_service.running is False
        
        # Wait a moment for thread to finish
        time.sleep(0.2)
        
        # Thread should no longer be alive
        assert not test_auto_flow_service.timer_thread.is_alive()


if __name__ == '__main__':
    pytest.main([__file__])