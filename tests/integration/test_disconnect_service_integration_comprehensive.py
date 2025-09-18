"""
Comprehensive disconnect service integration tests.

This file consolidates disconnect integration testing from:
- test_disconnect_service_integration.py
- test_disconnect_service_integration_reliable.py

Tests service interactions, workflow reliability, and cross-service coordination
during disconnect scenarios with reduced redundancy.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
import time

from src.room_manager import RoomManager
from src.game_manager import GameManager
from src.services.auto_game_flow_service import AutoGameFlowService
from src.services.broadcast_service import BroadcastService
from src.services.session_service import SessionService
from src.services.error_response_factory import ErrorResponseFactory
from src.services.room_state_presenter import RoomStatePresenter
from tests.helpers.socket_mocks import create_mock_socketio


class TestDisconnectWorkflowIntegration:
    """Test complete disconnect workflow integration across all services."""

    def setup_method(self):
        """Set up test fixtures with real services."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.session_service = SessionService()
        self.error_factory = ErrorResponseFactory()
        self.room_state_presenter = RoomStatePresenter(self.game_manager)

        # Mock socketio for broadcast service using shared pattern
        self.mock_socketio = create_mock_socketio()
        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager,
            self.error_factory, self.room_state_presenter
        )

        self.auto_flow_service = AutoGameFlowService(
            self.broadcast_service, self.game_manager, self.room_manager
        )

    def test_complete_disconnect_workflow_integration(self):
        """Test complete disconnect workflow across all services with reliability."""
        room_id = "workflow-integration-room"
        socket_id = "socket123"

        # 1. Set up initial state with session
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", socket_id)
        player_id = player_data['player_id']

        session_data = {
            'room_id': room_id,
            'player_id': player_id,
            'player_name': 'Alice'
        }
        self.session_service.create_session(socket_id, **session_data)

        # Verify initial state
        assert self.session_service.has_session(socket_id) == True
        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 1

        # 2. Execute complete disconnect workflow

        # Step 1: Mark player as disconnected in room
        disconnect_success = self.room_manager.disconnect_player_from_room(room_id, player_id)
        assert disconnect_success == True

        # Step 2: Handle game impact (should be robust)
        try:
            self.auto_flow_service.handle_player_disconnect_game_impact(room_id, player_id)
        except Exception as e:
            pytest.fail(f"Game impact handling should be robust: {e}")

        # Step 3: Broadcast updates
        self.broadcast_service.broadcast_player_list_update(room_id)
        self.broadcast_service.broadcast_room_state_update(room_id)

        # Step 4: Clean up session
        self.session_service.remove_session(socket_id)

        # 3. Verify final integrated state

        # Player should be disconnected but preserved
        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 0

        room_state = self.room_manager.get_room_state(room_id)
        assert len(room_state['players']) == 1
        player = list(room_state['players'].values())[0]
        assert player['connected'] == False
        assert player['name'] == 'Alice'

        # Session should be removed
        assert self.session_service.has_session(socket_id) == False

        # Broadcasts should have been made
        assert self.mock_socketio.emit.call_count >= 2

    def test_multi_player_disconnect_workflow_integration(self):
        """Test disconnect workflow reliability with multiple players."""
        room_id = "multi-workflow-room"

        # Set up multiple players with sessions
        players = []
        for i, name in enumerate(['Alice', 'Bob', 'Charlie']):
            socket_id = f"socket{i}"
            player_data = self.room_manager.add_player_to_room(room_id, name, socket_id)

            session_data = {
                'room_id': room_id,
                'player_id': player_data['player_id'],
                'player_name': name
            }
            self.session_service.create_session(socket_id, **session_data)
            players.append({'socket_id': socket_id, 'player_data': player_data})

        # Verify initial state
        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 3

        # Execute workflow for one player disconnect (Alice)
        alice = players[0]
        alice_player_id = alice['player_data']['player_id']
        alice_socket_id = alice['socket_id']

        # Complete disconnect workflow
        disconnect_result = self.room_manager.disconnect_player_from_room(room_id, alice_player_id)
        assert disconnect_result == True

        self.auto_flow_service.handle_player_disconnect_game_impact(room_id, alice_player_id)
        self.broadcast_service.broadcast_player_list_update(room_id)
        self.session_service.remove_session(alice_socket_id)

        # Verify integrated state consistency
        room_state = self.room_manager.get_room_state(room_id)
        assert len(room_state['players']) == 3  # All players preserved

        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 2  # Only Bob and Charlie connected

        # Verify sessions
        assert not self.session_service.has_session(alice_socket_id)
        assert self.session_service.has_session(players[1]['socket_id'])  # Bob
        assert self.session_service.has_session(players[2]['socket_id'])  # Charlie


