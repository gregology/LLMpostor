"""
Socket Event Pipeline Integration Tests

Tests the complete Socket.IO event flow through the router, handlers, services, and response pipeline.
Validates middleware execution order, error propagation, and end-to-end event processing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from flask_socketio import SocketIOTestClient

from src.handlers.socket_event_router import SocketEventRouter, EventRouteNotFoundError, create_router_with_socketio
from src.handlers.room_connection_handler import RoomConnectionHandler
from src.handlers.game_action_handler import GameActionHandler
from src.handlers.game_info_handler import GameInfoHandler
from container import ServiceContainer
from tests.migration_compat import app, socketio, room_manager, session_service


class TestSocketEventPipeline:
    """Test complete Socket.IO event pipeline integration."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Clear any existing state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()

        # Create test client with real SocketIO integration
        self.client = SocketIOTestClient(app, socketio)

    def teardown_method(self):
        """Clean up after each test."""
        # Disconnect client
        if hasattr(self, 'client') and self.client:
            self.client.disconnect()

        # Clear state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()

    @pytest.fixture
    def router(self):
        """Create a router instance connected to SocketIO for direct testing."""
        return create_router_with_socketio(socketio)

    def test_socketio_integration_registration(self):
        """Test that router properly registers with SocketIO instance."""
        router = create_router_with_socketio(socketio)

        # Register test handler
        def test_handler(data):
            return {'result': 'success'}

        router.register_route('integration_test', test_handler)

        # Register with SocketIO
        router.register_with_socketio()

        # Verify handler was registered (check internal structures exist)
        assert hasattr(router, 'register_with_socketio')
        assert router.has_route('integration_test')
        assert 'integration_test' in router.get_registered_events()

    def test_real_room_join_through_pipeline(self):
        """Test real room join event flows through complete pipeline."""
        # Test using real SocketIO client to join a room
        received = []

        # Emit room join request
        result = self.client.emit('join_room', {
            'room_id': 'pipeline-test-room',
            'player_name': 'PipelineTestPlayer'
        })

        # Get received events
        received = self.client.get_received()

        # Should have received room_joined success event
        success_events = [event for event in received if event['name'] == 'room_joined']
        assert len(success_events) > 0, "Should receive room_joined event"

        # Extract data from nested structure
        success_response = success_events[0]['args'][0]
        assert success_response['success'] is True
        success_data = success_response['data']

        assert success_data['room_id'] == 'pipeline-test-room'
        assert success_data['player_name'] == 'PipelineTestPlayer'
        assert 'player_id' in success_data

        # Should also receive player list update and room state events
        player_list_events = [event for event in received if event['name'] == 'player_list_updated']
        room_state_events = [event for event in received if event['name'] == 'room_state']

        assert len(player_list_events) > 0, "Should receive player list update"
        assert len(room_state_events) > 0, "Should receive room state update"

        # Verify room state was updated through complete pipeline
        room_state = room_manager.get_room_state('pipeline-test-room')
        assert room_state is not None
        assert len(room_state['players']) == 1

    def test_error_handling_in_real_pipeline(self):
        """Test error handling in real pipeline with invalid data."""
        # Test with invalid room join data (missing required fields)
        result = self.client.emit('join_room', {
            'room_id': 'test-room'
            # Missing 'player_name'
        })

        # Get received events
        received = self.client.get_received()

        # Should have received error event
        error_events = [event for event in received if event['name'] == 'error']
        assert len(error_events) > 0, "Should receive error event for invalid data"

        error_response = error_events[0]['args'][0]
        assert error_response['success'] is False
        assert 'error' in error_response

        error_data = error_response['error']
        assert 'code' in error_data
        assert 'message' in error_data
        assert error_data['code'] == 'MISSING_PLAYER_NAME'

    def test_complete_game_flow_through_pipeline(self):
        """Test a complete game flow through the event pipeline."""
        # 1. Join room
        self.client.emit('join_room', {
            'room_id': 'game-flow-room',
            'player_name': 'GameFlowPlayer'
        })

        # Clear received events
        self.client.get_received()

        # 2. Get room state
        self.client.emit('get_room_state', {})
        received = self.client.get_received()

        # Should receive room state update
        state_events = [event for event in received if event['name'] == 'room_state']
        assert len(state_events) > 0, "Should receive room state event"

        # 3. Verify pipeline maintained state consistency
        room_state = room_manager.get_room_state('game-flow-room')
        assert len(room_state['players']) == 1
        assert list(room_state['players'].values())[0]['name'] == 'GameFlowPlayer'


    def test_concurrent_event_pipeline_handling(self):
        """Test pipeline handles concurrent events properly."""
        # Create multiple clients
        client2 = SocketIOTestClient(app, socketio)

        try:
            # Both clients join the same room
            self.client.emit('join_room', {
                'room_id': 'concurrent-room',
                'player_name': 'Player1'
            })

            client2.emit('join_room', {
                'room_id': 'concurrent-room',
                'player_name': 'Player2'
            })

            # Verify both players are in the room
            room_state = room_manager.get_room_state('concurrent-room')
            assert len(room_state['players']) == 2

            # Verify both clients received appropriate events
            client1_events = self.client.get_received()
            client2_events = client2.get_received()

            # Both should have success events
            assert any(event['name'] == 'room_joined' for event in client1_events)
            assert any(event['name'] == 'room_joined' for event in client2_events)

        finally:
            client2.disconnect()