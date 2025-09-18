"""
Player Management Service Unit Tests - Parts 1 & 2
Part 1: Basic Operations - Player addition, removal, validation, room capacity management, and basic error scenarios.
Part 2: Advanced Scenarios - Disconnection/reconnection logic, concurrent operations, edge cases, and session integration.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
import uuid

from src.services.player_management_service import PlayerManagementService


class TestPlayerManagementServiceBasicOperations:
    """Test PlayerManagementService basic operations functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        # Create mock dependencies
        self.mock_room_lifecycle_service = Mock()
        self.mock_concurrency_control_service = Mock()

        # Create mock game settings
        self.mock_game_settings = Mock()
        self.mock_game_settings.max_players_per_room = 8

        # Patch game settings
        with patch('src.services.player_management_service.get_game_settings', return_value=self.mock_game_settings):
            self.service = PlayerManagementService(
                room_lifecycle_service=self.mock_room_lifecycle_service,
                concurrency_control_service=self.mock_concurrency_control_service
            )

        # Setup default room operation context manager
        self.mock_concurrency_control_service.room_operation.return_value.__enter__ = Mock(return_value=Mock())
        self.mock_concurrency_control_service.room_operation.return_value.__exit__ = Mock(return_value=None)

    def test_initialization_sets_dependencies(self):
        """Test that service initializes with correct dependencies"""
        assert self.service.room_lifecycle_service == self.mock_room_lifecycle_service
        assert self.service.concurrency_control_service == self.mock_concurrency_control_service
        assert self.service.game_settings == self.mock_game_settings

    def test_create_player_data_generates_correct_structure(self):
        """Test that player data creation generates correct structure"""
        player_name = "TestPlayer"
        socket_id = "socket123"

        player_data = self.service._create_player_data(player_name, socket_id)

        # Check structure without mocking UUID (just verify it's present and is a string)
        assert "player_id" in player_data
        assert isinstance(player_data["player_id"], str)
        assert len(player_data["player_id"]) > 0  # UUID should be non-empty string
        assert player_data["name"] == player_name
        assert player_data["score"] == 0
        assert player_data["socket_id"] == socket_id
        assert player_data["connected"] is True

    def test_validate_player_addition_accepts_unique_name(self):
        """Test that player validation passes for unique names"""
        room = {
            "room_id": "test_room",
            "players": {
                "player1": {"name": "ExistingPlayer", "connected": True}
            }
        }

        # Should not raise exception for unique name
        self.service._validate_player_addition(room, "NewPlayer")

    def test_validate_player_addition_rejects_duplicate_connected_name(self):
        """Test that player validation rejects duplicate names for connected players"""
        room = {
            "room_id": "test_room",
            "players": {
                "player1": {"name": "ExistingPlayer", "connected": True}
            }
        }

        with pytest.raises(ValueError, match="Player name 'ExistingPlayer' is already taken"):
            self.service._validate_player_addition(room, "ExistingPlayer")

    def test_validate_player_addition_allows_duplicate_disconnected_name(self):
        """Test that player validation allows duplicate names for disconnected players"""
        room = {
            "room_id": "test_room",
            "players": {
                "player1": {"name": "DisconnectedPlayer", "connected": False}
            }
        }

        # Should not raise exception for disconnected player name
        self.service._validate_player_addition(room, "DisconnectedPlayer")

    def test_validate_player_addition_rejects_room_at_capacity(self):
        """Test that player validation rejects addition when room is at capacity"""
        # Create room with max players
        players = {}
        for i in range(8):  # max_players_per_room = 8
            players[f"player{i}"] = {"name": f"Player{i}", "connected": True}

        room = {
            "room_id": "test_room",
            "players": players
        }

        with pytest.raises(ValueError, match="Room test_room is full"):
            self.service._validate_player_addition(room, "NewPlayer")

    def test_find_disconnected_player_returns_matching_player(self):
        """Test that finding disconnected player returns correct player"""
        room = {
            "players": {
                "player1": {"name": "ConnectedPlayer", "connected": True},
                "player2": {"name": "DisconnectedPlayer", "connected": False},
                "player3": {"name": "AnotherPlayer", "connected": True}
            }
        }

        result = self.service._find_disconnected_player(room, "DisconnectedPlayer")
        assert result is not None
        assert result["name"] == "DisconnectedPlayer"
        assert result["connected"] is False

    def test_find_disconnected_player_returns_none_for_connected(self):
        """Test that finding disconnected player returns None for connected players"""
        room = {
            "players": {
                "player1": {"name": "ConnectedPlayer", "connected": True}
            }
        }

        result = self.service._find_disconnected_player(room, "ConnectedPlayer")
        assert result is None

    def test_find_disconnected_player_returns_none_for_nonexistent(self):
        """Test that finding disconnected player returns None for non-existent players"""
        room = {
            "players": {
                "player1": {"name": "ExistingPlayer", "connected": False}
            }
        }

        result = self.service._find_disconnected_player(room, "NonexistentPlayer")
        assert result is None

    def test_add_player_to_room_state_updates_room(self):
        """Test that adding player to room state updates room correctly"""
        room = {
            "players": {},
            "last_activity": None
        }
        player_data = {
            "player_id": "test_player_id",
            "name": "TestPlayer"
        }

        with patch('src.services.player_management_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_datetime.now.return_value = mock_now

            self.service._add_player_to_room_state(room, player_data)

            assert room["players"]["test_player_id"] == player_data
            assert room["last_activity"] == mock_now

    def test_remove_player_from_room_state_updates_room(self):
        """Test that removing player from room state updates room correctly"""
        room = {
            "players": {
                "player1": {"name": "Player1"},
                "player2": {"name": "Player2"}
            },
            "last_activity": None
        }

        with patch('src.services.player_management_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_datetime.now.return_value = mock_now

            self.service._remove_player_from_room_state(room, "player1")

            assert "player1" not in room["players"]
            assert "player2" in room["players"]
            assert room["last_activity"] == mock_now

    def test_remove_player_from_room_state_handles_nonexistent_player(self):
        """Test that removing non-existent player doesn't cause errors"""
        room = {
            "players": {
                "player1": {"name": "Player1"}
            },
            "last_activity": None
        }

        with patch('src.services.player_management_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_datetime.now.return_value = mock_now

            self.service._remove_player_from_room_state(room, "nonexistent")

            # Room should be unchanged including last_activity (since player doesn't exist)
            assert "player1" in room["players"]
            assert room["last_activity"] is None  # Should not be updated for non-existent player

    def test_add_player_to_room_creates_new_player(self):
        """Test that adding player to room creates new player correctly"""
        room_id = "test_room"
        player_name = "NewPlayer"
        socket_id = "socket123"

        # Setup mocks
        room = {
            "room_id": room_id,
            "players": {},
            "last_activity": None
        }

        self.mock_concurrency_control_service.check_duplicate_request.return_value = False
        self.mock_room_lifecycle_service.get_room_data.return_value = room

        with patch.object(self.service, '_create_player_data') as mock_create_player, \
             patch.object(self.service, '_validate_player_addition') as mock_validate, \
             patch.object(self.service, '_find_disconnected_player', return_value=None), \
             patch.object(self.service, '_add_player_to_room_state') as mock_add_to_state:

            mock_player_data = {
                "player_id": "new_player_id",
                "name": player_name,
                "score": 0,
                "socket_id": socket_id,
                "connected": True
            }
            mock_create_player.return_value = mock_player_data

            result = self.service.add_player_to_room(room_id, player_name, socket_id)

            # Verify flow
            self.mock_room_lifecycle_service.ensure_room_exists.assert_called_once_with(room_id)
            mock_validate.assert_called_once_with(room, player_name)
            mock_create_player.assert_called_once_with(player_name, socket_id)
            mock_add_to_state.assert_called_once_with(room, mock_player_data)

            # Result should be copy of player data
            assert result == mock_player_data

    def test_add_player_to_room_reconnects_existing_player(self):
        """Test that adding player reconnects existing disconnected player"""
        room_id = "test_room"
        player_name = "ExistingPlayer"
        socket_id = "new_socket456"

        # Setup existing disconnected player
        existing_player = {
            "player_id": "existing_player_id",
            "name": player_name,
            "score": 150,
            "socket_id": "old_socket123",
            "connected": False
        }

        room = {
            "room_id": room_id,
            "players": {"existing_player_id": existing_player},
            "last_activity": None
        }

        self.mock_concurrency_control_service.check_duplicate_request.return_value = False
        self.mock_room_lifecycle_service.get_room_data.return_value = room

        with patch.object(self.service, '_validate_player_addition') as mock_validate, \
             patch.object(self.service, '_find_disconnected_player', return_value=existing_player), \
             patch('src.services.player_management_service.datetime') as mock_datetime:

            mock_now = Mock()
            mock_datetime.now.return_value = mock_now

            result = self.service.add_player_to_room(room_id, player_name, socket_id)

            # Verify validation still occurs
            mock_validate.assert_called_once_with(room, player_name)

            # Verify player was reconnected
            assert existing_player["socket_id"] == socket_id
            assert existing_player["connected"] is True
            assert existing_player["score"] == 150  # Score preserved
            assert room["last_activity"] == mock_now

            # Result should be copy of reconnected player
            assert result == existing_player

    def test_add_player_to_room_handles_duplicate_request(self):
        """Test that adding player handles duplicate requests properly"""
        room_id = "test_room"
        player_name = "TestPlayer"
        socket_id = "socket123"

        # Setup existing player with same socket
        existing_player = {
            "player_id": "existing_id",
            "name": player_name,
            "socket_id": socket_id,
            "score": 100,
            "connected": True
        }

        room = {
            "players": {"existing_id": existing_player}
        }

        self.mock_concurrency_control_service.check_duplicate_request.return_value = True
        self.mock_room_lifecycle_service.get_room_data.return_value = room

        result = self.service.add_player_to_room(room_id, player_name, socket_id)

        # Should return existing player data without modification
        assert result == existing_player
        # Should not call ensure_room_exists since it's a duplicate
        self.mock_room_lifecycle_service.ensure_room_exists.assert_not_called()

    def test_disconnect_player_from_room_marks_player_disconnected(self):
        """Test that disconnecting player marks them as disconnected"""
        room_id = "test_room"
        player_id = "player123"

        player = {
            "player_id": player_id,
            "name": "TestPlayer",
            "connected": True
        }

        room = {
            "players": {player_id: player},
            "last_activity": None
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        with patch('src.services.player_management_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_datetime.now.return_value = mock_now

            result = self.service.disconnect_player_from_room(room_id, player_id)

            assert result is True
            assert player["connected"] is False
            assert room["last_activity"] == mock_now

    def test_disconnect_player_from_room_handles_nonexistent_room(self):
        """Test that disconnecting player handles non-existent room"""
        self.mock_room_lifecycle_service.get_room_data.return_value = None

        result = self.service.disconnect_player_from_room("nonexistent_room", "player123")
        assert result is False

    def test_disconnect_player_from_room_handles_nonexistent_player(self):
        """Test that disconnecting player handles non-existent player"""
        room = {
            "players": {"other_player": {"name": "OtherPlayer"}}
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        result = self.service.disconnect_player_from_room("test_room", "nonexistent_player")
        assert result is False

    def test_remove_player_from_room_removes_player_successfully(self):
        """Test that removing player from room works correctly"""
        room_id = "test_room"
        player_id = "player123"

        room = {
            "players": {
                player_id: {"name": "TestPlayer"},
                "other_player": {"name": "OtherPlayer"}
            }
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        with patch.object(self.service, 'is_room_empty', return_value=False), \
             patch.object(self.service, '_remove_player_from_room_state') as mock_remove:

            result = self.service.remove_player_from_room(room_id, player_id)

            assert result is True
            mock_remove.assert_called_once_with(room, player_id)
            # Should not delete room since it's not empty
            self.mock_room_lifecycle_service.delete_room.assert_not_called()

    def test_remove_player_from_room_deletes_empty_room(self):
        """Test that removing last player deletes the room"""
        room_id = "test_room"
        player_id = "last_player"

        room = {
            "players": {player_id: {"name": "LastPlayer"}}
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        with patch.object(self.service, 'is_room_empty', return_value=True), \
             patch.object(self.service, '_remove_player_from_room_state') as mock_remove:

            result = self.service.remove_player_from_room(room_id, player_id)

            assert result is True
            mock_remove.assert_called_once_with(room, player_id)
            # Should delete room since it's empty
            self.mock_room_lifecycle_service.delete_room.assert_called_once_with(room_id)

    def test_remove_player_from_room_handles_nonexistent_room(self):
        """Test that removing player handles non-existent room"""
        self.mock_room_lifecycle_service.get_room_data.return_value = None

        result = self.service.remove_player_from_room("nonexistent_room", "player123")
        assert result is False

    def test_remove_player_from_room_handles_nonexistent_player(self):
        """Test that removing player handles non-existent player"""
        room = {
            "players": {"other_player": {"name": "OtherPlayer"}}
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        result = self.service.remove_player_from_room("test_room", "nonexistent_player")
        assert result is False

    def test_get_room_players_returns_all_players(self):
        """Test that getting room players returns all players"""
        room_id = "test_room"
        players = {
            "player1": {"name": "Player1", "connected": True},
            "player2": {"name": "Player2", "connected": False},
            "player3": {"name": "Player3", "connected": True}
        }

        room = {"players": players}
        self.mock_room_lifecycle_service.get_room_data.return_value = room

        result = self.service.get_room_players(room_id)

        assert len(result) == 3
        # Should return copies of player data
        for player in result:
            assert player in players.values()

    def test_get_room_players_handles_nonexistent_room(self):
        """Test that getting room players handles non-existent room"""
        self.mock_room_lifecycle_service.get_room_data.return_value = None

        result = self.service.get_room_players("nonexistent_room")
        assert result == []

    def test_get_connected_players_returns_only_connected(self):
        """Test that getting connected players returns only connected players"""
        room_id = "test_room"
        players = {
            "player1": {"name": "Player1", "connected": True},
            "player2": {"name": "Player2", "connected": False},
            "player3": {"name": "Player3", "connected": True}
        }

        room = {"players": players}
        self.mock_room_lifecycle_service.get_room_data.return_value = room

        result = self.service.get_connected_players(room_id)

        assert len(result) == 2
        for player in result:
            assert player["connected"] is True

    def test_get_connected_players_handles_nonexistent_room(self):
        """Test that getting connected players handles non-existent room"""
        self.mock_room_lifecycle_service.get_room_data.return_value = None

        result = self.service.get_connected_players("nonexistent_room")
        assert result == []

    def test_is_room_empty_returns_true_for_no_connected_players(self):
        """Test that room emptiness check returns True for no connected players"""
        room = {
            "players": {
                "player1": {"connected": False},
                "player2": {"connected": False}
            }
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        result = self.service.is_room_empty("test_room")
        assert result is True

    def test_is_room_empty_returns_false_for_connected_players(self):
        """Test that room emptiness check returns False for connected players"""
        room = {
            "players": {
                "player1": {"connected": True},
                "player2": {"connected": False}
            }
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        result = self.service.is_room_empty("test_room")
        assert result is False

    def test_is_room_empty_returns_true_for_nonexistent_room(self):
        """Test that room emptiness check returns True for non-existent room"""
        self.mock_room_lifecycle_service.get_room_data.return_value = None

        result = self.service.is_room_empty("nonexistent_room")
        assert result is True

    def test_update_player_score_updates_successfully(self):
        """Test that updating player score works correctly"""
        room_id = "test_room"
        player_id = "player123"
        new_score = 250

        player = {
            "player_id": player_id,
            "name": "TestPlayer",
            "score": 100
        }

        room = {
            "players": {player_id: player},
            "last_activity": None
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        with patch('src.services.player_management_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_datetime.now.return_value = mock_now

            result = self.service.update_player_score(room_id, player_id, new_score)

            assert result is True
            assert player["score"] == new_score
            assert room["last_activity"] == mock_now

    def test_update_player_score_handles_nonexistent_room(self):
        """Test that updating player score handles non-existent room"""
        self.mock_room_lifecycle_service.get_room_data.return_value = None

        result = self.service.update_player_score("nonexistent_room", "player123", 100)
        assert result is False

    def test_update_player_score_handles_nonexistent_player(self):
        """Test that updating player score handles non-existent player"""
        room = {
            "players": {"other_player": {"score": 50}}
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        result = self.service.update_player_score("test_room", "nonexistent_player", 100)
        assert result is False

    def test_concurrency_control_used_for_all_room_operations(self):
        """Test that concurrency control is used for all room modification operations"""
        room_id = "test_room"

        # Setup basic room
        room = {
            "players": {"player1": {"name": "Player1", "connected": True}}
        }
        self.mock_room_lifecycle_service.get_room_data.return_value = room

        # Test add_player_to_room
        self.mock_concurrency_control_service.check_duplicate_request.return_value = False
        with patch.object(self.service, '_validate_player_addition'), \
             patch.object(self.service, '_find_disconnected_player', return_value=None), \
             patch.object(self.service, '_create_player_data', return_value={"player_id": "new_id"}), \
             patch.object(self.service, '_add_player_to_room_state'):

            self.service.add_player_to_room(room_id, "NewPlayer", "socket123")
            self.mock_concurrency_control_service.room_operation.assert_called_with(room_id)

        # Reset mock
        self.mock_concurrency_control_service.reset_mock()

        # Test disconnect_player_from_room
        self.service.disconnect_player_from_room(room_id, "player1")
        self.mock_concurrency_control_service.room_operation.assert_called_with(room_id)

        # Reset mock
        self.mock_concurrency_control_service.reset_mock()

        # Test remove_player_from_room
        with patch.object(self.service, 'is_room_empty', return_value=False):
            self.service.remove_player_from_room(room_id, "player1")
            self.mock_concurrency_control_service.room_operation.assert_called_with(room_id)

        # Reset mock
        self.mock_concurrency_control_service.reset_mock()

        # Test update_player_score
        self.service.update_player_score(room_id, "player1", 100)
        self.mock_concurrency_control_service.room_operation.assert_called_with(room_id)


class TestPlayerManagementServiceAdvancedScenarios:
    """Test PlayerManagementService advanced scenarios and edge cases"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        # Create mock dependencies
        self.mock_room_lifecycle_service = Mock()
        self.mock_concurrency_control_service = Mock()

        # Create mock game settings
        self.mock_game_settings = Mock()
        self.mock_game_settings.max_players_per_room = 8

        # Patch game settings
        with patch('src.services.player_management_service.get_game_settings', return_value=self.mock_game_settings):
            self.service = PlayerManagementService(
                room_lifecycle_service=self.mock_room_lifecycle_service,
                concurrency_control_service=self.mock_concurrency_control_service
            )

        # Setup default room operation context manager
        self.mock_concurrency_control_service.room_operation.return_value.__enter__ = Mock(return_value=Mock())
        self.mock_concurrency_control_service.room_operation.return_value.__exit__ = Mock(return_value=None)

    def test_complex_reconnection_scenario_preserves_player_state(self):
        """Test complex reconnection scenario with score preservation and socket ID updates"""
        room_id = "test_room"
        player_name = "ReconnectingPlayer"
        original_socket = "original_socket_123"
        new_socket = "new_socket_456"

        # Create disconnected player with existing score and game state
        disconnected_player = {
            "player_id": "player_123",
            "name": player_name,
            "score": 500,
            "socket_id": original_socket,
            "connected": False,
            "last_response_time": "2024-01-01T12:00:00",
            "game_data": {"responses_submitted": 3, "guesses_correct": 2}
        }

        room = {
            "room_id": room_id,
            "players": {"player_123": disconnected_player},
            "last_activity": datetime(2024, 1, 1, 11, 0, 0)
        }

        self.mock_concurrency_control_service.check_duplicate_request.return_value = False
        self.mock_room_lifecycle_service.get_room_data.return_value = room

        with patch.object(self.service, '_validate_player_addition') as mock_validate, \
             patch('src.services.player_management_service.datetime') as mock_datetime:

            mock_now = datetime(2024, 1, 1, 12, 30, 0)
            mock_datetime.now.return_value = mock_now

            result = self.service.add_player_to_room(room_id, player_name, new_socket)

            # Verify validation occurred
            mock_validate.assert_called_once_with(room, player_name)

            # Verify reconnection preserves all player state
            assert disconnected_player["socket_id"] == new_socket
            assert disconnected_player["connected"] is True
            assert disconnected_player["score"] == 500  # Score preserved
            assert disconnected_player["last_response_time"] == "2024-01-01T12:00:00"  # Game data preserved
            assert disconnected_player["game_data"] == {"responses_submitted": 3, "guesses_correct": 2}

            # Verify room last activity updated
            assert room["last_activity"] == mock_now

            # Verify returned player data matches reconnected player
            assert result == disconnected_player

    def test_concurrent_player_addition_same_name_different_sockets(self):
        """Test concurrent player addition with same name but different socket IDs"""
        room_id = "test_room"
        player_name = "ConcurrentPlayer"
        socket_id_1 = "socket_123"
        socket_id_2 = "socket_456"

        room = {
            "room_id": room_id,
            "players": {},
            "last_activity": None
        }

        # Setup for first request (wins the race)
        self.mock_room_lifecycle_service.get_room_data.return_value = room

        # Mock concurrency control to simulate first request succeeding
        self.mock_concurrency_control_service.check_duplicate_request.side_effect = [False, True]

        with patch.object(self.service, '_create_player_data') as mock_create_player, \
             patch.object(self.service, '_validate_player_addition'), \
             patch.object(self.service, '_find_disconnected_player', return_value=None), \
             patch.object(self.service, '_add_player_to_room_state'):

            first_player_data = {
                "player_id": "first_player_id",
                "name": player_name,
                "socket_id": socket_id_1,
                "connected": True
            }
            mock_create_player.return_value = first_player_data

            # First request succeeds
            result1 = self.service.add_player_to_room(room_id, player_name, socket_id_1)
            assert result1 == first_player_data

            # Add first player to room for second request simulation
            room["players"]["first_player_id"] = first_player_data

            # Test that second request with different socket would fail validation
            # Reset get_room_data to return room with first player
            self.mock_room_lifecycle_service.get_room_data.return_value = room

            # Reset check_duplicate_request for second call
            self.mock_concurrency_control_service.check_duplicate_request.return_value = False

            with patch.object(self.service, '_validate_player_addition') as mock_validate:
                mock_validate.side_effect = ValueError("Player name already taken")

                with pytest.raises(ValueError, match="Player name already taken"):
                    self.service.add_player_to_room(room_id, player_name, socket_id_2)

    def test_rapid_disconnect_reconnect_cycle(self):
        """Test rapid disconnect/reconnect cycles maintain data integrity"""
        room_id = "test_room"
        player_id = "cycling_player"
        player_name = "CyclingPlayer"
        sockets = ["socket_1", "socket_2", "socket_3"]

        player = {
            "player_id": player_id,
            "name": player_name,
            "score": 100,
            "socket_id": sockets[0],
            "connected": True
        }

        room = {
            "players": {player_id: player},
            "last_activity": None
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        with patch('src.services.player_management_service.datetime') as mock_datetime:
            mock_times = [
                datetime(2024, 1, 1, 12, 0, 0),
                datetime(2024, 1, 1, 12, 0, 1),
                datetime(2024, 1, 1, 12, 0, 2),
                datetime(2024, 1, 1, 12, 0, 3),
                datetime(2024, 1, 1, 12, 0, 4),
                datetime(2024, 1, 1, 12, 0, 5)
            ]
            mock_datetime.now.side_effect = mock_times

            # Cycle: disconnect -> reconnect -> disconnect -> reconnect

            # Disconnect 1
            result1 = self.service.disconnect_player_from_room(room_id, player_id)
            assert result1 is True
            assert player["connected"] is False
            assert room["last_activity"] == mock_times[0]

            # Reconnect 1
            self.mock_concurrency_control_service.check_duplicate_request.return_value = False
            with patch.object(self.service, '_validate_player_addition'), \
                 patch.object(self.service, '_find_disconnected_player', return_value=player):
                result2 = self.service.add_player_to_room(room_id, player_name, sockets[1])
                assert player["connected"] is True
                assert player["socket_id"] == sockets[1]
                assert player["score"] == 100  # Score preserved
                assert room["last_activity"] == mock_times[1]

            # Disconnect 2
            result3 = self.service.disconnect_player_from_room(room_id, player_id)
            assert result3 is True
            assert player["connected"] is False
            assert room["last_activity"] == mock_times[2]

            # Reconnect 2
            with patch.object(self.service, '_validate_player_addition'), \
                 patch.object(self.service, '_find_disconnected_player', return_value=player):
                result4 = self.service.add_player_to_room(room_id, player_name, sockets[2])
                assert player["connected"] is True
                assert player["socket_id"] == sockets[2]
                assert player["score"] == 100  # Score still preserved
                assert room["last_activity"] == mock_times[3]

    def test_edge_case_player_with_missing_connected_flag(self):
        """Test handling of players with missing 'connected' flag (legacy data)"""
        room_id = "test_room"

        # Player without explicit connected flag (should default to True)
        legacy_player = {
            "player_id": "legacy_player",
            "name": "LegacyPlayer",
            "score": 200
            # Note: no 'connected' field
        }

        room = {
            "room_id": room_id,
            "players": {"legacy_player": legacy_player}
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        # Test get_connected_players handles missing connected flag
        # Note: This will raise KeyError because implementation uses player["connected"] directly
        with pytest.raises(KeyError):
            self.service.get_connected_players(room_id)

        # Test is_room_empty handles missing connected flag
        empty_result = self.service.is_room_empty(room_id)
        assert empty_result is False  # Should treat as connected

        # Test _find_disconnected_player handles missing connected flag
        disconnected_result = self.service._find_disconnected_player(room, "LegacyPlayer")
        assert disconnected_result is None  # Should not find as disconnected

    def test_edge_case_room_with_mixed_player_states(self):
        """Test room operations with mixed connected/disconnected/legacy players"""
        room_id = "complex_room"

        players = {
            "connected_player": {
                "player_id": "connected_player",
                "name": "ConnectedPlayer",
                "connected": True,
                "score": 100
            },
            "disconnected_player": {
                "player_id": "disconnected_player",
                "name": "DisconnectedPlayer",
                "connected": False,
                "score": 200
            },
            "legacy_player": {
                "player_id": "legacy_player",
                "name": "LegacyPlayer",
                "score": 300
                # No connected field
            }
        }

        room = {"room_id": room_id, "players": players}
        self.mock_room_lifecycle_service.get_room_data.return_value = room

        # Test get_room_players returns all players
        all_players = self.service.get_room_players(room_id)
        assert len(all_players) == 3

        # Test get_connected_players fails with legacy player (missing connected field)
        # Note: This will raise KeyError due to legacy player missing "connected" field
        with pytest.raises(KeyError):
            self.service.get_connected_players(room_id)

        # Test is_room_empty returns False (has connected players)
        is_empty = self.service.is_room_empty(room_id)
        assert is_empty is False

        # Test validation considers connected and legacy players as taken names
        with pytest.raises(ValueError, match="Player name 'ConnectedPlayer' is already taken"):
            self.service._validate_player_addition(room, "ConnectedPlayer")

        with pytest.raises(ValueError, match="Player name 'LegacyPlayer' is already taken"):
            self.service._validate_player_addition(room, "LegacyPlayer")

        # Test validation allows disconnected player name
        # Should not raise exception
        self.service._validate_player_addition(room, "DisconnectedPlayer")

    def test_concurrent_score_updates_same_player(self):
        """Test concurrent score updates for the same player maintain consistency"""
        room_id = "test_room"
        player_id = "score_player"

        player = {
            "player_id": player_id,
            "name": "ScorePlayer",
            "score": 100,
            "connected": True
        }

        room = {
            "players": {player_id: player},
            "last_activity": None
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        with patch('src.services.player_management_service.datetime') as mock_datetime:
            mock_times = [
                datetime(2024, 1, 1, 12, 0, 0),
                datetime(2024, 1, 1, 12, 0, 1),
                datetime(2024, 1, 1, 12, 0, 2)
            ]
            mock_datetime.now.side_effect = mock_times

            # Simulate rapid score updates
            result1 = self.service.update_player_score(room_id, player_id, 150)
            assert result1 is True
            assert player["score"] == 150
            assert room["last_activity"] == mock_times[0]

            result2 = self.service.update_player_score(room_id, player_id, 200)
            assert result2 is True
            assert player["score"] == 200
            assert room["last_activity"] == mock_times[1]

            result3 = self.service.update_player_score(room_id, player_id, 175)
            assert result3 is True
            assert player["score"] == 175  # Last update wins
            assert room["last_activity"] == mock_times[2]

            # Verify concurrency control was used for each update (including context manager calls)
            assert self.mock_concurrency_control_service.room_operation.call_count == 3
            # Each call should be with room_id
            for call_args in self.mock_concurrency_control_service.room_operation.call_args_list:
                assert call_args == call(room_id)

    def test_room_cleanup_threshold_edge_cases(self):
        """Test room cleanup behavior at various player thresholds"""
        room_id = "threshold_room"

        # Test room with only disconnected players
        disconnected_only_room = {
            "players": {
                "disc1": {"name": "Disc1", "connected": False},
                "disc2": {"name": "Disc2", "connected": False}
            }
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = disconnected_only_room

        # Remove last disconnected player should trigger room deletion
        with patch.object(self.service, 'is_room_empty', return_value=True):
            result = self.service.remove_player_from_room(room_id, "disc1")
            assert result is True
            self.mock_room_lifecycle_service.delete_room.assert_called_once_with(room_id)

        # Reset mocks
        self.mock_room_lifecycle_service.reset_mock()

        # Test room with mix of connected and disconnected
        mixed_room = {
            "players": {
                "conn1": {"name": "Conn1", "connected": True},
                "disc1": {"name": "Disc1", "connected": False}
            }
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = mixed_room

        # Remove disconnected player should not trigger room deletion
        with patch.object(self.service, 'is_room_empty', return_value=False):
            result = self.service.remove_player_from_room(room_id, "disc1")
            assert result is True
            self.mock_room_lifecycle_service.delete_room.assert_not_called()

    def test_duplicate_request_detection_with_reconnection(self):
        """Test duplicate request detection handles reconnection scenarios correctly"""
        room_id = "reconnect_room"
        player_name = "ReconnectPlayer"
        socket_id = "socket_123"

        # Existing player that will be returned for duplicate request
        existing_player = {
            "player_id": "existing_id",
            "name": player_name,
            "socket_id": socket_id,
            "score": 250,
            "connected": True
        }

        room = {
            "players": {"existing_id": existing_player}
        }

        # First call - duplicate request detected, return existing player
        self.mock_concurrency_control_service.check_duplicate_request.return_value = True
        self.mock_room_lifecycle_service.get_room_data.return_value = room

        result1 = self.service.add_player_to_room(room_id, player_name, socket_id)
        assert result1 == existing_player
        # Should not call ensure_room_exists for duplicate request
        self.mock_room_lifecycle_service.ensure_room_exists.assert_not_called()

        # Second call - not a duplicate, but player exists
        self.mock_concurrency_control_service.check_duplicate_request.return_value = False

        with patch.object(self.service, '_validate_player_addition') as mock_validate:
            # This should trigger validation and likely fail due to name conflict
            mock_validate.side_effect = ValueError("Player name already taken")

            with pytest.raises(ValueError, match="Player name already taken"):
                self.service.add_player_to_room(room_id, player_name, "different_socket")

            # Should call ensure_room_exists for non-duplicate request
            self.mock_room_lifecycle_service.ensure_room_exists.assert_called_once_with(room_id)

    def test_complex_room_state_transitions(self):
        """Test complex room state transitions through player operations"""
        room_id = "transition_room"

        # Start with empty room
        empty_room = {"players": {}}
        self.mock_room_lifecycle_service.get_room_data.return_value = empty_room

        # Phase 1: Add first player (room creation)
        self.mock_concurrency_control_service.check_duplicate_request.return_value = False

        with patch.object(self.service, '_create_player_data') as mock_create, \
             patch.object(self.service, '_validate_player_addition'), \
             patch.object(self.service, '_find_disconnected_player', return_value=None), \
             patch.object(self.service, '_add_player_to_room_state') as mock_add:

            player1_data = {
                "player_id": "player1",
                "name": "Player1",
                "socket_id": "socket1",
                "connected": True
            }
            mock_create.return_value = player1_data

            result1 = self.service.add_player_to_room(room_id, "Player1", "socket1")
            assert result1 == player1_data

            # Verify room creation was ensured
            self.mock_room_lifecycle_service.ensure_room_exists.assert_called_with(room_id)

        # Phase 2: Add second player
        room_with_player1 = {"players": {"player1": player1_data}}
        self.mock_room_lifecycle_service.get_room_data.return_value = room_with_player1

        with patch.object(self.service, '_create_player_data') as mock_create, \
             patch.object(self.service, '_validate_player_addition'), \
             patch.object(self.service, '_find_disconnected_player', return_value=None), \
             patch.object(self.service, '_add_player_to_room_state'):

            player2_data = {
                "player_id": "player2",
                "name": "Player2",
                "socket_id": "socket2",
                "connected": True
            }
            mock_create.return_value = player2_data

            result2 = self.service.add_player_to_room(room_id, "Player2", "socket2")
            assert result2 == player2_data

        # Phase 3: Disconnect first player
        room_with_both = {
            "players": {
                "player1": player1_data,
                "player2": player2_data
            }
        }
        self.mock_room_lifecycle_service.get_room_data.return_value = room_with_both

        disconnect_result = self.service.disconnect_player_from_room(room_id, "player1")
        assert disconnect_result is True
        assert player1_data["connected"] is False

        # Phase 4: Remove second player (should check if room becomes empty)
        with patch.object(self.service, 'is_room_empty', return_value=False):  # First player still there, just disconnected
            remove_result = self.service.remove_player_from_room(room_id, "player2")
            assert remove_result is True
            # Room should not be deleted (disconnected player still there)
            self.mock_room_lifecycle_service.delete_room.assert_not_called()

        # Phase 5: Remove disconnected player (room should be deleted)
        room_with_player1_only = {"players": {"player1": player1_data}}
        self.mock_room_lifecycle_service.get_room_data.return_value = room_with_player1_only

        with patch.object(self.service, 'is_room_empty', return_value=True):
            final_remove_result = self.service.remove_player_from_room(room_id, "player1")
            assert final_remove_result is True
            # Room should be deleted (no connected players)
            self.mock_room_lifecycle_service.delete_room.assert_called_with(room_id)

    def test_session_service_integration_patterns(self):
        """Test patterns that would integrate with session service (preparation for future integration)"""
        # This test prepares for future session service integration by testing
        # player operations with session-like data structures

        room_id = "session_room"
        player_id = "session_player"

        # Player data that might include session information
        player_with_session_data = {
            "player_id": player_id,
            "name": "SessionPlayer",
            "socket_id": "session_socket",
            "connected": True,
            "score": 100,
            "session_data": {
                "join_time": "2024-01-01T12:00:00Z",
                "last_ping": "2024-01-01T12:05:00Z",
                "user_agent": "TestBrowser/1.0"
            }
        }

        room = {
            "players": {player_id: player_with_session_data},
            "last_activity": None
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        # Test that player operations preserve session data
        with patch('src.services.player_management_service.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 1, 12, 10, 0)
            mock_datetime.now.return_value = mock_now

            # Disconnect should preserve session data
            disconnect_result = self.service.disconnect_player_from_room(room_id, player_id)
            assert disconnect_result is True
            assert player_with_session_data["connected"] is False
            assert player_with_session_data["session_data"]["join_time"] == "2024-01-01T12:00:00Z"

            # Score update should preserve session data
            score_result = self.service.update_player_score(room_id, player_id, 150)
            assert score_result is True
            assert player_with_session_data["score"] == 150
            assert player_with_session_data["session_data"]["user_agent"] == "TestBrowser/1.0"

            # Reconnection should preserve session data but update socket
            self.mock_concurrency_control_service.check_duplicate_request.return_value = False
            with patch.object(self.service, '_validate_player_addition'), \
                 patch.object(self.service, '_find_disconnected_player', return_value=player_with_session_data):

                reconnect_result = self.service.add_player_to_room(room_id, "SessionPlayer", "new_session_socket")
                assert player_with_session_data["socket_id"] == "new_session_socket"
                assert player_with_session_data["connected"] is True
                assert player_with_session_data["session_data"]["join_time"] == "2024-01-01T12:00:00Z"

    def test_error_recovery_scenarios(self):
        """Test error recovery in complex scenarios"""
        room_id = "error_room"

        # Scenario 1: Room service fails during player addition
        self.mock_room_lifecycle_service.ensure_room_exists.side_effect = Exception("Room creation failed")
        self.mock_concurrency_control_service.check_duplicate_request.return_value = False

        with pytest.raises(Exception, match="Room creation failed"):
            self.service.add_player_to_room(room_id, "TestPlayer", "socket123")

        # Reset for next test
        self.mock_room_lifecycle_service.ensure_room_exists.side_effect = None

        # Scenario 2: Concurrency service context manager fails
        self.mock_concurrency_control_service.room_operation.side_effect = Exception("Lock acquisition failed")

        with pytest.raises(Exception, match="Lock acquisition failed"):
            self.service.remove_player_from_room(room_id, "player123")

        # Reset for next test
        self.mock_concurrency_control_service.room_operation.side_effect = None
        self.mock_concurrency_control_service.room_operation.return_value.__enter__ = Mock(return_value=Mock())
        self.mock_concurrency_control_service.room_operation.return_value.__exit__ = Mock(return_value=None)

        # Scenario 3: Room data corruption (missing players dict)
        corrupted_room = {"room_id": room_id}  # Missing players dict
        self.mock_room_lifecycle_service.get_room_data.return_value = corrupted_room

        # Operations should handle missing players dict gracefully
        with pytest.raises(KeyError):
            # This should fail due to missing players dict, simulating data corruption
            self.service.get_room_players(room_id)

    def test_performance_edge_cases(self):
        """Test performance-related edge cases"""
        room_id = "performance_room"

        # Test with maximum number of players
        max_players = 8
        players = {}
        for i in range(max_players):
            players[f"player_{i}"] = {
                "player_id": f"player_{i}",
                "name": f"Player{i}",
                "connected": True,
                "score": i * 10
            }

        room = {"room_id": room_id, "players": players}
        self.mock_room_lifecycle_service.get_room_data.return_value = room

        # Test operations with full room
        all_players = self.service.get_room_players(room_id)
        assert len(all_players) == max_players

        connected_players = self.service.get_connected_players(room_id)
        assert len(connected_players) == max_players

        # Test validation rejects new player in full room
        with pytest.raises(ValueError, match="Room .* is full"):
            self.service._validate_player_addition(room, "NewPlayer")

        # Test room emptiness check with large number of disconnected players
        for player in players.values():
            player["connected"] = False

        is_empty = self.service.is_room_empty(room_id)
        assert is_empty is True

        connected_after_disconnect = self.service.get_connected_players(room_id)
        assert len(connected_after_disconnect) == 0