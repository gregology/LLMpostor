"""
End-to-end tests for complete player connection lifecycle.

Tests the full player journey:
- Connect → Join → Disconnect → Reconnect
- Session preservation concepts
- Multiple client scenarios
- Connection state verification
"""

import time
import pytest
import uuid
from unittest.mock import patch, MagicMock
from flask_socketio import SocketIOTestClient

from tests.migration_compat import app, socketio, room_manager, game_manager
from tests.helpers.room_helpers import (
    join_room_helper, find_event_in_received,
    wait_for_room_state_event, wait_for_player_list_event
)


class TestPlayerConnectionLifecycle:
    """End-to-end tests for player connection lifecycle."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self, app, socketio, request):
        """Set up test environment before each test."""
        # Create test client
        self.client = SocketIOTestClient(app, socketio)
        self.client.connect()

        # Clear received messages
        self.client.get_received()

        # Generate unique identifiers for this test to avoid name collisions
        test_id = str(uuid.uuid4())[:4]
        self.test_room_id = f"lifecycle-{test_id}"
        self.test_player_name = f"P-{test_id}"  # Keep name short to avoid length limits

        yield

        # Teardown: Clean up
        if hasattr(self, 'client') and self.client.is_connected():
            self.client.disconnect()

    def test_basic_connection_and_room_joining(self):
        """Test basic connection and room joining lifecycle."""
        # 1. Initial connection (already done in setup)
        assert self.client.is_connected()

        # 2. Join room
        join_data = join_room_helper(self.client, self.test_room_id, self.test_player_name)
        original_player_id = join_data['player_id']
        assert join_data['room_id'] == self.test_room_id
        assert join_data['player_name'] == self.test_player_name

        # 3. Verify player is in room state
        self.client.emit('get_room_state')
        received = self.client.get_received()
        room_state_event = find_event_in_received(received, 'room_state')
        assert room_state_event is not None
        room_state = room_state_event['args'][0]

        # Verify player is present in room state
        players = room_state['players']
        assert len(players) == 1

        # Handle both dict (direct room manager) and list (presenter) formats
        if isinstance(players, dict):
            player_in_state = next(iter(players.values()))
        else:
            player_in_state = players[0]

        assert player_in_state['name'] == self.test_player_name
        assert player_in_state['connected'] is True

        # 4. Test new connection with different name (simulates reconnection scenario)
        new_client = SocketIOTestClient(app, socketio)
        new_client.connect()

        try:
            reconnect_name = f"{self.test_player_name}-new"
            rejoin_data = join_room_helper(new_client, self.test_room_id, reconnect_name)

            # Should be able to join with new name
            assert rejoin_data['room_id'] == self.test_room_id
            assert rejoin_data['player_name'] == reconnect_name

            # Verify room now has both players
            self.client.emit('get_room_state')
            received = self.client.get_received()
            room_state_event = find_event_in_received(received, 'room_state')
            assert room_state_event is not None
            room_state = room_state_event['args'][0]

            players = room_state['players']
            assert len(players) == 2

        finally:
            if new_client.is_connected():
                new_client.disconnect()

    def test_multiple_clients_connection_lifecycle(self):
        """Test multiple clients connecting and disconnecting."""
        # Create multiple clients
        clients = []
        player_data = []

        try:
            # Create 3 players
            for i in range(3):
                client = SocketIOTestClient(app, socketio)
                client.connect()
                clients.append(client)

                data = join_room_helper(client, self.test_room_id, f"{self.test_player_name}-{i}")
                player_data.append(data)

            # Main client joins as well
            main_data = join_room_helper(self.client, self.test_room_id, self.test_player_name)

            # Verify all 4 players are in room
            self.client.emit('get_room_state')
            received = self.client.get_received()
            room_state_event = find_event_in_received(received, 'room_state')
            assert room_state_event is not None

            room_state = room_state_event['args'][0]
            assert len(room_state['players']) == 4

            # Disconnect some clients
            clients[0].disconnect()
            clients[1].disconnect()

            # Wait for server processing
            time.sleep(0.1)

            # Verify remaining connections still work
            self.client.emit('get_room_state')
            received = self.client.get_received()
            room_state_event = find_event_in_received(received, 'room_state')
            assert room_state_event is not None

            # Room should still exist and function
            room_state = room_state_event['args'][0]
            assert room_state['room_id'] == self.test_room_id

        finally:
            # Clean up all clients
            for client in clients:
                if client.is_connected():
                    client.disconnect()

    def test_session_consistency_during_game_play(self):
        """Test that session data remains consistent during game operations."""
        # Create second client for game interaction
        client2 = SocketIOTestClient(app, socketio)
        client2.connect()

        try:
            # Both players join
            join_data = join_room_helper(self.client, self.test_room_id, self.test_player_name)
            player_id = join_data['player_id']

            join_room_helper(client2, self.test_room_id, f"{self.test_player_name}-2")

            # Clear initial messages
            self.client.get_received()
            client2.get_received()

            # Start a game round
            with patch('src.content_manager.ContentManager.is_loaded', return_value=True), \
                 patch('src.content_manager.ContentManager.get_prompt_count', return_value=1), \
                 patch('src.content_manager.ContentManager.get_random_prompt_response') as mock_prompt:

                mock_prompt.return_value = MagicMock(
                    id='test_001',
                    prompt='Test prompt',
                    model='TestModel',
                    response='Test LLM response'
                )

                # Start round
                self.client.emit('start_round')

                # Wait for round to start
                time.sleep(0.1)
                self.client.get_received()
                client2.get_received()

                # Submit response
                self.client.emit('submit_response', {'response': 'Human response'})

                # Verify session maintained during game operations
                self.client.emit('get_room_state')
                received = self.client.get_received()
                room_state_event = find_event_in_received(received, 'room_state')
                assert room_state_event is not None

                room_state = room_state_event['args'][0]
                # Session should be maintained throughout game operations
                assert room_state['room_id'] == self.test_room_id

                # Player should still exist in room
                players = room_state['players']
                if isinstance(players, dict):
                    assert any(p['player_id'] == player_id for p in players.values())
                else:
                    assert any(p['player_id'] == player_id for p in players)

        finally:
            if client2.is_connected():
                client2.disconnect()

    def test_new_connection_after_disconnect(self):
        """Test that new connections work correctly after previous disconnections."""
        # Join room initially
        join_data = join_room_helper(self.client, self.test_room_id, self.test_player_name)
        original_player_id = join_data['player_id']

        # Disconnect main client
        self.client.disconnect()
        assert not self.client.is_connected()

        # Create completely new client (simulates new browser session)
        new_client = SocketIOTestClient(app, socketio)
        new_client.connect()

        try:
            # Join with different name (new session)
            new_name = f"{self.test_player_name}-new"
            new_join_data = join_room_helper(new_client, self.test_room_id, new_name)

            # Should be able to join successfully
            assert new_join_data['room_id'] == self.test_room_id
            assert new_join_data['player_name'] == new_name

            # Get room state
            new_client.emit('get_room_state')
            received = new_client.get_received()
            room_state_event = find_event_in_received(received, 'room_state')
            assert room_state_event is not None

            room_state = room_state_event['args'][0]
            players = room_state['players']

            # Verify new player exists and is connected
            if isinstance(players, dict):
                new_player = next((p for p in players.values() if p['name'] == new_name), None)
            else:
                new_player = next((p for p in players if p['name'] == new_name), None)

            assert new_player is not None
            assert new_player['connected'] is True

        finally:
            if new_client.is_connected():
                new_client.disconnect()

    def test_connection_state_verification(self):
        """Test that connection states are properly tracked and reported."""
        # Join room
        join_data = join_room_helper(self.client, self.test_room_id, self.test_player_name)

        # Verify initial connected state
        self.client.emit('get_room_state')
        received = self.client.get_received()
        room_state_event = find_event_in_received(received, 'room_state')
        assert room_state_event is not None

        room_state = room_state_event['args'][0]
        players = room_state['players']

        # Verify player is marked as connected
        if isinstance(players, dict):
            player = next(iter(players.values()))
        else:
            player = players[0]

        assert player['connected'] is True
        assert player['name'] == self.test_player_name

        # Test that room state queries continue to work
        for _ in range(3):
            self.client.emit('get_room_state')
            received = self.client.get_received()
            room_state_event = find_event_in_received(received, 'room_state')
            assert room_state_event is not None
            assert room_state_event['args'][0]['room_id'] == self.test_room_id

    def test_error_handling_in_connection_lifecycle(self):
        """Test error handling during connection lifecycle operations."""
        # Join room initially
        join_data = join_room_helper(self.client, self.test_room_id, self.test_player_name)

        # Try to join the same room again with same name (should fail)
        self.client.emit('join_room', {
            'room_id': self.test_room_id,
            'player_name': self.test_player_name
        })
        received = self.client.get_received()

        # Should receive error for already being in room
        error_event = find_event_in_received(received, 'error')
        assert error_event is not None
        assert error_event['args'][0]['error']['code'] == 'ALREADY_IN_ROOM'

        # Verify client can still perform valid operations after error
        self.client.emit('get_room_state')
        received = self.client.get_received()
        room_state_event = find_event_in_received(received, 'room_state')
        assert room_state_event is not None

        # Should still be in the room
        room_state = room_state_event['args'][0]
        assert room_state['room_id'] == self.test_room_id

    def test_room_state_consistency_across_operations(self):
        """Test that room state remains consistent across various operations."""
        # Join room
        join_data = join_room_helper(self.client, self.test_room_id, self.test_player_name)
        player_id = join_data['player_id']

        # Perform multiple operations and verify consistency
        operations = [
            lambda: self.client.emit('get_room_state'),
            lambda: self.client.emit('submit_response', {'response': 'Test'}),  # Should fail gracefully
            lambda: self.client.emit('get_room_state'),
        ]

        for operation in operations:
            operation()
            received = self.client.get_received()

            # Look for room_state event (may be mixed with error events)
            room_state_event = find_event_in_received(received, 'room_state')
            if room_state_event:
                room_state = room_state_event['args'][0]
                assert room_state['room_id'] == self.test_room_id

                # Verify player consistency
                players = room_state['players']
                if isinstance(players, dict):
                    assert any(p['player_id'] == player_id for p in players.values())
                else:
                    assert any(p['player_id'] == player_id for p in players)

    def test_concurrent_connection_operations(self):
        """Test concurrent connection operations don't cause conflicts."""
        # Create multiple clients that connect and join simultaneously
        clients = []

        try:
            # Create and connect multiple clients quickly
            for i in range(3):
                client = SocketIOTestClient(app, socketio)
                client.connect()
                clients.append(client)

                # Join room with unique name
                join_data = join_room_helper(client, self.test_room_id, f"{self.test_player_name}-c{i}")
                assert join_data['room_id'] == self.test_room_id
                assert join_data['player_name'] == f"{self.test_player_name}-c{i}"

            # Main client also joins
            main_data = join_room_helper(self.client, self.test_room_id, self.test_player_name)

            # Verify all clients can get room state
            all_clients = clients + [self.client]
            for client in all_clients:
                client.emit('get_room_state')
                received = client.get_received()
                room_state_event = find_event_in_received(received, 'room_state')
                assert room_state_event is not None

                room_state = room_state_event['args'][0]
                assert room_state['room_id'] == self.test_room_id
                assert len(room_state['players']) == 4

        finally:
            # Clean up all clients
            for client in clients:
                if client.is_connected():
                    client.disconnect()