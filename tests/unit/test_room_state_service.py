"""
Room State Service Unit Tests

Tests room state retrieval, consistency validation, performance optimization, and caching behavior.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import threading

from src.services.room_state_service import RoomStateService


class TestRoomStateServiceBasicOperations:
    """Test basic room state operations"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.mock_room_lifecycle_service = Mock()
        self.mock_concurrency_control_service = Mock()

        # Setup mock context manager for concurrency control
        self.mock_context = Mock()
        self.mock_concurrency_control_service.room_operation.return_value = self.mock_context
        self.mock_context.__enter__ = Mock(return_value=self.mock_context)
        self.mock_context.__exit__ = Mock(return_value=None)

        self.service = RoomStateService(
            room_lifecycle_service=self.mock_room_lifecycle_service,
            concurrency_control_service=self.mock_concurrency_control_service
        )

    def test_initialization(self):
        """Test service initialization"""
        assert self.service.room_lifecycle_service == self.mock_room_lifecycle_service
        assert self.service.concurrency_control_service == self.mock_concurrency_control_service

    def test_get_room_state_existing_room(self):
        """Test getting state for existing room"""
        room_id = "test-room"
        mock_room_data = {
            "room_id": room_id,
            "players": {"player1": {"player_id": "player1", "name": "Test Player"}},
            "game_state": {
                "phase": "waiting",
                "current_prompt": None,
                "responses": [],
                "guesses": {},
                "round_number": 0
            },
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = mock_room_data

        result = self.service.get_room_state(room_id)

        assert result is not None
        assert result["room_id"] == room_id
        assert result["players"] == mock_room_data["players"]
        assert result["game_state"] == mock_room_data["game_state"]
        # Verify it returns a copy, not the original
        assert result is not mock_room_data

    def test_get_room_state_non_existent_room(self):
        """Test getting state for non-existent room"""
        room_id = "non-existent"

        self.mock_room_lifecycle_service.get_room_data.return_value = None

        result = self.service.get_room_state(room_id)

        assert result is None

    def test_update_room_activity_success(self):
        """Test successful room activity update"""
        room_id = "test-room"
        mock_room_data = {
            "room_id": room_id,
            "last_activity": datetime.now() - timedelta(minutes=10)
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = mock_room_data

        with patch('src.services.room_state_service.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now

            result = self.service.update_room_activity(room_id)

            assert result is True
            assert mock_room_data["last_activity"] == mock_now

    def test_update_room_activity_non_existent_room(self):
        """Test room activity update for non-existent room"""
        room_id = "non-existent"

        self.mock_room_lifecycle_service.get_room_data.return_value = None

        result = self.service.update_room_activity(room_id)

        assert result is False


class TestRoomStateServiceConsistencyValidation:
    """Test room state consistency validation"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.mock_room_lifecycle_service = Mock()
        self.mock_concurrency_control_service = Mock()

        self.service = RoomStateService(
            room_lifecycle_service=self.mock_room_lifecycle_service,
            concurrency_control_service=self.mock_concurrency_control_service
        )

    def create_valid_room_data(self, room_id="test-room"):
        """Helper to create valid room data"""
        return {
            "room_id": room_id,
            "players": {
                "player1": {"player_id": "player1", "name": "Test Player"}
            },
            "game_state": {
                "phase": "waiting",
                "current_prompt": None,
                "responses": [],
                "guesses": {},
                "round_number": 0
            },
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }

    def test_validate_room_state_consistency_valid_room(self):
        """Test validation passes for valid room"""
        room_id = "valid-room"
        valid_room = self.create_valid_room_data(room_id)

        self.mock_room_lifecycle_service.get_room_data.return_value = valid_room

        result = self.service.validate_room_state_consistency(room_id)

        assert result is True

    def test_validate_room_state_consistency_non_existent_room(self):
        """Test validation fails for non-existent room"""
        room_id = "non-existent"

        self.mock_room_lifecycle_service.get_room_data.return_value = None

        result = self.service.validate_room_state_consistency(room_id)

        assert result is False

    def test_validate_room_state_consistency_missing_required_field(self):
        """Test validation fails when required field is missing"""
        room_id = "invalid-room"
        invalid_room = self.create_valid_room_data(room_id)
        del invalid_room["players"]  # Remove required field

        self.mock_room_lifecycle_service.get_room_data.return_value = invalid_room

        result = self.service.validate_room_state_consistency(room_id)

        assert result is False

    def test_validate_room_state_consistency_missing_game_state_field(self):
        """Test validation fails when game state field is missing"""
        room_id = "invalid-room"
        invalid_room = self.create_valid_room_data(room_id)
        del invalid_room["game_state"]["phase"]  # Remove required game state field

        self.mock_room_lifecycle_service.get_room_data.return_value = invalid_room

        result = self.service.validate_room_state_consistency(room_id)

        assert result is False

    def test_validate_room_state_consistency_invalid_player_data(self):
        """Test validation fails for invalid player data"""
        room_id = "invalid-room"
        invalid_room = self.create_valid_room_data(room_id)
        invalid_room["players"]["player1"] = "not_a_dict"  # Invalid player data

        self.mock_room_lifecycle_service.get_room_data.return_value = invalid_room

        result = self.service.validate_room_state_consistency(room_id)

        assert result is False

    def test_validate_room_state_consistency_mismatched_player_id(self):
        """Test validation fails for mismatched player ID"""
        room_id = "invalid-room"
        invalid_room = self.create_valid_room_data(room_id)
        invalid_room["players"]["player1"]["player_id"] = "different_id"  # Mismatched ID

        self.mock_room_lifecycle_service.get_room_data.return_value = invalid_room

        result = self.service.validate_room_state_consistency(room_id)

        assert result is False

    def test_validate_room_state_consistency_exception_handling(self):
        """Test validation handles exceptions gracefully"""
        room_id = "exception-room"
        # Create room data that will cause an exception during iteration
        malformed_room = {
            "room_id": room_id,
            "players": "not_a_dict",  # This will cause exception when iterating
            "game_state": {
                "phase": "waiting",
                "current_prompt": None,
                "responses": [],
                "guesses": {},
                "round_number": 0
            },
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = malformed_room

        result = self.service.validate_room_state_consistency(room_id)

        assert result is False

    def test_validate_room_consistency_success(self):
        """Test validate_room_consistency doesn't raise for valid room"""
        room_id = "valid-room"
        valid_room = self.create_valid_room_data(room_id)

        self.mock_room_lifecycle_service.get_room_data.return_value = valid_room

        # Should not raise an exception
        self.service.validate_room_consistency(room_id)

    def test_validate_room_consistency_raises_for_invalid(self):
        """Test validate_room_consistency raises ValueError for invalid room"""
        room_id = "invalid-room"

        self.mock_room_lifecycle_service.get_room_data.return_value = None

        with pytest.raises(ValueError, match=f"Room {room_id} is in an inconsistent state"):
            self.service.validate_room_consistency(room_id)


class TestRoomStateServiceGameStateTransitions:
    """Test game state transition validation"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.mock_room_lifecycle_service = Mock()
        self.mock_concurrency_control_service = Mock()

        self.service = RoomStateService(
            room_lifecycle_service=self.mock_room_lifecycle_service,
            concurrency_control_service=self.mock_concurrency_control_service
        )

    def create_room_with_phase(self, phase):
        """Helper to create room with specific phase"""
        return {
            "room_id": "test-room",
            "players": {},
            "game_state": {
                "phase": phase,
                "current_prompt": None,
                "responses": [],
                "guesses": {},
                "round_number": 0
            },
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }

    def create_game_state_with_phase(self, phase):
        """Helper to create game state with specific phase"""
        return {
            "phase": phase,
            "current_prompt": None,
            "responses": [],
            "guesses": {},
            "round_number": 0
        }

    def test_validate_game_state_transition_valid_waiting_to_responding(self):
        """Test valid transition from waiting to responding"""
        room = self.create_room_with_phase("waiting")
        new_game_state = self.create_game_state_with_phase("responding")

        result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

        assert result is True

    def test_validate_game_state_transition_valid_responding_to_guessing(self):
        """Test valid transition from responding to guessing"""
        room = self.create_room_with_phase("responding")
        new_game_state = self.create_game_state_with_phase("guessing")

        result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

        assert result is True

    def test_validate_game_state_transition_valid_guessing_to_results(self):
        """Test valid transition from guessing to results"""
        room = self.create_room_with_phase("guessing")
        new_game_state = self.create_game_state_with_phase("results")

        result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

        assert result is True

    def test_validate_game_state_transition_valid_results_to_waiting(self):
        """Test valid transition from results to waiting"""
        room = self.create_room_with_phase("results")
        new_game_state = self.create_game_state_with_phase("waiting")

        result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

        assert result is True

    def test_validate_game_state_transition_invalid_waiting_to_results(self):
        """Test invalid transition from waiting to results"""
        room = self.create_room_with_phase("waiting")
        new_game_state = self.create_game_state_with_phase("results")

        with patch('src.services.room_state_service.logger') as mock_logger:
            result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

            assert result is False
            mock_logger.warning.assert_called()

    def test_validate_game_state_transition_invalid_responding_to_results(self):
        """Test invalid transition from responding to results"""
        room = self.create_room_with_phase("responding")
        new_game_state = self.create_game_state_with_phase("results")

        result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

        assert result is False

    def test_validate_game_state_transition_same_phase(self):
        """Test staying in same phase is valid"""
        room = self.create_room_with_phase("waiting")
        new_game_state = self.create_game_state_with_phase("waiting")

        result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

        assert result is True

    def test_validate_game_state_transition_missing_phase_field(self):
        """Test validation fails when phase field is missing"""
        room = self.create_room_with_phase("waiting")
        new_game_state = self.create_game_state_with_phase("responding")
        del new_game_state["phase"]

        with patch('src.services.room_state_service.logger') as mock_logger:
            result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

            assert result is False
            mock_logger.warning.assert_called()

    def test_validate_game_state_transition_missing_required_field(self):
        """Test validation fails when required field is missing"""
        room = self.create_room_with_phase("waiting")
        new_game_state = self.create_game_state_with_phase("responding")
        del new_game_state["responses"]

        with patch('src.services.room_state_service.logger') as mock_logger:
            result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

            assert result is False
            mock_logger.warning.assert_called()

    def test_validate_game_state_transition_exception_handling(self):
        """Test validation handles exceptions gracefully"""
        room = self.create_room_with_phase("waiting")
        # Create a malformed game state structure that will cause exception during field checking
        new_game_state = Mock()
        new_game_state.get.side_effect = [
            "responding",  # First call for phase succeeds
            Exception("Test exception")  # Second call for required fields check fails
        ]

        with patch('src.services.room_state_service.logger') as mock_logger:
            result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

            assert result is False
            mock_logger.error.assert_called()


class TestRoomStateServiceGameStateUpdates:
    """Test game state update operations"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.mock_room_lifecycle_service = Mock()
        self.mock_concurrency_control_service = Mock()

        # Setup mock context manager for concurrency control
        self.mock_context = Mock()
        self.mock_concurrency_control_service.room_operation.return_value = self.mock_context
        self.mock_context.__enter__ = Mock(return_value=self.mock_context)
        self.mock_context.__exit__ = Mock(return_value=None)

        self.service = RoomStateService(
            room_lifecycle_service=self.mock_room_lifecycle_service,
            concurrency_control_service=self.mock_concurrency_control_service
        )

    def create_valid_room_data(self, phase="waiting"):
        """Helper to create valid room data"""
        return {
            "room_id": "test-room",
            "players": {
                "player1": {"player_id": "player1", "name": "Test Player"}
            },
            "game_state": {
                "phase": phase,
                "current_prompt": None,
                "responses": [],
                "guesses": {},
                "round_number": 0
            },
            "created_at": datetime.now(),
            "last_activity": datetime.now() - timedelta(minutes=5)
        }

    def test_update_room_game_state(self):
        """Test updating room's game state"""
        room = self.create_valid_room_data()
        new_game_state = {
            "phase": "responding",
            "current_prompt": "Test prompt",
            "responses": [],
            "guesses": {},
            "round_number": 1
        }

        with patch('src.services.room_state_service.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now

            self.service.update_room_game_state(room, new_game_state)

            assert room["game_state"] == new_game_state
            assert room["last_activity"] == mock_now

    def test_update_game_state_success(self):
        """Test successful game state update"""
        room_id = "test-room"
        room = self.create_valid_room_data("waiting")
        new_game_state = {
            "phase": "responding",
            "current_prompt": "Test prompt",
            "responses": [],
            "guesses": {},
            "round_number": 1
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        # Mock validation methods to return True
        with patch.object(self.service, 'validate_game_state_transition', return_value=True), \
             patch.object(self.service, 'validate_room_state_consistency', return_value=True):

            result = self.service.update_game_state(room_id, new_game_state)

            assert result is True
            assert room["game_state"]["phase"] == "responding"

    def test_update_game_state_non_existent_room(self):
        """Test game state update for non-existent room"""
        room_id = "non-existent"
        new_game_state = {"phase": "responding"}

        self.mock_room_lifecycle_service.get_room_data.return_value = None

        result = self.service.update_game_state(room_id, new_game_state)

        assert result is False

    def test_update_game_state_invalid_transition(self):
        """Test game state update with invalid transition"""
        room_id = "test-room"
        room = self.create_valid_room_data("waiting")
        new_game_state = {
            "phase": "results",  # Invalid transition from waiting
            "current_prompt": None,
            "responses": [],
            "guesses": {},
            "round_number": 0
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        with patch.object(self.service, 'validate_game_state_transition', return_value=False):
            result = self.service.update_game_state(room_id, new_game_state)

            assert result is False

    def test_update_game_state_consistency_failure(self):
        """Test game state update fails when consistency check fails"""
        room_id = "test-room"
        room = self.create_valid_room_data("waiting")
        new_game_state = {
            "phase": "responding",
            "current_prompt": "Test prompt",
            "responses": [],
            "guesses": {},
            "round_number": 1
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room

        with patch.object(self.service, 'validate_game_state_transition', return_value=True), \
             patch.object(self.service, 'validate_room_state_consistency', return_value=False), \
             patch('src.services.room_state_service.logger') as mock_logger:

            result = self.service.update_game_state(room_id, new_game_state)

            assert result is False
            mock_logger.error.assert_called()


class TestRoomStateServiceConcurrency:
    """Test concurrency control integration"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.mock_room_lifecycle_service = Mock()
        self.mock_concurrency_control_service = Mock()

        # Setup mock context manager for concurrency control
        self.mock_context = Mock()
        self.mock_concurrency_control_service.room_operation.return_value = self.mock_context
        self.mock_context.__enter__ = Mock(return_value=self.mock_context)
        self.mock_context.__exit__ = Mock(return_value=None)

        self.service = RoomStateService(
            room_lifecycle_service=self.mock_room_lifecycle_service,
            concurrency_control_service=self.mock_concurrency_control_service
        )

    def test_update_game_state_uses_concurrency_control(self):
        """Test that update_game_state uses concurrency control"""
        room_id = "test-room"
        new_game_state = {"phase": "responding"}

        self.mock_room_lifecycle_service.get_room_data.return_value = None

        self.service.update_game_state(room_id, new_game_state)

        # Verify concurrency control was called
        self.mock_concurrency_control_service.room_operation.assert_called_once_with(room_id)
        self.mock_context.__enter__.assert_called_once()
        self.mock_context.__exit__.assert_called_once()

    def test_update_room_activity_uses_concurrency_control(self):
        """Test that update_room_activity uses concurrency control"""
        room_id = "test-room"

        self.mock_room_lifecycle_service.get_room_data.return_value = None

        self.service.update_room_activity(room_id)

        # Verify concurrency control was called
        self.mock_concurrency_control_service.room_operation.assert_called_once_with(room_id)
        self.mock_context.__enter__.assert_called_once()
        self.mock_context.__exit__.assert_called_once()

    def test_concurrency_control_exception_handling(self):
        """Test that exceptions in concurrency control are handled"""
        room_id = "test-room"
        room = {
            "room_id": room_id,
            "players": {},
            "game_state": {"phase": "waiting"},
            "last_activity": datetime.now()
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = room
        self.mock_context.__enter__.side_effect = Exception("Concurrency error")

        with pytest.raises(Exception, match="Concurrency error"):
            self.service.update_room_activity(room_id)


class TestRoomStateServiceEdgeCases:
    """Test edge cases and error scenarios"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.mock_room_lifecycle_service = Mock()
        self.mock_concurrency_control_service = Mock()

        self.service = RoomStateService(
            room_lifecycle_service=self.mock_room_lifecycle_service,
            concurrency_control_service=self.mock_concurrency_control_service
        )

    def test_get_room_state_empty_room_data(self):
        """Test get_room_state with empty room data"""
        room_id = "test-room"
        empty_room = {}

        self.mock_room_lifecycle_service.get_room_data.return_value = empty_room

        result = self.service.get_room_state(room_id)

        # Empty dict is falsy, so service returns None
        assert result is None

    def test_validate_consistency_malformed_players(self):
        """Test validation with malformed players data"""
        room_id = "test-room"
        malformed_room = {
            "room_id": room_id,
            "players": {
                "player1": {"player_id": "player1"},
                "player2": {}  # Missing player_id
            },
            "game_state": {
                "phase": "waiting",
                "current_prompt": None,
                "responses": [],
                "guesses": {},
                "round_number": 0
            },
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }

        self.mock_room_lifecycle_service.get_room_data.return_value = malformed_room

        result = self.service.validate_room_state_consistency(room_id)

        assert result is False

    def test_validate_transition_unknown_phase(self):
        """Test validation with unknown phase"""
        room = {
            "game_state": {"phase": "unknown_phase"}
        }
        new_game_state = {
            "phase": "waiting",
            "current_prompt": None,
            "responses": [],
            "guesses": {},
            "round_number": 0
        }

        result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

        assert result is False

    def test_validate_transition_missing_current_phase(self):
        """Test validation when current phase is missing"""
        room = {
            "game_state": {}  # Missing phase
        }
        new_game_state = {
            "phase": "waiting",
            "current_prompt": None,
            "responses": [],
            "guesses": {},
            "round_number": 0
        }

        result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

        # Should default to "waiting" and allow transition
        assert result is True

    def test_validate_transition_missing_new_phase(self):
        """Test validation when new phase is missing"""
        room = {
            "game_state": {"phase": "waiting"}
        }
        new_game_state = {
            # Missing phase
            "current_prompt": None,
            "responses": [],
            "guesses": {},
            "round_number": 0
        }

        with patch('src.services.room_state_service.logger') as mock_logger:
            result = self.service.validate_game_state_transition(room, new_game_state, "test-room")

            assert result is False
            mock_logger.warning.assert_called()

    def test_multiple_validation_phases(self):
        """Test all possible valid phase transitions"""
        valid_transitions = {
            "waiting": ["responding", "waiting"],
            "responding": ["guessing", "waiting", "responding"],
            "guessing": ["results", "responding", "waiting", "guessing"],
            "results": ["waiting", "responding"]
        }

        for current_phase, valid_next_phases in valid_transitions.items():
            for next_phase in valid_next_phases:
                room = {"game_state": {"phase": current_phase}}
                new_game_state = {
                    "phase": next_phase,
                    "current_prompt": None,
                    "responses": [],
                    "guesses": {},
                    "round_number": 0
                }

                result = self.service.validate_game_state_transition(room, new_game_state, "test-room")
                assert result is True, f"Failed transition: {current_phase} -> {next_phase}"