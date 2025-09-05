"""
Integration tests for Socket.IO room operations.
Tests room joining, player management, and real-time updates.
"""

import pytest
from flask_socketio import SocketIOTestClient
from app import app, socketio, room_manager, session_service
import time


class TestSocketIORoomOperations:
    """Test Socket.IO room operation event handlers."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Clear any existing state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()
        
        # Create test client
        self.client = SocketIOTestClient(app, socketio)
    
    def teardown_method(self):
        """Clean up after each test."""
        # Disconnect all clients
        if hasattr(self, 'client') and self.client:
            self.client.disconnect()
        
        # Clear state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()
    
    def test_successful_room_join(self):
        """Test successful room joining."""
        # Connect client
        received = self.client.get_received()
        
        # Join room
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'TestPlayer'
        })
        
        # Check response
        received = self.client.get_received()
        
        # Should receive connected event and room_joined event
        assert len(received) >= 2
        
        # Find room_joined event
        room_joined_event = None
        for event in received:
            if event['name'] == 'room_joined':
                room_joined_event = event
                break
        
        assert room_joined_event is not None
        response = room_joined_event['args'][0]
        assert response['success'] is True
        data = response['data']
        assert data['room_id'] == 'test-room'
        assert data['player_name'] == 'TestPlayer'
        assert 'player_id' in data
        
        # Verify room was created and player added
        room_state = room_manager.get_room_state('test-room')
        assert room_state is not None
        assert len(room_state['players']) == 1
        
        player = list(room_state['players'].values())[0]
        assert player['name'] == 'TestPlayer'
        assert player['connected'] is True
        assert player['score'] == 0
    
    def test_join_room_missing_data(self):
        """Test room join with missing required data."""
        # Connect client
        received = self.client.get_received()
        
        # Try to join without room_id
        self.client.emit('join_room', {
            'player_name': 'TestPlayer'
        })
        
        received = self.client.get_received()
        
        # Should receive error
        error_event = None
        for event in received:
            if event['name'] == 'error':
                error_event = event
                break
        
        assert error_event is not None
        data = error_event['args'][0]
        assert data['error']['code'] == 'MISSING_ROOM_ID'
        
        # Try to join without player_name
        self.client.emit('join_room', {
            'room_id': 'test-room'
        })
        
        received = self.client.get_received()
        
        error_event = None
        for event in received:
            if event['name'] == 'error':
                error_event = event
                break
        
        assert error_event is not None
        data = error_event['args'][0]
        assert data['error']['code'] == 'MISSING_PLAYER_NAME'
    
    def test_join_room_invalid_room_id(self):
        """Test room join with invalid room ID format."""
        # Connect client
        received = self.client.get_received()
        
        # Try to join with invalid room_id
        self.client.emit('join_room', {
            'room_id': 'test room!@#',  # Invalid characters
            'player_name': 'TestPlayer'
        })
        
        received = self.client.get_received()
        
        # Should receive error
        error_event = None
        for event in received:
            if event['name'] == 'error':
                error_event = event
                break
        
        assert error_event is not None
        data = error_event['args'][0]
        assert data['error']['code'] == 'INVALID_ROOM_ID'
    
    def test_join_room_duplicate_player_name(self):
        """Test joining room with duplicate player name."""
        # Create first client and join room
        client1 = SocketIOTestClient(app, socketio)
        client1.get_received()  # Clear initial messages
        
        client1.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'TestPlayer'
        })
        client1.get_received()  # Clear join messages
        
        # Create second client and try to join with same name
        client2 = SocketIOTestClient(app, socketio)
        client2.get_received()  # Clear initial messages
        
        client2.emit('join_room', {
            'room_id': 'test-room',
            'player_name': 'TestPlayer'  # Same name
        })
        
        received = client2.get_received()
        
        # Should receive error
        error_event = None
        for event in received:
            if event['name'] == 'error':
                error_event = event
                break
        
        assert error_event is not None
        data = error_event['args'][0]
        assert data['error']['code'] == 'PLAYER_NAME_TAKEN'
        
        # Verify only one player in room
        room_state = room_manager.get_room_state('test-room')
        assert len(room_state['players']) == 1
        
        # Clean up
        client1.disconnect()
        client2.disconnect()
    
    def test_multiple_players_join_room(self):
        """Test multiple players joining the same room."""
        # Create multiple clients
        clients = []
        player_names = ['Player1', 'Player2', 'Player3']
        
        for i, name in enumerate(player_names):
            client = SocketIOTestClient(app, socketio)
            client.get_received()  # Clear initial messages
            
            client.emit('join_room', {
                'room_id': 'multi-room',
                'player_name': name
            })
            
            received = client.get_received()
            
            # Should receive room_joined event
            room_joined_event = None
            for event in received:
                if event['name'] == 'room_joined':
                    room_joined_event = event
                    break
            
            assert room_joined_event is not None
            response = room_joined_event['args'][0]
            assert response['success'] is True
            data = response['data']
            assert data['player_name'] == name
            
            clients.append(client)
        
        # Verify all players are in room
        room_state = room_manager.get_room_state('multi-room')
        assert len(room_state['players']) == 3
        
        player_names_in_room = [p['name'] for p in room_state['players'].values()]
        assert set(player_names_in_room) == set(player_names)
        
        # Clean up
        for client in clients:
            client.disconnect()
    
    def test_player_list_updates(self):
        """Test that player list updates are broadcast when players join."""
        # Create first client and join
        client1 = SocketIOTestClient(app, socketio)
        client1.get_received()  # Clear initial messages
        
        client1.emit('join_room', {
            'room_id': 'update-room',
            'player_name': 'Player1'
        })
        client1.get_received()  # Clear join messages
        
        # Create second client and join
        client2 = SocketIOTestClient(app, socketio)
        client2.get_received()  # Clear initial messages
        
        client2.emit('join_room', {
            'room_id': 'update-room',
            'player_name': 'Player2'
        })
        
        # Both clients should receive player_list_updated event
        received1 = client1.get_received()
        received2 = client2.get_received()
        
        # Check client1 received player list update
        player_list_event = None
        for event in received1:
            if event['name'] == 'player_list_updated':
                player_list_event = event
                break
        
        assert player_list_event is not None
        data = player_list_event['args'][0]
        assert data['connected_count'] == 2
        assert data['total_count'] == 2
        assert len(data['players']) == 2
        
        # Verify player names
        player_names = [p['name'] for p in data['players']]
        assert 'Player1' in player_names
        assert 'Player2' in player_names
        
        # Clean up
        client1.disconnect()
        client2.disconnect()
    
    def test_leave_room(self):
        """Test leaving a room."""
        # Join room first
        self.client.get_received()  # Clear initial messages
        
        self.client.emit('join_room', {
            'room_id': 'leave-room',
            'player_name': 'TestPlayer'
        })
        self.client.get_received()  # Clear join messages
        
        # Leave room
        self.client.emit('leave_room')
        
        received = self.client.get_received()
        
        # Should receive room_left event
        room_left_event = None
        for event in received:
            if event['name'] == 'room_left':
                room_left_event = event
                break
        
        assert room_left_event is not None
        data = room_left_event['args'][0]
        assert data['success'] is True
        
        # Verify room is empty and cleaned up
        room_state = room_manager.get_room_state('leave-room')
        assert room_state is None  # Room should be deleted when empty
    
    def test_leave_room_not_in_room(self):
        """Test leaving room when not in a room."""
        # Try to leave without joining
        self.client.get_received()  # Clear initial messages
        
        self.client.emit('leave_room')
        
        received = self.client.get_received()
        
        # Should receive error
        error_event = None
        for event in received:
            if event['name'] == 'error':
                error_event = event
                break
        
        assert error_event is not None
        error_response = error_event['args'][0]
        assert error_response['success'] is False
        assert error_response['error']['code'] == 'NOT_IN_ROOM'
    
    def test_disconnect_cleanup(self):
        """Test that disconnection properly cleans up player from room."""
        # Create two clients and join room
        client1 = SocketIOTestClient(app, socketio)
        client1.get_received()
        
        client1.emit('join_room', {
            'room_id': 'disconnect-room',
            'player_name': 'Player1'
        })
        client1.get_received()
        
        client2 = SocketIOTestClient(app, socketio)
        client2.get_received()
        
        client2.emit('join_room', {
            'room_id': 'disconnect-room',
            'player_name': 'Player2'
        })
        client2.get_received()
        
        # Verify both players in room
        room_state = room_manager.get_room_state('disconnect-room')
        assert len(room_state['players']) == 2
        
        # Disconnect one client
        client1.disconnect()
        
        # Give some time for cleanup
        time.sleep(0.1)
        
        # Verify player was removed
        room_state = room_manager.get_room_state('disconnect-room')
        assert len(room_state['players']) == 1
        
        remaining_player = list(room_state['players'].values())[0]
        assert remaining_player['name'] == 'Player2'
        
        # Clean up
        client2.disconnect()
    
    def test_get_room_state(self):
        """Test getting current room state."""
        # Join room first
        self.client.get_received()
        
        self.client.emit('join_room', {
            'room_id': 'state-room',
            'player_name': 'TestPlayer'
        })
        self.client.get_received()  # Clear join messages
        
        # Request room state
        self.client.emit('get_room_state')
        
        received = self.client.get_received()
        
        # Should receive room_state event
        room_state_event = None
        for event in received:
            if event['name'] == 'room_state':
                room_state_event = event
                break
        
        assert room_state_event is not None
        data = room_state_event['args'][0]
        
        assert data['room_id'] == 'state-room'
        assert data['connected_count'] == 1
        assert data['total_count'] == 1
        assert len(data['players']) == 1
        assert data['players'][0]['name'] == 'TestPlayer'
        assert 'game_state' in data
        assert data['game_state']['phase'] == 'waiting'
    
    def test_get_room_state_not_in_room(self):
        """Test getting room state when not in a room."""
        self.client.get_received()
        
        # Request room state without joining
        self.client.emit('get_room_state')
        
        received = self.client.get_received()
        
        # Should receive error
        error_event = None
        for event in received:
            if event['name'] == 'error':
                error_event = event
                break
        
        assert error_event is not None
        error_response = error_event['args'][0]
        assert error_response['success'] is False
        assert error_response['error']['code'] == 'NOT_IN_ROOM'
    
    def test_player_name_length_validation(self):
        """Test player name length validation."""
        self.client.get_received()
        
        # Try to join with too long name
        long_name = 'a' * 21  # 21 characters, limit is 20
        
        self.client.emit('join_room', {
            'room_id': 'test-room',
            'player_name': long_name
        })
        
        received = self.client.get_received()
        
        # Should receive error
        error_event = None
        for event in received:
            if event['name'] == 'error':
                error_event = event
                break
        
        assert error_event is not None
        error_response = error_event['args'][0]
        assert error_response['success'] is False
        assert error_response['error']['code'] == 'PLAYER_NAME_TOO_LONG'
    
    def test_already_in_room_error(self):
        """Test error when trying to join room while already in one."""
        self.client.get_received()
        
        # Join first room
        self.client.emit('join_room', {
            'room_id': 'room1',
            'player_name': 'TestPlayer'
        })
        self.client.get_received()
        
        # Try to join second room
        self.client.emit('join_room', {
            'room_id': 'room2',
            'player_name': 'TestPlayer'
        })
        
        received = self.client.get_received()
        
        # Should receive error
        error_event = None
        for event in received:
            if event['name'] == 'error':
                error_event = event
                break
        
        assert error_event is not None
        error_response = error_event['args'][0]
        assert error_response['success'] is False
        assert error_response['error']['code'] == 'ALREADY_IN_ROOM'


if __name__ == '__main__':
    pytest.main([__file__])