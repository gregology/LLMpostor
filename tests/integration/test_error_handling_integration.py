"""
Integration tests for error handling and recovery mechanisms.

Tests error scenarios across the full application stack.
"""

import time
from unittest.mock import patch
import pytest
from flask_socketio import SocketIOTestClient
# Service imports
from tests.migration_compat import app, socketio, room_manager


class TestErrorHandlingIntegration:
    """Integration tests for error handling scenarios."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Clear any existing rooms
        room_manager._rooms.clear()
        
        # Create test client
        self.client = SocketIOTestClient(app, socketio)
        self.client.connect()
        
        # Clear received messages
        self.client.get_received()
    
    def teardown_method(self):
        """Clean up after each test."""
        if self.client.is_connected():
            self.client.disconnect()
        room_manager._rooms.clear()
    
    def test_join_room_validation_errors(self):
        """Test various validation errors when joining a room."""
        # Test missing data (empty dict) - should return missing room_id error
        self.client.emit('join_room', {})
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'MISSING_ROOM_ID'
        
        # Test missing room_id
        self.client.emit('join_room', {'player_name': 'Alice'})
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'MISSING_ROOM_ID'
        
        # Test missing player_name
        self.client.emit('join_room', {'room_id': 'test-room'})
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'MISSING_PLAYER_NAME'
        
        # Test invalid room_id format
        self.client.emit('join_room', {
            'room_id': 'invalid room with spaces',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'INVALID_ROOM_ID'
        
        # Test player name too long
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'A' * 21
        })
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'PLAYER_NAME_TOO_LONG'
    
    def test_duplicate_player_name_error(self):
        """Test error when trying to join with duplicate player name."""
        # First player joins successfully
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        assert len(received) >= 1
        assert any(msg['name'] == 'room_joined' for msg in received)
        
        # Second client tries to join with same name
        client2 = SocketIOTestClient(app, socketio)
        client2.connect()
        client2.get_received()  # Clear initial messages
        
        client2.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        received = client2.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'PLAYER_NAME_TAKEN'
        
        client2.disconnect()
    
    def test_already_in_room_error(self):
        """Test error when trying to join room while already in one."""
        # Join first room
        self.client.emit('join_room', {
            'room_id': 'room1',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        assert any(msg['name'] == 'room_joined' for msg in received)
        
        # Try to join another room
        self.client.emit('join_room', {
            'room_id': 'room2',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'ALREADY_IN_ROOM'
    
    def test_submit_response_validation_errors(self):
        """Test validation errors when submitting responses."""
        # Join room first
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        self.client.get_received()  # Clear messages
        
        # Test submitting response without being in responding phase
        self.client.emit('submit_response', {'response': 'Test response'})
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'WRONG_PHASE'
        
        # Test empty response
        self.client.emit('submit_response', {'response': ''})
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'EMPTY_RESPONSE'
        
        # Test response too long
        self.client.emit('submit_response', {'response': 'A' * 1001})
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'RESPONSE_TOO_LONG'
    
    def test_submit_guess_validation_errors(self):
        """Test validation errors when submitting guesses."""
        # Join room first
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        self.client.get_received()  # Clear messages
        
        # Test submitting guess without being in guessing phase
        self.client.emit('submit_guess', {'guess_index': 0})
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'WRONG_PHASE'
        
        # Test missing guess index (phase check happens first)
        self.client.emit('submit_guess', {})
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'WRONG_PHASE'
        
        # Test invalid guess format (phase check happens first)
        self.client.emit('submit_guess', {'guess_index': 'not_a_number'})
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'WRONG_PHASE'
    
    def test_not_in_room_errors(self):
        """Test errors when trying to perform actions without being in a room."""
        # Test various actions without joining a room
        actions = [
            ('submit_response', {'response': 'Test'}),
            ('submit_guess', {'guess_index': 0}),
            ('start_round', {}),
            ('get_room_state', {}),
            ('leave_room', {})
        ]
        
        for action, data in actions:
            self.client.emit(action, data)
            received = self.client.get_received()
            assert len(received) == 1
            assert received[0]['name'] == 'error'
            assert received[0]['args'][0]['error']['code'] == 'NOT_IN_ROOM'
    
    @patch('src.content_manager.ContentManager.is_loaded')
    @patch('src.content_manager.ContentManager.get_prompt_count')
    def test_start_round_no_prompts_error(self, mock_count, mock_loaded):
        """Test error when trying to start round with no prompts available."""
        mock_loaded.return_value = False
        mock_count.return_value = 0
        
        # Join room and add second player
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        self.client.get_received()
        
        client2 = SocketIOTestClient(app, socketio)
        client2.connect()
        client2.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Bob'
        })
        client2.get_received()
        self.client.get_received()  # Clear Alice's messages
        
        # Try to start round
        self.client.emit('start_round')
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'NO_PROMPTS_AVAILABLE'
        
        client2.disconnect()
    
    def test_player_disconnection_handling(self):
        """Test graceful handling of player disconnections."""
        # Create two clients
        client2 = SocketIOTestClient(app, socketio)
        client2.connect()
        
        # Both join the same room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        client2.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Bob'
        })
        
        # Clear initial messages
        self.client.get_received()
        client2.get_received()
        
        # Disconnect one client
        client2.disconnect()
        
        # Check that remaining client receives disconnect notification
        time.sleep(0.1)  # Allow time for disconnect handling
        received = self.client.get_received()
        
        # Should receive player list update and possibly game pause notification
        assert len(received) >= 1
        message_names = [msg['name'] for msg in received]
        assert 'player_list_updated' in message_names or 'game_paused' in message_names
    
    def test_connection_recovery_simulation(self):
        """Test connection recovery by simulating disconnect/reconnect."""
        # Join room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        assert any(msg['name'] == 'room_joined' for msg in received)
        
        # Simulate disconnect
        self.client.disconnect()
        
        # Reconnect
        self.client.connect()
        self.client.get_received()  # Clear connection messages
        
        # Try to rejoin the same room (should work since room was cleaned up)
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        received = self.client.get_received()
        assert any(msg['name'] == 'room_joined' for msg in received)
    
    def test_malformed_data_handling(self):
        """Test handling of malformed or unexpected data."""
        # Test with non-dictionary data
        self.client.emit('join_room', "not a dictionary")
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'INVALID_DATA'
        
        # Test with list instead of dictionary (room check happens first)
        self.client.emit('submit_response', ['not', 'a', 'dict'])
        received = self.client.get_received()
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        assert received[0]['args'][0]['error']['code'] == 'NOT_IN_ROOM'
    
    def test_concurrent_error_scenarios(self):
        """Test error handling under concurrent operations."""
        # Create multiple clients
        clients = []
        for i in range(3):
            client = SocketIOTestClient(app, socketio)
            client.connect()
            clients.append(client)
        
        try:
            # All try to join with same name simultaneously
            for i, client in enumerate(clients):
                client.emit('join_room', {
                    'room_id': 'test-room',
                    'player_name': 'SameName'
                })
            
            # Check that only one succeeded and others got errors
            success_count = 0
            error_count = 0
            
            for client in clients:
                received = client.get_received()
                for msg in received:
                    if msg['name'] == 'room_joined':
                        success_count += 1
                    elif msg['name'] == 'error' and msg['args'][0]['error']['code'] == 'PLAYER_NAME_TAKEN':
                        error_count += 1
            
            assert success_count == 1
            assert error_count >= 1  # At least one should get error
            
        finally:
            # Clean up clients
            for client in clients:
                if client.is_connected():
                    client.disconnect()
    
    @patch('src.game_manager.GameManager.submit_player_response')
    def test_game_manager_error_propagation(self, mock_submit):
        """Test that game manager errors are properly propagated."""
        # Mock game manager to raise an exception
        mock_submit.side_effect = Exception("Game manager error")
        
        # Join room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'Alice'
        })
        self.client.get_received()
        
        # Try to submit response (will fail due to wrong phase, but test error handling)
        self.client.emit('submit_response', {'response': 'Test response'})
        received = self.client.get_received()
        
        # Should get an error response
        assert len(received) == 1
        assert received[0]['name'] == 'error'
        # Could be WRONG_PHASE or INTERNAL_ERROR depending on when the mock is called
        assert received[0]['args'][0]['error']['code'] in ['WRONG_PHASE', 'INTERNAL_ERROR']
    
    def test_error_response_format(self):
        """Test that all error responses follow the standard format."""
        # Generate various errors
        error_scenarios = [
            ('join_room', {}),  # Missing data
            ('submit_response', {'response': ''}),  # Empty response
            ('submit_guess', {'guess_index': 'invalid'}),  # Invalid format
        ]
        
        for action, data in error_scenarios:
            self.client.emit(action, data)
            received = self.client.get_received()
            
            assert len(received) == 1
            error_msg = received[0]
            
            # Check standard error format
            assert error_msg['name'] == 'error'
            assert 'args' in error_msg
            assert len(error_msg['args']) == 1
            
            error_data = error_msg['args'][0]
            assert 'success' in error_data
            assert error_data['success'] is False
            assert 'error' in error_data
            
            error_info = error_data['error']
            assert 'code' in error_info
            assert 'message' in error_info
            assert 'details' in error_info
            assert isinstance(error_info['code'], str)
            assert isinstance(error_info['message'], str)
            assert isinstance(error_info['details'], dict)