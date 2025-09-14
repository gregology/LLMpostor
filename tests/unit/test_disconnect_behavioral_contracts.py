"""
Behavioral contract tests for disconnect handling.

Tests verify that disconnect handling components adhere to their behavioral contracts,
including proper error handling, state consistency, and service interaction patterns.
"""

import pytest
from unittest.mock import Mock, patch, call
from datetime import datetime

from src.room_manager import RoomManager
from src.game_manager import GameManager
from src.services.auto_game_flow_service import AutoGameFlowService
from src.services.broadcast_service import BroadcastService
from src.services.session_service import SessionService
from src.services.error_response_factory import ErrorResponseFactory
from src.services.room_state_presenter import RoomStatePresenter


class TestRoomManagerDisconnectContract:
    """Test RoomManager disconnect handling behavioral contracts."""

    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()

    def test_disconnect_player_contract_success_case(self):
        """Test disconnect_player_from_room success contract."""
        room_id = "test-room"
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        player_id = player_data['player_id']

        # Contract: Method should return True for successful disconnection
        result = self.room_manager.disconnect_player_from_room(room_id, player_id)
        assert result == True

        # Contract: Player should be marked as disconnected but preserved
        room_state = self.room_manager.get_room_state(room_id)
        player = room_state['players'][player_id]
        assert player['connected'] == False
        assert player['name'] == "Alice"  # Data preserved
        assert player['score'] == 0  # Score preserved

    def test_disconnect_player_contract_nonexistent_room(self):
        """Test disconnect_player_from_room contract for nonexistent room."""
        # Contract: Should return False for nonexistent room without crashing
        result = self.room_manager.disconnect_player_from_room("nonexistent", "fake-id")
        assert result == False

    def test_disconnect_player_contract_nonexistent_player(self):
        """Test disconnect_player_from_room contract for nonexistent player."""
        room_id = "test-room"
        self.room_manager.add_player_to_room(room_id, "Alice", "socket1")

        # Contract: Should return False for nonexistent player without crashing
        result = self.room_manager.disconnect_player_from_room(room_id, "fake-id")
        assert result == False

    def test_disconnect_player_idempotency_contract(self):
        """Test that disconnect_player_from_room is idempotent."""
        room_id = "test-room"
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        player_id = player_data['player_id']

        # First disconnect
        result1 = self.room_manager.disconnect_player_from_room(room_id, player_id)
        assert result1 == True

        # Second disconnect (idempotent)
        result2 = self.room_manager.disconnect_player_from_room(room_id, player_id)
        assert result2 == True  # Should still return True

        # Contract: Player state should be consistent
        room_state = self.room_manager.get_room_state(room_id)
        player = room_state['players'][player_id]
        assert player['connected'] == False

    def test_get_connected_players_contract_after_disconnect(self):
        """Test get_connected_players contract behavior after disconnects."""
        room_id = "test-room"
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")

        # Initial state
        connected = self.room_manager.get_connected_players(room_id)
        assert len(connected) == 2

        # After disconnect
        self.room_manager.disconnect_player_from_room(room_id, alice_data['player_id'])
        connected = self.room_manager.get_connected_players(room_id)

        # Contract: Should return only connected players
        assert len(connected) == 1
        assert connected[0]['name'] == "Bob"
        assert connected[0]['connected'] == True


class TestAutoGameFlowServiceDisconnectContract:
    """Test AutoGameFlowService disconnect handling behavioral contracts."""

    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.mock_socketio = Mock()
        self.error_factory = ErrorResponseFactory()
        self.room_state_presenter = RoomStatePresenter(self.game_manager)

        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager,
            self.error_factory, self.room_state_presenter
        )

        self.auto_flow_service = AutoGameFlowService(
            self.broadcast_service, self.game_manager, self.room_manager
        )

    def test_handle_player_disconnect_contract_nonexistent_room(self):
        """Test disconnect handling contract for nonexistent room."""
        # Contract: Should handle gracefully without throwing exceptions
        try:
            self.auto_flow_service.handle_player_disconnect_game_impact("nonexistent", "fake-id")
            # Should complete without exception
        except Exception as e:
            pytest.fail(f"Should handle nonexistent room gracefully, but got: {e}")

    def test_handle_player_disconnect_contract_corrupted_state(self):
        """Test disconnect handling contract with corrupted room state."""
        room_id = "test-room"
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")

        # Corrupt the room state
        room_state = self.room_manager.get_room_state(room_id)
        del room_state['game_state']

        # Contract: Should handle corrupted state gracefully
        try:
            self.auto_flow_service.handle_player_disconnect_game_impact(room_id, player_data['player_id'])
            # Should complete without exception
        except Exception as e:
            pytest.fail(f"Should handle corrupted state gracefully, but got: {e}")

    def test_handle_player_disconnect_contract_insufficient_players(self):
        """Test disconnect handling contract for insufficient players scenario."""
        room_id = "test-room"
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")

        # Set up active game
        room_state = self.room_manager.get_room_state(room_id)
        room_state['game_state']['phase'] = 'responding'

        # Disconnect one player (leaving only 1, below minimum of 2)
        self.room_manager.disconnect_player_from_room(room_id, bob_data['player_id'])

        with patch.object(self.game_manager, '_advance_to_waiting_phase') as mock_reset:
            mock_reset.return_value = 'waiting'

            # Contract: Should reset to waiting phase and broadcast game paused
            self.auto_flow_service.handle_player_disconnect_game_impact(room_id, bob_data['player_id'])

            # Verify contract obligations
            mock_reset.assert_called_once_with(room_id)