class TestDisconnectServiceCoordination:
    """Test service coordination during disconnect scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.session_service = SessionService()
        self.error_factory = ErrorResponseFactory()
        self.room_state_presenter = RoomStatePresenter(self.game_manager)
        self.mock_socketio = create_mock_socketio()

        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager,
            self.error_factory, self.room_state_presenter
        )

        self.auto_flow_service = AutoGameFlowService(
            self.broadcast_service, self.game_manager, self.room_manager
        )

    def test_service_coordination_during_active_game_disconnect(self):
        """Test service coordination when disconnecting during active game states."""
        room_id = "active-game-coordination"

        # Set up game with 3 players in active state
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")
        charlie_data = self.room_manager.add_player_to_room(room_id, "Charlie", "socket3")

        # Set up active game state (not relying on phase advancement)
        room_state = self.room_manager.get_room_state(room_id)
        room_state['game_state']['phase'] = 'responding'
        room_state['game_state']['round_number'] = 1

        # Test service coordination - disconnect and verify service interactions
        disconnect_result = self.room_manager.disconnect_player_from_room(room_id, charlie_data['player_id'])
        assert disconnect_result == True

        # Verify room state is consistent
        post_disconnect_state = self.room_manager.get_room_state(room_id)
        assert len(post_disconnect_state['players']) == 3  # All players preserved

        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 2  # Only Alice and Bob connected

        # Verify broadcast service integration works
        self.broadcast_service.broadcast_player_list_update(room_id)
        self.broadcast_service.broadcast_room_state_update(room_id)

        # Verify service coordination through broadcast calls
        assert self.mock_socketio.emit.call_count >= 2
        call_names = [call_args[0][0] for call_args in self.mock_socketio.emit.call_args_list]
        assert 'player_list_updated' in call_names
        assert 'room_state_updated' in call_names

    def test_concurrent_disconnects_service_coordination(self):
        """Test service stability and coordination with concurrent disconnect operations."""
        room_id = "concurrent-coordination"

        # Set up multiple players
        players = []
        for i, name in enumerate(['Alice', 'Bob', 'Charlie', 'Diana']):
            player_data = self.room_manager.add_player_to_room(room_id, name, f"socket{i}")
            players.append(player_data)

        # Verify initial state
        initial_state = self.room_manager.get_room_state(room_id)
        assert len(initial_state['players']) == 4

        # Perform concurrent-style disconnects with service coordination
        disconnect_results = []
        disconnect_results.append(self.room_manager.disconnect_player_from_room(room_id, players[0]['player_id']))
        disconnect_results.append(self.room_manager.disconnect_player_from_room(room_id, players[2]['player_id']))

        # Verify all operations succeeded
        assert all(disconnect_results)

        # Test service coordination for each disconnect
        for i in [0, 2]:  # Alice and Charlie
            try:
                self.auto_flow_service.handle_player_disconnect_game_impact(room_id, players[i]['player_id'])
            except Exception as e:
                pytest.fail(f"Service coordination should handle concurrent disconnects: {e}")

        # Verify final service state consistency
        final_state = self.room_manager.get_room_state(room_id)
        assert len(final_state['players']) == 4  # All players preserved

        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 2  # Only Bob and Diana connected

        # Verify services handle the final state correctly
        self.broadcast_service.broadcast_player_list_update(room_id)
        self.broadcast_service.broadcast_room_state_update(room_id)

        # Should have successful service coordination
        assert self.mock_socketio.emit.call_count >= 2

    def test_insufficient_players_service_coordination(self):
        """Test service coordination when disconnect results in insufficient players."""
        room_id = "insufficient-coordination"

        # Set up minimum players scenario
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")

        # Set initial active state
        room_state = self.room_manager.get_room_state(room_id)
        room_state['game_state']['phase'] = 'responding'

        # Disconnect one player (leaving insufficient players)
        disconnect_result = self.room_manager.disconnect_player_from_room(room_id, bob_data['player_id'])
        assert disconnect_result == True

        # Test service coordination handles insufficient players scenario gracefully
        try:
            self.auto_flow_service.handle_player_disconnect_game_impact(room_id, bob_data['player_id'])
        except Exception as e:
            pytest.fail(f"Services should coordinate gracefully with insufficient players: {e}")

        # Verify service state after coordination
        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 1  # Only Alice left

        # Verify broadcast services still function in coordination
        self.broadcast_service.broadcast_player_list_update(room_id)
        assert self.mock_socketio.emit.called


class TestDisconnectBroadcastIntegration:
    """Test broadcast service integration during disconnects."""

    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.error_factory = ErrorResponseFactory()
        self.room_state_presenter = RoomStatePresenter(self.game_manager)
        self.mock_socketio = create_mock_socketio()

        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager,
            self.error_factory, self.room_state_presenter
        )

    def test_player_list_broadcast_integration(self):
        """Test that player list broadcasts correctly integrate with disconnect state."""
        room_id = "broadcast-integration"

        # Add players
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")

        # Disconnect Alice
        self.room_manager.disconnect_player_from_room(room_id, alice_data['player_id'])

        # Mock room state presenter to return expected format
        expected_payload = {
            'players': [
                {'player_id': alice_data['player_id'], 'name': 'Alice', 'score': 0, 'connected': False},
                {'player_id': bob_data['player_id'], 'name': 'Bob', 'score': 0, 'connected': True}
            ],
            'connected_count': 1,
            'total_count': 2
        }

        # Mock the room state and presenter for integration testing
        with patch.object(self.room_manager, 'get_connected_players') as mock_connected:
            mock_connected.return_value = [{'player_id': bob_data['player_id'], 'name': 'Bob', 'score': 0, 'connected': True}]

            with patch.object(self.room_state_presenter, 'create_player_list_update') as mock_presenter:
                mock_presenter.return_value = expected_payload

                # Test broadcast integration
                self.broadcast_service.broadcast_player_list_update(room_id)

                # Verify integration points
                mock_presenter.assert_called_once()
                mock_connected.assert_called_once_with(room_id)

                # Verify broadcast integration
                self.mock_socketio.emit.assert_called_once_with(
                    'player_list_updated', expected_payload, room=room_id
                )

    def test_room_state_broadcast_security_integration(self):
        """Test that room state broadcasts properly integrate security filtering."""
        room_id = "security-integration"

        # Add player and set up game
        self.room_manager.add_player_to_room(room_id, "Alice", "socket1")

        # Mock room state with sensitive data
        mock_room_state = {
            'players': {'player1': {'name': 'Alice', 'connected': False}},
            'game_state': {
                'phase': 'responding',
                'current_prompt': {
                    'id': 'prompt1',
                    'prompt': 'Test prompt',
                    'model': 'gpt-4',
                    'ai_response': 'SECRET_RESPONSE'  # Should be filtered
                }
            }
        }

        # Mock presenter to return safe data (integration point)
        safe_game_state = {
            'phase': 'responding',
            'current_prompt': {
                'id': 'prompt1',
                'prompt': 'Test prompt',
                'model': 'gpt-4'
                # ai_response should be filtered out
            }
        }

        with patch.object(self.room_manager, 'get_room_state') as mock_room_state_getter:
            mock_room_state_getter.return_value = mock_room_state

            with patch.object(self.room_state_presenter, 'create_safe_game_state') as mock_presenter:
                mock_presenter.return_value = safe_game_state

                # Test security integration
                self.broadcast_service.broadcast_room_state_update(room_id)

                # Verify security integration
                mock_presenter.assert_called_once_with(mock_room_state, room_id)

                # Verify secure broadcast integration
                self.mock_socketio.emit.assert_called_once_with(
                    'room_state_updated', safe_game_state, room=room_id
                )


class TestDisconnectErrorResilience:
    """Test error resilience and isolation between services during disconnects."""

    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.session_service = SessionService()
        self.mock_socketio = create_mock_socketio()
        self.error_factory = ErrorResponseFactory()
        self.room_state_presenter = RoomStatePresenter(self.game_manager)

        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager,
            self.error_factory, self.room_state_presenter
        )

        self.auto_flow_service = AutoGameFlowService(
            self.broadcast_service, self.game_manager, self.room_manager
        )

    def test_service_isolation_during_errors(self):
        """Test that service errors are isolated and don't break other services."""
        room_id = "error-isolation"

        # Set up test scenario
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")

        # Test service isolation - one service failing shouldn't break others
        with patch.object(self.room_manager, 'get_connected_players', side_effect=Exception("Simulated service error")):

            # Auto flow should handle errors gracefully without breaking other services
            try:
                self.auto_flow_service.handle_player_disconnect_game_impact(room_id, player_data['player_id'])
            except Exception as e:
                # This is acceptable - the key is that other services still work
                pass

            # Other services should remain functional despite the error (isolation)
            disconnect_result = self.room_manager.disconnect_player_from_room(room_id, player_data['player_id'])
            assert disconnect_result == True

            # Broadcast service should still work (service isolation)
            self.broadcast_service.broadcast_room_state_update(room_id)
            self.mock_socketio.emit.assert_called()

    def test_broadcast_error_handling_integration(self):
        """Test broadcast service error handling and recovery during disconnect scenarios."""
        room_id = "broadcast-error-integration"

        # Set up players
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")

        # Disconnect a player
        self.room_manager.disconnect_player_from_room(room_id, alice_data['player_id'])

        # Test broadcast error handling and recovery
        call_count = 0
        def mock_emit_with_error(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Simulated broadcast error")
            return True

        self.mock_socketio.emit.side_effect = mock_emit_with_error

        # Broadcast operations should handle errors gracefully
        try:
            self.broadcast_service.broadcast_player_list_update(room_id)
        except Exception:
            # Error handling is acceptable
            pass

        # Reset side effect for recovery test
        self.mock_socketio.emit.side_effect = None

        # Service should recover and continue working
        try:
            self.broadcast_service.broadcast_room_state_update(room_id)
        except Exception as e:
            pytest.fail(f"Broadcast service should recover from errors: {e}")


class TestDisconnectMemoryManagement:
    """Test memory management and resource cleanup during disconnect scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.session_service = SessionService()

    def test_session_memory_cleanup_integration(self):
        """Test that sessions are properly cleaned up without memory leaks."""
        initial_session_count = len(self.session_service.get_all_sessions())

        # Create multiple sessions (simulating multiple players)
        socket_ids = [f"socket_{i}" for i in range(10)]
        for socket_id in socket_ids:
            self.session_service.create_session(
                socket_id,
                room_id=f"room_{socket_id}",
                player_id=f"player_{socket_id}",
                player_name=f"Player{socket_id}"
            )

        # Verify sessions created
        assert len(self.session_service.get_all_sessions()) == initial_session_count + 10

        # Remove all sessions (simulating disconnects with cleanup)
        for socket_id in socket_ids:
            self.session_service.remove_session(socket_id)

        # Verify complete memory cleanup
        final_session_count = len(self.session_service.get_all_sessions())
        assert final_session_count == initial_session_count

    def test_room_state_preservation_with_memory_management(self):
        """Test that room state is preserved correctly during multiple disconnects without memory leaks."""
        room_id = "memory-preservation"

        # Add multiple players
        players = []
        for i in range(5):
            player_data = self.room_manager.add_player_to_room(room_id, f"Player{i}", f"socket{i}")
            players.append(player_data)

        initial_room_state = self.room_manager.get_room_state(room_id)
        initial_player_count = len(initial_room_state['players'])

        # Disconnect all but one player
        for i in range(4):
            self.room_manager.disconnect_player_from_room(room_id, players[i]['player_id'])

        # Verify room state preservation with proper memory management
        final_room_state = self.room_manager.get_room_state(room_id)

        # All players should still be in room state (preserved)
        assert len(final_room_state['players']) == initial_player_count

        # Only one should be connected
        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 1
        assert connected_players[0]['name'] == 'Player4'

        # Disconnected players should have preserved data
        all_players = list(final_room_state['players'].values())
        disconnected_players = [p for p in all_players if not p['connected']]
        assert len(disconnected_players) == 4

        # Verify data integrity (no memory corruption)
        for i, player in enumerate(disconnected_players):
            assert player['name'] in [f"Player{j}" for j in range(4)]
            assert player['score'] == 0  # Score preserved

    def test_repeated_disconnect_reconnect_memory_stability(self):
        """Test memory stability during repeated disconnect/reconnect cycles."""
        room_id = "memory-stability"

        # Simulate multiple disconnect/reconnect cycles
        for cycle in range(10):
            # Add player
            player_data = self.room_manager.add_player_to_room(room_id, f"Player{cycle}", f"socket{cycle}")

            # Verify player added
            connected = self.room_manager.get_connected_players(room_id)
            assert len(connected) == 1

            # Disconnect player
            self.room_manager.disconnect_player_from_room(room_id, player_data['player_id'])

            # Verify disconnected but preserved
            room_state = self.room_manager.get_room_state(room_id)
            assert len(room_state['players']) == 1

            connected = self.room_manager.get_connected_players(room_id)
            assert len(connected) == 0

            # Remove player completely (simulate cleanup)
            self.room_manager.remove_player_from_room(room_id, player_data['player_id'])

        # Verify no memory accumulation
        final_room_state = self.room_manager.get_room_state(room_id)
        if final_room_state:  # Room might be auto-cleaned
            assert len(final_room_state['players']) == 0