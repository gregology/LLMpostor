"""
Unit tests for disconnect handling business logic.

Tests the core disconnect handling functionality without relying on SocketIO client simulation.
Uses direct method calls to test the business logic that would be triggered during disconnects.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.room_manager import RoomManager
from src.game_manager import GameManager
from src.services.auto_game_flow_service import AutoGameFlowService
from src.services.broadcast_service import BroadcastService
from src.services.session_service import SessionService
from src.services.error_response_factory import ErrorResponseFactory
from src.services.room_state_presenter import RoomStatePresenter
from src.core.game_phases import GamePhase


class TestDisconnectHandlingLogic:
    """Test disconnect handling business logic directly."""

    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.session_service = SessionService()
        self.error_factory = ErrorResponseFactory()
        self.room_state_presenter = RoomStatePresenter(self.game_manager)

        # Mock socketio for broadcast service
        self.mock_socketio = Mock()
        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager,
            self.error_factory, self.room_state_presenter
        )

        self.auto_flow_service = AutoGameFlowService(
            self.broadcast_service, self.game_manager, self.room_manager
        )

    def test_single_player_disconnect_cleanup(self):
        """Test that disconnecting a single player marks them as disconnected."""
        room_id = "test-room"

        # Add player to room
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket123")
        player_id = player_data['player_id']

        # Verify player is initially connected
        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 1
        assert connected_players[0]['name'] == 'Alice'
        assert connected_players[0]['connected'] == True

        # Disconnect the player
        success = self.room_manager.disconnect_player_from_room(room_id, player_id)
        assert success == True

        # Verify player is now disconnected but preserved in room
        room_state = self.room_manager.get_room_state(room_id)
        assert len(room_state['players']) == 1  # Player still in room

        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 0  # No connected players

        # Verify player data is preserved with connected=False
        player = list(room_state['players'].values())[0]
        assert player['name'] == 'Alice'
        assert player['connected'] == False
        assert player['score'] == 0  # Score preserved

    def test_multiple_player_disconnect_scenario(self):
        """Test disconnect handling with multiple players."""
        room_id = "multi-player-room"

        # Add three players
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")
        charlie_data = self.room_manager.add_player_to_room(room_id, "Charlie", "socket3")

        # Verify all players connected
        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 3

        # Disconnect Alice
        self.room_manager.disconnect_player_from_room(room_id, alice_data['player_id'])

        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 2
        assert all(p['name'] in ['Bob', 'Charlie'] for p in connected_players)

        # Disconnect Charlie
        self.room_manager.disconnect_player_from_room(room_id, charlie_data['player_id'])

        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 1
        assert connected_players[0]['name'] == 'Bob'

        # Verify all players still in room state
        room_state = self.room_manager.get_room_state(room_id)
        assert len(room_state['players']) == 3

    def test_disconnect_from_nonexistent_room(self):
        """Test disconnect handling for nonexistent room."""
        success = self.room_manager.disconnect_player_from_room("nonexistent", "fake-player-id")
        assert success == False

    def test_disconnect_nonexistent_player(self):
        """Test disconnect handling for nonexistent player."""
        room_id = "test-room"

        # Add a player to create the room
        self.room_manager.add_player_to_room(room_id, "Alice", "socket1")

        # Try to disconnect nonexistent player
        success = self.room_manager.disconnect_player_from_room(room_id, "fake-player-id")
        assert success == False

    def test_session_cleanup_on_disconnect(self):
        """Test that session service properly handles disconnect cleanup."""
        socket_id = "socket123"
        room_id = "test-room"

        # Create session
        session_data = {
            'room_id': room_id,
            'player_id': 'player123',
            'player_name': 'Alice'
        }
        self.session_service.create_session(socket_id, **session_data)

        # Verify session exists
        assert self.session_service.has_session(socket_id) == True
        retrieved_session = self.session_service.get_session(socket_id)
        assert retrieved_session['player_name'] == 'Alice'

        # Simulate disconnect cleanup
        self.session_service.remove_session(socket_id)

        # Verify session removed
        assert self.session_service.has_session(socket_id) == False
        assert self.session_service.get_session(socket_id) is None


class TestDisconnectAutoFlowLogic:
    """Test auto game flow service disconnect handling logic."""

    def setup_method(self):
        """Set up test fixtures for auto flow testing."""
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

    def test_insufficient_players_after_disconnect_resets_to_waiting(self):
        """Test that game resets to waiting when too few players remain."""
        room_id = "test-room"

        # Set up game with minimum players (2)
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")

        # Mock a game in progress (responding phase)
        with patch.object(self.game_manager, 'start_new_round') as mock_start:
            mock_start.return_value = True
            self.game_manager.start_new_round(room_id)

        # Manually set game state to responding phase
        room_state = self.room_manager.get_room_state(room_id)
        room_state['game_state']['phase'] = 'responding'
        room_state['game_state']['round_number'] = 1

        # Disconnect one player, leaving only 1 (below minimum of 2)
        self.room_manager.disconnect_player_from_room(room_id, bob_data['player_id'])

        # Trigger auto flow disconnect handling
        self.auto_flow_service.handle_player_disconnect_game_impact(room_id, bob_data['player_id'])

        # Verify game reset to waiting phase
        final_room_state = self.room_manager.get_room_state(room_id)
        assert final_room_state['game_state']['phase'] == 'waiting'

    def test_no_advancement_when_remaining_players_incomplete(self):
        """Test that phase doesn't advance when remaining players haven't completed current phase."""
        room_id = "test-room"

        # Set up game with 3 players
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")
        charlie_data = self.room_manager.add_player_to_room(room_id, "Charlie", "socket3")

        # Set up game state in responding phase with only 1 response
        room_state = self.room_manager.get_room_state(room_id)
        room_state['game_state'] = {
            'phase': 'responding',
            'round_number': 1,
            'responses': [
                {'player_id': alice_data['player_id'], 'text': 'Alice response'}
                # Bob and Charlie haven't responded
            ],
            'guesses': {},
            'current_prompt': {'id': 'test', 'prompt': 'Test prompt'},
            'phase_start_time': datetime.now(),
            'phase_duration': 60
        }

        # Disconnect Charlie (still leaves Bob who hasn't responded)
        self.room_manager.disconnect_player_from_room(room_id, charlie_data['player_id'])

        # Mock game manager to track if advance is called
        with patch.object(self.game_manager, 'advance_game_phase') as mock_advance:
            # Trigger disconnect handling
            self.auto_flow_service.handle_player_disconnect_game_impact(room_id, charlie_data['player_id'])

            # Verify advance_game_phase was NOT called (Bob still needs to respond)
            mock_advance.assert_not_called()


class TestDisconnectErrorRecovery:
    """Test disconnect handling with error conditions."""

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

    def test_disconnect_handling_with_corrupted_room_state(self):
        """Test disconnect handling when room state is corrupted."""
        room_id = "test-room"

        # Create room and add player
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")

        # Corrupt the room state by removing required fields
        room_state = self.room_manager.get_room_state(room_id)
        del room_state['game_state']  # Remove game_state

        # Disconnect handling should not crash
        try:
            self.auto_flow_service.handle_player_disconnect_game_impact(room_id, player_data['player_id'])
            # Should handle gracefully without throwing exception
        except Exception as e:
            pytest.fail(f"Disconnect handling should handle corrupted state gracefully, but got: {e}")

    def test_disconnect_handling_with_room_manager_error(self):
        """Test disconnect handling when room manager throws errors."""
        room_id = "test-room"

        # Mock room manager to throw error on get_connected_players
        with patch.object(self.room_manager, 'get_connected_players', side_effect=Exception("Connection error")):
            # Should handle error gracefully
            try:
                self.auto_flow_service.handle_player_disconnect_game_impact(room_id, "fake-player-id")
                # Should not crash
            except Exception as e:
                pytest.fail(f"Should handle room manager errors gracefully, but got: {e}")

    def test_disconnect_cleanup_idempotency(self):
        """Test that disconnect cleanup can be called multiple times safely."""
        room_id = "test-room"

        # Add player
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        player_id = player_data['player_id']

        # Disconnect player
        result1 = self.room_manager.disconnect_player_from_room(room_id, player_id)
        assert result1 == True

        # Disconnect again - should be safe
        result2 = self.room_manager.disconnect_player_from_room(room_id, player_id)
        assert result2 == True  # Still returns True for already disconnected player

        # Verify player is still in room but disconnected
        room_state = self.room_manager.get_room_state(room_id)
        assert len(room_state['players']) == 1
        assert not list(room_state['players'].values())[0]['connected']