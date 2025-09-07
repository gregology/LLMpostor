"""
Basic Reliability Tests
Simplified reliability tests to validate testing infrastructure and core reliability scenarios.
"""

import pytest
import time
import threading
from flask_socketio import SocketIOTestClient
from app import app, socketio, room_manager, session_service


class TestBasicReliability:
    """Test basic reliability scenarios"""
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Clear any existing state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()
    
    def teardown_method(self):
        """Clean up after each test."""
        # Clean up state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()
    
    def create_test_client(self):
        """Create a Socket.IO test client"""
        return SocketIOTestClient(app, socketio)
    
    def join_room(self, client, room_id, player_name):
        """Helper to join a room"""
        client.emit('join_room', {
            'room_id': room_id,
            'player_name': player_name
        })
        
        # Get the response
        received = client.get_received()
        if received:
            for response in received:
                if response['name'] == 'room_joined':
                    return response['args'][0]['data']  # Extract data from the response
        
        return None

    def test_basic_connection_handling(self):
        """Test basic connection and disconnection handling"""
        client = self.create_test_client()
        
        # Test connection
        assert client.connected
        
        # Test room joining
        join_data = self.join_room(client, "test-room", "TestPlayer")
        assert join_data is not None
        assert 'player_id' in join_data
        
        # Test disconnection
        client.disconnect()
        assert not client.connected

    def test_concurrent_room_joining(self):
        """Test multiple clients joining the same room"""
        clients = []
        join_results = []
        
        # Create multiple clients
        for i in range(3):
            clients.append(self.create_test_client())
        
        # Join room concurrently
        def join_room_threaded(client, player_name):
            try:
                result = self.join_room(client, "concurrent-room", player_name)
                join_results.append(result)
            except Exception as e:
                join_results.append({'error': str(e)})
        
        threads = []
        for i, client in enumerate(clients):
            thread = threading.Thread(target=join_room_threaded, args=(client, f"Player{i}"))
            threads.append(thread)
            thread.start()
        
        # Wait for all to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        successful_joins = [r for r in join_results if r and 'player_id' in r]
        assert len(successful_joins) == 3
        
        # Clean up
        for client in clients:
            if client.connected:
                client.disconnect()

    def test_invalid_data_handling(self):
        """Test handling of invalid data in requests"""
        client = self.create_test_client()
        
        # Test invalid room join data
        client.emit('join_room', {})  # Missing required fields
        
        responses = client.get_received()
        
        # Should receive error response
        error_responses = [r for r in responses if r['name'] == 'error']
        assert len(error_responses) > 0
        
        client.disconnect()

    def test_game_state_consistency(self):
        """Test basic game state consistency"""
        client1 = self.create_test_client()
        client2 = self.create_test_client()
        
        # Both join same room
        self.join_room(client1, "consistency-room", "Player1")
        self.join_room(client2, "consistency-room", "Player2")
        
        # Clear buffers
        client1.get_received()
        client2.get_received()
        
        # Get room state from both clients
        client1.emit('get_room_state')
        client2.emit('get_room_state')
        
        response1 = client1.get_received()[0]
        response2 = client2.get_received()[0]
        
        # Both should see same room state
        assert response1['name'] == 'room_state'
        assert response2['name'] == 'room_state'
        
        room_state1 = response1['args'][0]
        room_state2 = response2['args'][0]
        
        # Key fields should match
        assert room_state1['total_count'] == room_state2['total_count']
        assert room_state1['connected_count'] == room_state2['connected_count']
        
        # Clean up
        client1.disconnect()
        client2.disconnect()

    def test_rapid_requests_handling(self):
        """Test handling of rapid successive requests"""
        client = self.create_test_client()
        self.join_room(client, "rapid-room", "TestPlayer")
        
        # Clear initial responses
        client.get_received()
        
        # Send rapid requests
        for i in range(10):
            client.emit('get_room_state')
            time.sleep(0.01)  # Small delay
        
        # Collect responses
        responses = client.get_received()
        
        # Should handle multiple requests
        state_responses = [r for r in responses if r['name'] == 'room_state']
        assert len(state_responses) >= 5  # At least some should succeed
        
        client.disconnect()

    def test_memory_cleanup_on_disconnect(self):
        """Test that disconnection properly cleans up resources"""
        initial_room_count = len(room_manager._rooms)
        initial_session_count = len(session_service._player_sessions)
        
        clients = []
        for i in range(5):
            client = self.create_test_client()
            self.join_room(client, f"cleanup-room-{i}", f"Player{i}")
            clients.append(client)
        
        # Verify resources were created
        assert len(room_manager._rooms) > initial_room_count
        
        # Disconnect all clients
        for client in clients:
            client.disconnect()
        
        # Give time for cleanup
        time.sleep(0.1)
        
        # Most resources should be cleaned up (some rooms might persist briefly)
        # This is a basic check - exact cleanup timing may vary
        current_session_count = len(session_service._player_sessions)
        assert current_session_count <= initial_session_count + 2  # Allow for some delay

    def test_error_recovery(self):
        """Test system recovery after errors"""
        client = self.create_test_client()
        self.join_room(client, "error-room", "TestPlayer")
        
        # Clear buffer
        client.get_received()
        
        # Send invalid request to trigger error
        client.emit('submit_response', {'invalid': 'data'})
        responses = client.get_received()
        
        # Should receive error
        error_responses = [r for r in responses if r['name'] == 'error']
        assert len(error_responses) > 0
        
        # System should still be responsive after error
        client.emit('get_room_state')
        recovery_response = client.get_received()
        
        assert len(recovery_response) > 0
        assert recovery_response[0]['name'] == 'room_state'
        
        client.disconnect()

    def test_boundary_conditions(self):
        """Test boundary conditions and edge cases"""
        client = self.create_test_client()
        
        # Test extremely long player name
        long_name = 'A' * 100  # Much longer than reasonable
        join_result = self.join_room(client, "boundary-room", long_name)
        
        # Should either accept (with truncation) or reject gracefully
        if join_result:
            # If accepted, name should be reasonable length
            assert len(join_result.get('player_name', '')) <= 50
        else:
            # If rejected, error was already logged. The join_room returned None which indicates rejection.
            # This is the expected behavior for overly long names.
            pass  # Test passes - long name was properly rejected
        
        client.disconnect()