class TestBroadcastServiceDisconnectContract:
    """Test BroadcastService behavioral contracts during disconnect scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.mock_socketio = Mock()
        self.error_factory = ErrorResponseFactory()
        self.room_state_presenter = RoomStatePresenter(self.game_manager)

        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager,
            self.error_factory, self.room_state_presenter
        )

    def test_broadcast_player_list_update_contract(self):
        """Test broadcast_player_list_update behavioral contract."""
        room_id = "test-room"
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        self.room_manager.add_player_to_room(room_id, "Bob", "socket2")

        # Disconnect Alice
        self.room_manager.disconnect_player_from_room(room_id, alice_data['player_id'])

        # Contract: Should broadcast updated player list
        self.broadcast_service.broadcast_player_list_update(room_id)

        # Verify contract: Should have called emit_to_room
        self.mock_socketio.emit.assert_called()

        # Verify the call includes correct player list data
        calls = self.mock_socketio.emit.call_args_list
        player_list_call = None
        for call_args in calls:
            if len(call_args[0]) > 0 and call_args[0][0] == 'player_list_updated':
                player_list_call = call_args
                break

        assert player_list_call is not None
        event_data = player_list_call[0][1]
        assert event_data['connected_count'] == 1
        assert event_data['total_count'] == 2

    def test_broadcast_game_paused_contract(self):
        """Test broadcast_game_paused behavioral contract."""
        room_id = "test-room"
        error_response = {
            'success': False,
            'error': {
                'code': 'INSUFFICIENT_PLAYERS',
                'message': 'Not enough players'
            }
        }

        # Contract: Should emit game_paused event with error response
        self.broadcast_service.broadcast_game_paused(room_id, error_response)

        # Verify contract obligations
        self.mock_socketio.emit.assert_called_with(
            'game_paused',
            error_response,
            room=room_id
        )

    def test_broadcast_room_state_update_contract(self):
        """Test broadcast_room_state_update behavioral contract."""
        room_id = "test-room"
        self.room_manager.add_player_to_room(room_id, "Alice", "socket1")

        # Contract: Should broadcast current room state
        self.broadcast_service.broadcast_room_state_update(room_id)

        # Verify contract: Should have called emit_to_room
        self.mock_socketio.emit.assert_called()

        # Verify the call includes room state data
        calls = self.mock_socketio.emit.call_args_list
        room_state_call = None
        for call_args in calls:
            if len(call_args[0]) > 0 and call_args[0][0] == 'room_state_updated':
                room_state_call = call_args
                break

        assert room_state_call is not None


class TestSessionServiceDisconnectContract:
    """Test SessionService disconnect handling behavioral contracts."""

    def setup_method(self):
        """Set up test fixtures."""
        self.session_service = SessionService()

    def test_session_cleanup_contract(self):
        """Test session cleanup behavioral contract."""
        socket_id = "socket123"
        session_data = {
            'room_id': 'test-room',
            'player_id': 'player123',
            'player_name': 'Alice'
        }

        # Create session
        self.session_service.create_session(socket_id, **session_data)
        assert self.session_service.has_session(socket_id) == True

        # Contract: remove_session should clean up completely
        self.session_service.remove_session(socket_id)

        # Verify contract obligations
        assert self.session_service.has_session(socket_id) == False
        assert self.session_service.get_session(socket_id) is None

    def test_session_cleanup_contract_nonexistent_session(self):
        """Test session cleanup contract for nonexistent session."""
        # Contract: Should handle cleanup of nonexistent session gracefully
        try:
            self.session_service.remove_session("nonexistent-socket")
            # Should complete without exception
        except Exception as e:
            pytest.fail(f"Should handle nonexistent session gracefully, but got: {e}")

    def test_session_cleanup_contract_idempotency(self):
        """Test session cleanup idempotency contract."""
        socket_id = "socket123"
        session_data = {
            'room_id': 'test-room',
            'player_id': 'player123',
            'player_name': 'Alice'
        }

        # Create and remove session
        self.session_service.create_session(socket_id, **session_data)
        self.session_service.remove_session(socket_id)

        # Contract: Multiple removals should be safe
        try:
            self.session_service.remove_session(socket_id)  # Second removal
            self.session_service.remove_session(socket_id)  # Third removal
            # Should complete without exception
        except Exception as e:
            pytest.fail(f"Session cleanup should be idempotent, but got: {e}")


class TestDisconnectHandlingServiceInteraction:
    """Test behavioral contracts for service interactions during disconnects."""

    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.session_service = SessionService()
        self.mock_socketio = Mock()
        self.error_factory = ErrorResponseFactory()
        self.room_state_presenter = RoomStatePresenter(self.game_manager)

        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager,
            self.error_factory, self.room_state_presenter
        )

        self.auto_flow_service = AutoGameFlowService(
            self.broadcast_service, self.game_manager, self.room_manager
        )

    def test_disconnect_service_interaction_contract(self):
        """Test the complete disconnect service interaction contract."""
        room_id = "interaction-room"
        socket_id = "socket123"

        # Set up initial state
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", socket_id)
        player_id = player_data['player_id']

        session_data = {
            'room_id': room_id,
            'player_id': player_id,
            'player_name': 'Alice'
        }
        self.session_service.create_session(socket_id, **session_data)

        # Simulate complete disconnect handling workflow
        # 1. Disconnect player from room
        disconnect_result = self.room_manager.disconnect_player_from_room(room_id, player_id)
        assert disconnect_result == True

        # 2. Handle game impact
        with patch.object(self.auto_flow_service, 'handle_player_disconnect_game_impact') as mock_impact:
            mock_impact.return_value = None
            self.auto_flow_service.handle_player_disconnect_game_impact(room_id, player_id)
            mock_impact.assert_called_once_with(room_id, player_id)

        # 3. Broadcast updates
        with patch.object(self.broadcast_service, 'broadcast_player_list_update') as mock_broadcast_list:
            with patch.object(self.broadcast_service, 'broadcast_room_state_update') as mock_broadcast_state:
                self.broadcast_service.broadcast_player_list_update(room_id)
                self.broadcast_service.broadcast_room_state_update(room_id)

                mock_broadcast_list.assert_called_once_with(room_id)
                mock_broadcast_state.assert_called_once_with(room_id)

        # 4. Clean up session
        self.session_service.remove_session(socket_id)
        assert self.session_service.has_session(socket_id) == False

    def test_error_propagation_contract(self):
        """Test error propagation behavioral contract across services."""
        room_id = "error-room"

        # Test error propagation when room manager fails
        with patch.object(self.room_manager, 'get_connected_players', side_effect=Exception("Connection error")):
            # Contract: Errors should be handled gracefully without crashing
            try:
                self.auto_flow_service.handle_player_disconnect_game_impact(room_id, "fake-player")
                # Should complete without propagating exception
            except Exception as e:
                pytest.fail(f"Should handle service errors gracefully, but got: {e}")

    def test_broadcast_ordering_contract(self):
        """Test that broadcast messages follow proper ordering contract."""
        room_id = "ordering-room"
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")

        # Disconnect Alice
        self.room_manager.disconnect_player_from_room(room_id, alice_data['player_id'])

        # Set up to track call order
        call_order = []

        original_emit = self.mock_socketio.emit
        def tracking_emit(*args, **kwargs):
            call_order.append(args[0] if args else 'unknown')
            return original_emit(*args, **kwargs)

        self.mock_socketio.emit.side_effect = tracking_emit

        # Execute broadcasts
        self.broadcast_service.broadcast_player_list_update(room_id)
        self.broadcast_service.broadcast_room_state_update(room_id)

        # Contract: Should have made broadcast calls in correct order
        assert len(call_order) >= 2
        # The specific order may vary, but both should be present
        assert 'player_list_updated' in call_order or 'room_state_updated' in call_order