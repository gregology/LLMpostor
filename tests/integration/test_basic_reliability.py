"""
Basic Reliability Tests
Simplified reliability tests to validate testing infrastructure and core reliability scenarios.
"""

import pytest
import time
import threading
from flask_socketio import SocketIOTestClient
from tests.helpers.room_helpers import join_room_helper, join_room_expect_error, find_event_in_received


class TestBasicReliability:
    """Test basic reliability scenarios"""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self, room_manager, session_service, app):
        """Set up test environment before each test."""
        # Clear any existing state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()
        
        app.config['TESTING'] = True
        
        yield  # This is where the test runs
        
        # Teardown: Clean up state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()
    
    def create_test_client(self, app, socketio):
        """Create a Socket.IO test client"""
        return SocketIOTestClient(app, socketio)
    
    # Removed local join_room helper - now using shared room_helpers

    def test_basic_connection_handling(self, app, socketio):
        """Test basic connection and disconnection handling"""
        client = self.create_test_client(app, socketio)
        
        # Test connection
        assert client.connected
        
        # Test room joining
        join_data = join_room_helper(client, "test-room", "TestPlayer")
        assert join_data is not None
        assert 'player_id' in join_data
        
        # Test disconnection
        client.disconnect()
        assert not client.connected

    def test_concurrent_room_joining(self, app, socketio):
        """Test multiple clients joining the same room"""
        clients = []
        join_results = []
        
        # Create multiple clients
        for i in range(3):
            clients.append(self.create_test_client(app, socketio))
        
        # Join room concurrently
        def join_room_threaded(client, player_name):
            try:
                result = join_room_helper(client, "concurrent-room", player_name)
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

    def test_invalid_data_handling(self, app, socketio):
        """Test handling of invalid data in requests"""
        client = self.create_test_client(app, socketio)
        
        # Test invalid room join data
        client.emit('join_room', {})  # Missing required fields
        
        responses = client.get_received()
        
        # Should receive error response
        error_responses = [r for r in responses if r['name'] == 'error']
        assert len(error_responses) > 0
        
        client.disconnect()

    def test_game_state_consistency(self, app, socketio):
        """Test basic game state consistency"""
        client1 = self.create_test_client(app, socketio)
        client2 = self.create_test_client(app, socketio)
        
        # Both join same room
        join_room_helper(client1, "consistency-room", "Player1")
        join_room_helper(client2, "consistency-room", "Player2")
        
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

    def test_rapid_requests_handling(self, app, socketio):
        """Test handling of rapid successive requests"""
        client = self.create_test_client(app, socketio)
        join_room_helper(client, "rapid-room", "TestPlayer")
        
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

    def test_error_recovery(self, app, socketio):
        """Test system recovery after errors"""
        client = self.create_test_client(app, socketio)
        join_room_helper(client, "error-room", "TestPlayer")
        
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

    def test_boundary_conditions(self, app, socketio):
        """Test boundary conditions and edge cases"""
        client = self.create_test_client(app, socketio)

        # Test extremely long player name - should be rejected
        long_name = 'A' * 100  # Much longer than reasonable
        error_response = join_room_expect_error(client, "boundary-room", long_name)
        assert error_response['error']['code'] == 'PLAYER_NAME_TOO_LONG'

        client.disconnect()