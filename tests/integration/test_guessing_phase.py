"""
Integration tests for guessing phase and response display.

Tests the Socket.IO event handlers for displaying anonymized responses,
guess submission, validation, and time limit enforcement during guessing phase.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Import the Flask app and Socket.IO client for testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app import app, socketio, room_manager, game_manager, content_manager
from src.content_manager import PromptData


class TestGuessingPhase:
    """Test class for guessing phase and response display."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for Socket.IO."""
        app.config['TESTING'] = True
        # Clear any existing rooms and sessions before each test
        room_manager._rooms.clear()
        from app import player_sessions
        player_sessions.clear()
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
                response="Artificial intelligence (AI) is a branch of computer science that aims to create intelligent machines."
            )
            mock_get_prompt.return_value = test_prompt
            yield mock_get_prompt
    
    def _setup_game_to_guessing_phase(self, client1, client2, mock_content_manager):
        """Helper method to set up a game to the guessing phase."""
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
        
        # Both players submit responses
        client1.emit('submit_response', {
            'response': 'AI is technology that mimics human intelligence.'
        })
        
        client2.emit('submit_response', {
            'response': 'Artificial intelligence creates smart computer systems.'
        })
        
        # Don't clear response submission events - these should trigger guessing phase
        # The guessing phase events should be available after this method returns
    
    def test_guessing_phase_starts_after_all_responses(self, client, mock_content_manager):
        """Test that guessing phase starts automatically when all players submit responses."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Check that both clients received guessing_phase_started event
            received1 = client.get_received()
            received2 = client2.get_received()
            

            
            # Look for guessing_phase_started event
            guessing_events1 = [event for event in received1 if event['name'] == 'guessing_phase_started']
            guessing_events2 = [event for event in received2 if event['name'] == 'guessing_phase_started']
            
            # Also check for room_state_updated events that might indicate phase change
            state_events1 = [event for event in received1 if event['name'] == 'room_state_updated']
            state_events2 = [event for event in received2 if event['name'] == 'room_state_updated']
            
            # Check if any room state update shows guessing phase
            guessing_state_found = False
            for event in state_events1 + state_events2:
                if event['args'][0].get('phase') == 'guessing':
                    guessing_state_found = True
                    break
            
            assert len(guessing_events1) > 0 or len(guessing_events2) > 0 or guessing_state_found
            
            if guessing_events1 or guessing_events2:
                # Check the guessing phase event data
                guessing_event = guessing_events1[0] if guessing_events1 else guessing_events2[0]
                event_data = guessing_event['args'][0]
                
                assert event_data['phase'] == 'guessing'
                assert 'responses' in event_data
                assert len(event_data['responses']) == 3  # 2 player responses + 1 LLM response
                assert 'round_number' in event_data
                assert 'phase_duration' in event_data
                
                # Verify responses are anonymized (no author info)
                for response in event_data['responses']:
                    assert 'index' in response
                    assert 'text' in response
                    assert 'author_name' not in response
                    assert 'is_llm' not in response
        
        finally:
            client2.disconnect()
    
    def test_submit_guess_success(self, client, mock_content_manager):
        """Test successful guess submission."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Clear any remaining events
            client.get_received()
            client2.get_received()
            
            # Submit a guess
            client.emit('submit_guess', {
                'guess_index': 1
            })
            
            received = client.get_received()
            
            # Should receive guess_submitted confirmation
            guess_events = [event for event in received if event['name'] == 'guess_submitted']
            assert len(guess_events) > 0
            
            guess_event = guess_events[0]
            assert guess_event['args'][0]['success'] is True
            assert guess_event['args'][0]['data']['guess_index'] == 1
        
        finally:
            client2.disconnect()
    
    def test_submit_guess_not_in_room(self, client):
        """Test submitting guess when not in a room."""
        client.emit('submit_guess', {
            'guess_index': 0
        })
        
        received = client.get_received()
        error_event = next(event for event in received if event['name'] == 'error')
        
        assert error_event['args'][0]['error']['code'] == 'NOT_IN_ROOM'
        assert 'not currently in a room' in error_event['args'][0]['error']['message']
    
    def test_submit_guess_wrong_phase(self, client, mock_content_manager):
        """Test submitting guess during wrong game phase."""
        # Join room but don't advance to guessing phase
        client.emit('join_room', {
            'room_id': 'test_room',
            'player_name': 'Player1'
        })
        
        client.get_received()  # Clear events
        
        client.emit('submit_guess', {
            'guess_index': 0
        })
        
        received = client.get_received()
        error_event = next(event for event in received if event['name'] == 'error')
        
        assert error_event['args'][0]['error']['code'] == 'WRONG_PHASE'
        assert 'guessing phase' in error_event['args'][0]['error']['message']
    
    def test_submit_guess_invalid_data_format(self, client, mock_content_manager):
        """Test submitting guess with invalid data format."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Clear any remaining events
            client.get_received()
            client2.get_received()
            
            # Submit invalid data format
            client.emit('submit_guess', 'invalid_string_data')
            
            received = client.get_received()
            error_event = next(event for event in received if event['name'] == 'error')
            
            assert error_event['args'][0]['error']['code'] == 'INVALID_DATA'
        
        finally:
            client2.disconnect()
    
    def test_submit_guess_missing_index(self, client, mock_content_manager):
        """Test submitting guess without guess_index."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Clear any remaining events
            client.get_received()
            client2.get_received()
            
            # Submit guess without index
            client.emit('submit_guess', {})
            
            received = client.get_received()
            error_event = next(event for event in received if event['name'] == 'error')
            
            assert error_event['args'][0]['error']['code'] == 'MISSING_GUESS'
        
        finally:
            client2.disconnect()
    
    def test_submit_guess_invalid_index_format(self, client, mock_content_manager):
        """Test submitting guess with non-integer index."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Clear any remaining events
            client.get_received()
            client2.get_received()
            
            # Submit guess with string index
            client.emit('submit_guess', {
                'guess_index': 'invalid'
            })
            
            received = client.get_received()
            error_event = next(event for event in received if event['name'] == 'error')
            
            assert error_event['args'][0]['error']['code'] == 'INVALID_GUESS_FORMAT'
        
        finally:
            client2.disconnect()
    
    def test_submit_guess_invalid_index_range(self, client, mock_content_manager):
        """Test submitting guess with out-of-range index."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Clear any remaining events
            client.get_received()
            client2.get_received()
            
            # Submit guess with invalid index (too high)
            client.emit('submit_guess', {
                'guess_index': 99
            })
            
            received = client.get_received()
            error_event = next(event for event in received if event['name'] == 'error')
            error_response = error_event['args'][0]
            
            assert error_response['success'] is False
            assert error_response['error']['code'] == 'INVALID_GUESS_INDEX'
        
        finally:
            client2.disconnect()
    
    def test_submit_guess_negative_index(self, client, mock_content_manager):
        """Test submitting guess with negative index."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Clear any remaining events
            client.get_received()
            client2.get_received()
            
            # Submit guess with negative index
            client.emit('submit_guess', {
                'guess_index': -1
            })
            
            received = client.get_received()
            error_event = next(event for event in received if event['name'] == 'error')
            error_response = error_event['args'][0]
            
            assert error_response['success'] is False
            assert error_response['error']['code'] == 'INVALID_GUESS_INDEX'
        
        finally:
            client2.disconnect()
    
    def test_submit_guess_duplicate(self, client, mock_content_manager):
        """Test submitting guess twice (should fail second time)."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Clear any remaining events
            client.get_received()
            client2.get_received()
            
            # Submit first guess
            client.emit('submit_guess', {
                'guess_index': 1
            })
            
            client.get_received()  # Clear events
            
            # Try to submit second guess
            client.emit('submit_guess', {
                'guess_index': 2
            })
            
            received = client.get_received()
            

            
            # Look for error event
            error_events = [event for event in received if event['name'] == 'error']
            
            if error_events:
                error_event = error_events[0]
                assert error_event['args'][0]['error']['code'] == 'SUBMIT_GUESS_FAILED'
            else:
                # If no error event, the duplicate submission might have been silently ignored
                # Check if there are any success events (there shouldn't be)
                success_events = [event for event in received if event['name'] == 'guess_submitted' and event['args'][0].get('success')]
                assert len(success_events) == 0, "Duplicate guess should not succeed"
        
        finally:
            client2.disconnect()
    
    def test_guessing_phase_auto_advance_to_results(self, client, mock_content_manager):
        """Test that guessing phase auto-advances to results when all players guess."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Clear any remaining events
            client.get_received()
            client2.get_received()
            
            # Both players submit guesses
            client.emit('submit_guess', {
                'guess_index': 1
            })
            
            client2.emit('submit_guess', {
                'guess_index': 2
            })
            
            # Check that results phase started
            received1 = client.get_received()
            received2 = client2.get_received()
            
            # Look for results_phase_started event
            results_events1 = [event for event in received1 if event['name'] == 'results_phase_started']
            results_events2 = [event for event in received2 if event['name'] == 'results_phase_started']
            
            assert len(results_events1) > 0 or len(results_events2) > 0
            
            # Check the results phase event data
            results_event = results_events1[0] if results_events1 else results_events2[0]
            event_data = results_event['args'][0]
            
            assert event_data['phase'] == 'results'
            assert 'round_results' in event_data
            assert 'leaderboard' in event_data
            
            # Check round results structure
            round_results = event_data['round_results']
            assert 'responses' in round_results
            assert 'player_results' in round_results
            assert 'llm_response_index' in round_results
            
            # Verify responses now show authorship
            for response in round_results['responses']:
                assert 'is_llm' in response
                if not response['is_llm']:
                    assert 'author_name' in response
        
        finally:
            client2.disconnect()
    
    def test_guess_count_broadcast(self, client, mock_content_manager):
        """Test that guess count is broadcasted when players submit guesses."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Clear any remaining events
            client.get_received()
            client2.get_received()
            
            # First player submits guess
            client.emit('submit_guess', {
                'guess_index': 1
            })
            
            # Check that both clients receive guess count update
            received1 = client.get_received()
            received2 = client2.get_received()
            
            # Look for guess_submitted broadcast event (not the confirmation)
            guess_broadcast_events1 = [event for event in received1 
                                     if event['name'] == 'guess_submitted' and 'guess_count' in event['args'][0]]
            guess_broadcast_events2 = [event for event in received2 
                                     if event['name'] == 'guess_submitted' and 'guess_count' in event['args'][0]]
            
            # At least one client should receive the broadcast
            assert len(guess_broadcast_events1) > 0 or len(guess_broadcast_events2) > 0
            
            # Check the broadcast data
            broadcast_event = guess_broadcast_events1[0] if guess_broadcast_events1 else guess_broadcast_events2[0]
            event_data = broadcast_event['args'][0]
            
            assert event_data['guess_count'] == 1
            assert event_data['total_players'] == 2
            assert 'time_remaining' in event_data
        
        finally:
            client2.disconnect()
    
    def test_room_state_update_during_guessing(self, client, mock_content_manager):
        """Test that room state updates properly during guessing phase."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Clear any remaining events
            client.get_received()
            client2.get_received()
            
            # Submit a guess to trigger room state update
            client.emit('submit_guess', {
                'guess_index': 0
            })
            
            # Check for room_state_updated events
            received1 = client.get_received()
            received2 = client2.get_received()
            
            state_updates1 = [event for event in received1 if event['name'] == 'room_state_updated']
            state_updates2 = [event for event in received2 if event['name'] == 'room_state_updated']
            
            assert len(state_updates1) > 0 or len(state_updates2) > 0
            
            # Check the room state data
            state_event = state_updates1[0] if state_updates1 else state_updates2[0]
            state_data = state_event['args'][0]
            
            assert state_data['phase'] == 'guessing'
            assert 'responses' in state_data
            assert 'guess_count' in state_data
            assert 'time_remaining' in state_data
        
        finally:
            client2.disconnect()
    
    def test_phase_time_remaining_calculation(self, client, mock_content_manager):
        """Test that time remaining is calculated correctly during guessing phase."""
        client2 = socketio.test_client(app)
        
        try:
            self._setup_game_to_guessing_phase(client, client2, mock_content_manager)
            
            # Get the guessing phase start event
            received1 = client.get_received()
            received2 = client2.get_received()
            
            guessing_events1 = [event for event in received1 if event['name'] == 'guessing_phase_started']
            guessing_events2 = [event for event in received2 if event['name'] == 'guessing_phase_started']
            
            # Ensure we have at least one guessing event
            assert len(guessing_events1) > 0 or len(guessing_events2) > 0, "No guessing phase started event found"
            
            guessing_event = guessing_events1[0] if guessing_events1 else guessing_events2[0]
            event_data = guessing_event['args'][0]
            
            # Check that time_remaining is reasonable (should be close to phase_duration)
            assert event_data['time_remaining'] > 0
            assert event_data['time_remaining'] <= event_data['phase_duration']
            
            # Time remaining should be close to phase duration (within a few seconds)
            time_diff = event_data['phase_duration'] - event_data['time_remaining']
            assert time_diff < 5  # Should be less than 5 seconds difference
        
        finally:
            client2.disconnect()


if __name__ == '__main__':
    pytest.main([__file__])