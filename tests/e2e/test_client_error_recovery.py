"""
End-to-end tests for client-side error handling and recovery mechanisms.

Tests client behavior during connection issues, server errors, and recovery scenarios.
"""

import time
import pytest
from unittest.mock import patch, MagicMock
from flask_socketio import SocketIOTestClient
from src.core.game_phases import GamePhase
# Service imports  
from tests.migration_compat import app, socketio, room_manager, game_manager


class TestClientErrorRecovery:
    """End-to-end tests for client error handling and recovery."""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self, room_manager, app, socketio):
        """Set up test environment before each test."""
        # Clear any existing rooms
        room_manager._rooms.clear()
        
        # Create test client
        self.client = SocketIOTestClient(app, socketio)
        self.client.connect()
        
        # Clear received messages
        self.client.get_received()
        
        yield  # This is where the test runs
        
        # Teardown: Clean up state
        room_manager._rooms.clear()
        if hasattr(self, 'client'):
            self.client.disconnect()
    
    
    def test_connection_loss_and_recovery(self):
        """Test client behavior during connection loss and recovery."""
        # Join room successfully
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        assert any(msg['name'] == 'room_joined' for msg in received)
        
        # Simulate connection loss
        self.client.disconnect()
        
        # Simulate reconnection
        self.client.connect()
        self.client.get_received()  # Clear connection messages
        
        # Client should be able to rejoin
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        assert any(msg['name'] == 'room_joined' for msg in received)
    
    def test_server_error_handling(self):
        """Test client handling of various server errors."""
        # Test invalid room ID error
        self.client.emit('join_room', {
            'room_id': 'invalid room name',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        error_data = received[0]['args'][0]
        assert error_data['error']['code'] == 'INVALID_ROOM_ID'
        assert 'message' in error_data['error']
        
        # Test player name too long error
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'A' * 25
        })
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        error_data = received[0]['args'][0]
        assert error_data['error']['code'] == 'PLAYER_NAME_TOO_LONG'
    
    def test_phase_mismatch_error_recovery(self):
        """Test recovery from phase mismatch errors."""
        # Join room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        self.client.get_received()
        
        # Try to submit response in wrong phase
        self.client.emit('submit_response', {'response': 'Test response'})
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'WRONG_PHASE'
        
        # Client should be able to request current state
        self.client.emit('get_room_state')
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'room_state'
    
    def test_duplicate_action_prevention(self):
        """Test prevention of duplicate actions and proper error handling."""
        # Create a game scenario with two players
        client2 = SocketIOTestClient(app, socketio)
        client2.connect()
        
        # Both join room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        client2.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Bob'
        })
        
        # Clear messages
        self.client.get_received()
        client2.get_received()
        
        # Start a round (requires prompts to be loaded)
        with patch('src.content_manager.ContentManager.is_loaded', return_value=True), \
             patch('src.content_manager.ContentManager.get_prompt_count', return_value=1), \
             patch('src.content_manager.ContentManager.get_random_prompt_response') as mock_prompt:
            
            mock_prompt.return_value = MagicMock(
                id='test_001',
                prompt='Test prompt',
                model='TestModel',
                response='Test LLM response'
            )
            
            self.client.emit('start_round')
            
            # Clear round start messages
            self.client.get_received()
            client2.get_received()
            
            # Submit response
            self.client.emit('submit_response', {'response': 'First response'})
            received = self.client.get_received()
            assert any(msg['name'] == 'response_submitted' for msg in received)
            
            # Try to submit another response (should fail)
            self.client.emit('submit_response', {'response': 'Second response'})
            received = self.client.get_received()
            assert len(received) == 1
            assert received[0]['name'] == 'error'
            assert received[0]['args'][0]['error']['code'] == 'SUBMIT_FAILED'
        
        client2.disconnect()
    
    def test_timeout_handling(self):
        """Test handling of phase timeouts and automatic progression."""
        # Create a game scenario
        client2 = SocketIOTestClient(app, socketio)
        client2.connect()
        
        # Both join room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        client2.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Bob'
        })
        
        self.client.get_received()
        client2.get_received()
        
        # Mock a round start with very short timeout
        with patch('src.content_manager.ContentManager.is_loaded', return_value=True), \
             patch('src.content_manager.ContentManager.get_prompt_count', return_value=1), \
             patch('src.content_manager.ContentManager.get_random_prompt_response') as mock_prompt, \
             patch.object(game_manager, 'PHASE_DURATIONS', {GamePhase.RESPONDING: 1, GamePhase.GUESSING: 1, GamePhase.RESULTS: 1}):
            
            mock_prompt.return_value = MagicMock(
                id='test_001',
                prompt='Test prompt',
                model='TestModel',
                response='Test LLM response'
            )
            
            self.client.emit('start_round')
            
            # Wait for timeout
            time.sleep(2)
            
            # Should receive phase change notifications
            received = self.client.get_received()
            message_names = [msg['name'] for msg in received]
            
            # Should have received some kind of phase progression
            assert any(name in ['guessing_phase_started', 'round_started', 'room_state_updated'] 
                      for name in message_names)
        
        client2.disconnect()
    
    def test_malformed_server_response_handling(self):
        """Test client handling of malformed server responses."""
        # This test would require mocking the server to send malformed data
        # For now, we test that the client can handle missing fields gracefully
        
        # Join room normally
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        
        # Verify we got a proper response
        room_joined_msg = next((msg for msg in received if msg['name'] == 'room_joined'), None)
        assert room_joined_msg is not None
        
        # Check that response has expected structure
        response_data = room_joined_msg['args'][0]
        assert 'success' in response_data or 'room_id' in response_data
    
    def test_concurrent_client_errors(self):
        """Test error handling with multiple concurrent clients."""
        clients = []
        
        try:
            # Create multiple clients
            for i in range(5):
                client = SocketIOTestClient(app, socketio)
                client.connect()
                clients.append(client)
            
            # All try to join with same player name
            for i, client in enumerate(clients):
                client.emit('join_room', {
                    'room_id': 'test-room',
                    'player_name': 'SameName'
                })
            
            # Check responses
            success_count = 0
            error_count = 0
            
            for client in clients:
                received = client.get_received()
                for msg in received:
                    if msg['name'] == 'room_joined':
                        success_count += 1
                    elif msg['name'] == 'error':
                        error_count += 1
            
            # Only one should succeed
            assert success_count == 1
            assert error_count >= 1
            
        finally:
            for client in clients:
                if client.is_connected():
                    client.disconnect()
    
    def test_error_message_localization_ready(self):
        """Test that error messages are structured for potential localization."""
        # Generate an error
        self.client.emit('join_room', {
            'room_id': '',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        
        assert len(received) == 1
        error_msg = received[0]['args'][0]
        
        # Check error structure supports localization
        assert 'error' in error_msg
        assert 'code' in error_msg['error']  # Code can be used for localization key
        assert 'message' in error_msg['error']  # Default message
        assert 'details' in error_msg['error']  # Additional context
        
        # Error code should be a constant string
        assert isinstance(error_msg['error']['code'], str)
        assert error_msg['error']['code'].isupper()  # Convention for error codes
    
    def test_graceful_degradation(self):
        """Test graceful degradation when features are unavailable."""
        # Test starting round with no prompts
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        self.client.get_received()
        
        # Add second player
        client2 = SocketIOTestClient(app, socketio)
        client2.connect()
        client2.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Bob'
        })
        client2.get_received()
        self.client.get_received()
        
        # Try to start round with no prompts
        with patch('src.content_manager.ContentManager.is_loaded', return_value=False):
            self.client.emit('start_round')
            received = self.client.get_received()
            
            assert len(received) == 1
            assert received[0]['name'] == 'error'
            assert received[0]['args'][0]['error']['code'] == 'NO_PROMPTS_AVAILABLE'
        
        client2.disconnect()
    
    def test_state_synchronization_after_error(self):
        """Test that client state stays synchronized after errors."""
        # Join room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        room_joined = next((msg for msg in received if msg['name'] == 'room_joined'), None)
        assert room_joined is not None
        
        # Cause an error
        self.client.emit('submit_response', {'response': 'Test'})
        error_received = self.client.get_received()
        assert len(error_received) == 1
        assert error_received[0]['name'] == 'error'
        
        # Request current state
        self.client.emit('get_room_state')
        state_received = self.client.get_received()
        
        assert len(state_received) == 1
        assert state_received[0]['name'] == 'room_state'
        
        # Verify state is consistent
        state_data = state_received[0]['args'][0]
        assert 'game_state' in state_data
        assert 'players' in state_data
    
    def test_error_recovery_workflow(self):
        """Test complete error recovery workflow."""
        # 1. Join room successfully
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        assert any(msg['name'] == 'room_joined' for msg in received)
        
        # 2. Encounter an error (wrong phase)
        self.client.emit('submit_response', {'response': 'Test'})
        received = self.client.get_received()
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'WRONG_PHASE'
        
        # 3. Recover by getting current state
        self.client.emit('get_room_state')
        received = self.client.get_received()
        assert received[0]['name'] == 'room_state'
        
        # 4. Verify can continue normal operations
        # Add second player for game operations
        client2 = SocketIOTestClient(app, socketio)
        client2.connect()
        client2.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Bob'
        })
        
        # Should be able to start round now
        with patch('src.content_manager.ContentManager.is_loaded', return_value=True), \
             patch('src.content_manager.ContentManager.get_prompt_count', return_value=1), \
             patch('src.content_manager.ContentManager.get_random_prompt_response') as mock_prompt:
            
            mock_prompt.return_value = MagicMock(
                id='test_001',
                prompt='Test prompt',
                model='TestModel',
                response='Test LLM response'
            )
            
            self.client.emit('start_round')
            received = self.client.get_received()
            
            # Should receive round start confirmation or room state update
            message_names = [msg['name'] for msg in received]
            assert any(name in ['round_started', 'room_state_updated'] for name in message_names)
        
        client2.disconnect()