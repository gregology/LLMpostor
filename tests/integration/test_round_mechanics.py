"""
Integration tests for game round mechanics and response submission.

Tests the Socket.IO event handlers for starting rounds and submitting responses,
including validation, time limits, and phase management.
"""

import pytest
from unittest.mock import patch

# Import the Flask app and Socket.IO client for testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app import app, socketio, room_manager, content_manager
from src.content_manager import PromptData


class TestRoundMechanics:
    """Test class for round mechanics and response submission."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for Socket.IO."""
        app.config['TESTING'] = True
        # Clear any existing rooms and sessions before each test
        room_manager._rooms.clear()
        from app import session_service
        session_service._player_sessions.clear()
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
                responses=["Artificial intelligence (AI) is a branch of computer science..."]
            )
            test_prompt.select_random_response()  # Ensure response is selected for tests
            mock_get_prompt.return_value = test_prompt
            yield mock_get_prompt
    
    def test_start_round_success(self, client, mock_content_manager):
        """Test successful round start."""
        # Join a room first
        client.emit('join_room', {
            'room_id': 'test_room_1',
            'player_name': 'Player1'
        })
        
        # Add a second player to meet minimum requirement
        client2 = socketio.test_client(app)
        client2.emit('join_room', {
            'room_id': 'test_room_1',
            'player_name': 'Player2'
        })
        
        # Clear initial events
        client.get_received()
        client2.get_received()
        
        # Start a round
        client.emit('start_round')
        
        # Check for successful round start
        received = client.get_received()
        
        # Should receive round_started event
        event_types = [event['name'] for event in received]
        assert 'round_started' in event_types
        
        # Find the round_started event - it should contain prompt info, not success flag
        round_started_event = next(event for event in received if event['name'] == 'round_started')
        event_data = round_started_event['args'][0]
        
        # Check that it contains prompt information
        assert 'prompt' in event_data
        assert 'model' in event_data
        assert 'round_number' in event_data
        
        # Verify content manager was called
        mock_content_manager.assert_called_once()
        
        # Clean up
        client2.disconnect()
    
    def test_start_round_not_in_room(self, client, mock_content_manager):
        """Test starting round when not in a room."""
        client.emit('start_round')
        
        received = client.get_received()
        error_event = next(event for event in received if event['name'] == 'error')
        
        assert error_event['args'][0]['error']['code'] == 'NOT_IN_ROOM'
        assert 'not currently in a room' in error_event['args'][0]['error']['message']
    
    def test_start_round_insufficient_players(self, client, mock_content_manager):
        """Test starting round with insufficient players."""
        # Join room with only one player
        client.emit('join_room', {
            'room_id': 'test_room_2',
            'player_name': 'Player1'
        })
        
        # Clear join events
        client.get_received()
        
        client.emit('start_round')
        
        received = client.get_received()
        error_event = next(event for event in received if event['name'] == 'error')
        
        assert error_event['args'][0]['error']['code'] == 'CANNOT_START_ROUND'
        assert 'at least 2 players' in error_event['args'][0]['error']['message']
    
    def test_start_round_no_prompts_available(self, client):
        """Test starting round when no prompts are loaded."""
        with patch.object(content_manager, 'is_loaded', return_value=False):
            # Join room with two players
            client.emit('join_room', {
                'room_id': 'test_room_3',
                'player_name': 'Player1'
            })
            
            client2 = socketio.test_client(app)
            client2.emit('join_room', {
                'room_id': 'test_room_3',
                'player_name': 'Player2'
            })
            
            # Clear join events
            client.get_received()
            client2.get_received()
            
            client.emit('start_round')
            
            received = client.get_received()
            error_event = next(event for event in received if event['name'] == 'error')
            
            assert error_event['args'][0]['error']['code'] == 'NO_PROMPTS_AVAILABLE'
            
            client2.disconnect()
    
    def test_submit_response_success(self, client, mock_content_manager):
        """Test successful response submission."""
        # Join room and start round
        client.emit('join_room', {
            'room_id': 'test_room_4',
            'player_name': 'Player1'
        })
        
        client2 = socketio.test_client(app)
        client2.emit('join_room', {
            'room_id': 'test_room_4',
            'player_name': 'Player2'
        })
        
        # Clear join events
        client.get_received()
        client2.get_received()
        
        client.emit('start_round')
        
        # Clear round start events
        client.get_received()
        client2.get_received()
        
        # Submit response
        test_response = "AI is a field of computer science that creates intelligent machines."
        client.emit('submit_response', {
            'response': test_response
        })
        
        received = client.get_received()
        
        # Should receive response_submitted confirmation
        response_event = next(event for event in received if event['name'] == 'response_submitted')
        assert response_event['args'][0]['success'] is True
        
        client2.disconnect()
    
    def test_submit_response_not_in_room(self, client):
        """Test submitting response when not in a room."""
        client.emit('submit_response', {
            'response': 'Test response'
        })
        
        received = client.get_received()
        error_event = next(event for event in received if event['name'] == 'error')
        
        assert error_event['args'][0]['error']['code'] == 'NOT_IN_ROOM'
    
    def test_submit_response_empty(self, client, mock_content_manager):
        """Test submitting empty response."""
        # Join room and start round
        client.emit('join_room', {
            'room_id': 'test_room_5',
            'player_name': 'Player1'
        })
        
        client2 = socketio.test_client(app)
        client2.emit('join_room', {
            'room_id': 'test_room_5',
            'player_name': 'Player2'
        })
        
        # Clear join events
        client.get_received()
        client2.get_received()
        
        client.emit('start_round')
        
        # Clear round start events
        client.get_received()
        client2.get_received()
        
        # Submit empty response
        client.emit('submit_response', {
            'response': ''
        })
        
        received = client.get_received()
        error_event = next(event for event in received if event['name'] == 'error')
        
        assert error_event['args'][0]['error']['code'] == 'EMPTY_RESPONSE'
        
        client2.disconnect()
    
    def test_submit_response_too_long(self, client, mock_content_manager):
        """Test submitting response that's too long."""
        # Join room and start round
        client.emit('join_room', {
            'room_id': 'test_room_6',
            'player_name': 'Player1'
        })
        
        client2 = socketio.test_client(app)
        client2.emit('join_room', {
            'room_id': 'test_room_6',
            'player_name': 'Player2'
        })
        
        # Clear join events
        client.get_received()
        client2.get_received()
        
        client.emit('start_round')
        
        # Clear round start events
        client.get_received()
        client2.get_received()
        
        # Submit response that's too long (over 100 characters)
        long_response = 'A' * 101
        client.emit('submit_response', {
            'response': long_response
        })
        
        received = client.get_received()
        error_event = next(event for event in received if event['name'] == 'error')
        
        assert error_event['args'][0]['error']['code'] == 'RESPONSE_TOO_LONG'
        
        client2.disconnect()
    
    def test_submit_response_wrong_phase(self, client):
        """Test submitting response during wrong game phase."""
        # Join room (but don't start round, so phase is 'waiting')
        client.emit('join_room', {
            'room_id': 'test_room_7',
            'player_name': 'Player1'
        })
        
        client.get_received()  # Clear events
        
        client.emit('submit_response', {
            'response': 'Test response'
        })
        
        received = client.get_received()
        error_event = next(event for event in received if event['name'] == 'error')
        
        assert error_event['args'][0]['error']['code'] == 'WRONG_PHASE'
    
    def test_submit_response_duplicate(self, client, mock_content_manager):
        """Test submitting response twice (should fail second time)."""
        # Join room and start round
        client.emit('join_room', {
            'room_id': 'test_room_8',
            'player_name': 'Player1'
        })
        
        client2 = socketio.test_client(app)
        client2.emit('join_room', {
            'room_id': 'test_room_8',
            'player_name': 'Player2'
        })
        
        # Clear join events
        client.get_received()
        client2.get_received()
        
        client.emit('start_round')
        
        # Clear round start events
        client.get_received()
        client2.get_received()
        
        # Submit first response
        client.emit('submit_response', {
            'response': 'First response'
        })
        
        client.get_received()  # Clear events
        
        # Try to submit second response
        client.emit('submit_response', {
            'response': 'Second response'
        })
        
        received = client.get_received()
        error_event = next(event for event in received if event['name'] == 'error')
        
        assert error_event['args'][0]['error']['code'] == 'SUBMIT_FAILED'
        
        client2.disconnect()
    
    def test_response_phase_auto_advance(self, client, mock_content_manager):
        """Test that response phase auto-advances when all players submit."""
        # Join room with two players
        client.emit('join_room', {
            'room_id': 'test_room_9',
            'player_name': 'Player1'
        })
        
        client2 = socketio.test_client(app)
        client2.emit('join_room', {
            'room_id': 'test_room_9',
            'player_name': 'Player2'
        })
        
        # Clear join events
        client.get_received()
        client2.get_received()
        
        client.emit('start_round')
        
        # Clear round start events
        client.get_received()
        client2.get_received()
        
        # Both players submit responses
        client.emit('submit_response', {
            'response': 'Response from player 1'
        })
        
        client2.emit('submit_response', {
            'response': 'Response from player 2'
        })
        
        # Check that game state updates indicate phase change
        # This would be verified by checking room state updates
        received1 = client.get_received()
        received2 = client2.get_received()
        
        # Should have room_state_updated events indicating phase change
        state_updates1 = [event for event in received1 if event['name'] == 'room_state_updated']
        state_updates2 = [event for event in received2 if event['name'] == 'room_state_updated']
        
        assert len(state_updates1) > 0 or len(state_updates2) > 0
        
        client2.disconnect()
    
    def test_invalid_data_format(self, client):
        """Test handling of invalid data formats."""
        client.emit('join_room', {
            'room_id': 'test_room_10',
            'player_name': 'Player1'
        })
        
        client.get_received()  # Clear events
        
        # Send invalid data format
        client.emit('submit_response', 'invalid_string_data')
        
        received = client.get_received()
        error_event = next(event for event in received if event['name'] == 'error')
        
        assert error_event['args'][0]['error']['code'] == 'INVALID_DATA'


if __name__ == '__main__':
    pytest.main([__file__])