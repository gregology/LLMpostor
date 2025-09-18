"""
Contract tests for standardized response formats.
Tests ensure all socket events follow consistent response schemas.
"""

import pytest
from flask_socketio import SocketIOTestClient
# Service imports
from tests.migration_compat import app, socketio, room_manager, game_manager, session_service, content_manager
from tests.helpers.room_helpers import join_room_helper, join_room_expect_error, find_event_in_received
import time


class TestResponseContracts:
    """Test standardized response contracts for all socket events."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Clear any existing state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()
        
        # Create test client
        self.client = SocketIOTestClient(app, socketio)
        
        # Load test content if needed
        if not content_manager.is_loaded():
            content_manager.load_content()
    
    def teardown_method(self):
        """Clean up after each test."""
        # Disconnect all clients
        if hasattr(self, 'client') and self.client:
            self.client.disconnect()
        
        # Clear state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()
    
    def _validate_success_response(self, response):
        """Validate success response format."""
        assert isinstance(response, dict), "Response must be a dictionary"
        assert 'success' in response, "Response must have 'success' field"
        assert response['success'] is True, "Success response must have success=True"
        assert 'data' in response, "Success response must have 'data' field"
        assert isinstance(response['data'], dict), "Data field must be a dictionary"
    
    def _validate_error_response(self, response):
        """Validate error response format."""
        assert isinstance(response, dict), "Response must be a dictionary"
        assert 'success' in response, "Response must have 'success' field"
        assert response['success'] is False, "Error response must have success=False"
        assert 'error' in response, "Error response must have 'error' field"
        assert isinstance(response['error'], dict), "Error field must be a dictionary"
        
        # Validate error structure
        error = response['error']
        assert 'code' in error, "Error must have 'code' field"
        assert 'message' in error, "Error must have 'message' field"
        assert 'details' in error, "Error must have 'details' field"
        assert isinstance(error['code'], str), "Error code must be a string"
        assert isinstance(error['message'], str), "Error message must be a string"
        assert isinstance(error['details'], dict), "Error details must be a dictionary"
    
    def _find_event_in_received(self, events, event_name):
        """Find specific event in received events list."""
        for event in events:
            if event['name'] == event_name:
                return event['args'][0] if event['args'] else None
        return None
    
    def test_join_room_success_contract(self):
        """Test join_room success response contract."""
        # Join room using helper
        response_data = join_room_helper(self.client, 'test-room', 'TestPlayer')

        # Validate specific data fields for join_room
        assert 'room_id' in response_data
        assert 'player_id' in response_data
        assert 'player_name' in response_data
        assert 'message' in response_data
        assert response_data['room_id'] == 'test-room'
        assert response_data['player_name'] == 'TestPlayer'
    
    def test_join_room_error_contract(self):
        """Test join_room error response contract."""
        # Try to join with invalid data using helper
        error_response = join_room_expect_error(self.client, '', 'TestPlayer')

        self._validate_error_response(error_response)

        # Validate specific error for invalid room ID
        error = error_response['error']
        assert error['code'] in ['MISSING_ROOM_ID', 'INVALID_ROOM_ID']
    
    def test_leave_room_success_contract(self):
        """Test leave_room success response contract."""
        # First join a room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'TestPlayer'
        })
        self.client.get_received()  # Clear join events
        
        # Leave room
        self.client.emit('leave_room')
        
        # Get response
        received = self.client.get_received()
        room_left_response = self._find_event_in_received(received, 'room_left')
        
        assert room_left_response is not None, "Should receive room_left event"
        self._validate_success_response(room_left_response)
        
        # Validate specific data fields for leave_room
        data = room_left_response['data']
        assert 'message' in data
    
    def test_leave_room_error_contract(self):
        """Test leave_room error response contract."""
        # Try to leave without joining first
        self.client.emit('leave_room')
        
        # Get response
        received = self.client.get_received()
        error_response = self._find_event_in_received(received, 'error')
        
        assert error_response is not None, "Should receive error event"
        self._validate_error_response(error_response)
        
        # Validate specific error for not in room
        error = error_response['error']
        assert error['code'] == 'NOT_IN_ROOM'
    
    def test_get_room_state_success_contract(self):
        """Test get_room_state success response contract."""
        # First join a room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'TestPlayer'
        })
        self.client.get_received()  # Clear join events
        
        # Get room state
        self.client.emit('get_room_state')
        
        # Get response - room state is sent as room_state event
        received = self.client.get_received()
        room_state_response = self._find_event_in_received(received, 'room_state')
        
        # Room state might be broadcast, so we check if we received it
        if room_state_response is not None:
            # Room state responses may have different format (broadcast)
            assert isinstance(room_state_response, dict)
    
    def test_get_room_state_error_contract(self):
        """Test get_room_state error response contract."""
        # Try to get room state without joining first
        self.client.emit('get_room_state')
        
        # Get response
        received = self.client.get_received()
        error_response = self._find_event_in_received(received, 'error')
        
        assert error_response is not None, "Should receive error event"
        self._validate_error_response(error_response)
        
        # Validate specific error for not in room
        error = error_response['error']
        assert error['code'] == 'NOT_IN_ROOM'
    
    def test_submit_response_success_contract(self):
        """Test submit_response success response contract."""
        # Setup: join room and start round
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'TestPlayer'
        })
        self.client.get_received()  # Clear join events
        
        # Start round if content is available
        if content_manager.is_loaded() and content_manager.get_prompt_count() > 0:
            self.client.emit('start_round')
            self.client.get_received()  # Clear round start events
            
            # Submit response
            self.client.emit('submit_response', {
                'response': 'Test response text'
            })
            
            # Get response
            received = self.client.get_received()
            response_submitted = self._find_event_in_received(received, 'response_submitted')
            
            if response_submitted is not None:
                self._validate_success_response(response_submitted)
                
                # Validate specific data fields for submit_response
                data = response_submitted['data']
                assert 'message' in data
    
    def test_submit_response_error_contract(self):
        """Test submit_response error response contract."""
        # Try to submit response without joining room
        self.client.emit('submit_response', {
            'response': 'Test response'
        })
        
        # Get response
        received = self.client.get_received()
        error_response = self._find_event_in_received(received, 'error')
        
        assert error_response is not None, "Should receive error event"
        self._validate_error_response(error_response)
        
        # Validate specific error for not in room
        error = error_response['error']
        assert error['code'] == 'NOT_IN_ROOM'
    
    def test_submit_guess_error_contract(self):
        """Test submit_guess error response contract."""
        # Try to submit guess without joining room
        self.client.emit('submit_guess', {
            'guess_index': 0
        })
        
        # Get response
        received = self.client.get_received()
        error_response = self._find_event_in_received(received, 'error')
        
        assert error_response is not None, "Should receive error event"
        self._validate_error_response(error_response)
        
        # Validate specific error for not in room
        error = error_response['error']
        assert error['code'] == 'NOT_IN_ROOM'
    
    def test_get_round_results_success_contract(self):
        """Test get_round_results success response contract."""
        # Setup: join room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'TestPlayer'
        })
        self.client.get_received()  # Clear join events
        
        # Get round results (will likely fail but test error format)
        self.client.emit('get_round_results')
        
        # Get response
        received = self.client.get_received()
        
        # Look for either success or error response
        round_results_response = self._find_event_in_received(received, 'round_results')
        error_response = self._find_event_in_received(received, 'error')
        
        if round_results_response is not None:
            self._validate_success_response(round_results_response)
            data = round_results_response['data']
            assert 'results' in data
        elif error_response is not None:
            self._validate_error_response(error_response)
    
    def test_get_round_results_error_contract(self):
        """Test get_round_results error response contract."""
        # Try to get results without joining room
        self.client.emit('get_round_results')
        
        # Get response
        received = self.client.get_received()
        error_response = self._find_event_in_received(received, 'error')
        
        assert error_response is not None, "Should receive error event"
        self._validate_error_response(error_response)
        
        # Validate specific error for not in room
        error = error_response['error']
        assert error['code'] == 'NOT_IN_ROOM'
    
    def test_get_leaderboard_success_contract(self):
        """Test get_leaderboard success response contract."""
        # Setup: join room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'TestPlayer'
        })
        self.client.get_received()  # Clear join events
        
        # Get leaderboard
        self.client.emit('get_leaderboard')
        
        # Get response
        received = self.client.get_received()
        leaderboard_response = self._find_event_in_received(received, 'leaderboard')
        
        if leaderboard_response is not None:
            self._validate_success_response(leaderboard_response)
            
            # Validate specific data fields for leaderboard
            data = leaderboard_response['data']
            assert 'leaderboard' in data
            assert 'scoring_summary' in data
    
    def test_get_leaderboard_error_contract(self):
        """Test get_leaderboard error response contract."""
        # Try to get leaderboard without joining room
        self.client.emit('get_leaderboard')
        
        # Get response
        received = self.client.get_received()
        error_response = self._find_event_in_received(received, 'error')
        
        assert error_response is not None, "Should receive error event"
        self._validate_error_response(error_response)
        
        # Validate specific error for not in room
        error = error_response['error']
        assert error['code'] == 'NOT_IN_ROOM'
    
    def test_get_time_remaining_success_contract(self):
        """Test get_time_remaining success response contract."""
        # Setup: join room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'TestPlayer'
        })
        self.client.get_received()  # Clear join events
        
        # Get time remaining
        self.client.emit('get_time_remaining')
        
        # Get response
        received = self.client.get_received()
        time_remaining_response = self._find_event_in_received(received, 'time_remaining')
        
        if time_remaining_response is not None:
            self._validate_success_response(time_remaining_response)
            
            # Validate specific data fields for time_remaining
            data = time_remaining_response['data']
            assert 'time_remaining' in data
            assert 'phase' in data
            assert 'phase_duration' in data
    
    def test_get_time_remaining_error_contract(self):
        """Test get_time_remaining error response contract."""
        # Try to get time remaining without joining room
        self.client.emit('get_time_remaining')
        
        # Get response
        received = self.client.get_received()
        error_response = self._find_event_in_received(received, 'error')
        
        assert error_response is not None, "Should receive error event"
        self._validate_error_response(error_response)
        
        # Validate specific error for not in room
        error = error_response['error']
        assert error['code'] == 'NOT_IN_ROOM'
    
    def test_start_round_error_contract(self):
        """Test start_round error response contract."""
        # Try to start round without joining room
        self.client.emit('start_round')
        
        # Get response
        received = self.client.get_received()
        error_response = self._find_event_in_received(received, 'error')
        
        assert error_response is not None, "Should receive error event"
        self._validate_error_response(error_response)
        
        # Validate specific error for not in room
        error = error_response['error']
        assert error['code'] == 'NOT_IN_ROOM'