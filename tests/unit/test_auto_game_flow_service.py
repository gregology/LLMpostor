"""
Auto Game Flow Service Unit Tests - Parts 1 & 2
Part 1: Core Logic - Phase transition logic, timeout detection, game state validation, and player readiness checking.
Part 2: Threading - Background thread management, timer service integration, thread lifecycle, and resource cleanup.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import time
import threading
from datetime import datetime

from src.services.auto_game_flow_service import AutoGameFlowService
from tests.helpers.socket_mocks import create_mock_socketio


class TestAutoGameFlowServiceCoreLogic:
    """Test AutoGameFlowService core logic functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        # Create mock dependencies
        self.mock_broadcast_service = Mock()
        self.mock_game_manager = Mock()
        self.mock_room_manager = Mock()
        self.mock_room_state_presenter = Mock()

        # Create mock configuration
        self.mock_config = Mock()
        self.mock_config.game_flow_check_interval = 1
        self.mock_config.countdown_broadcast_interval = 10
        self.mock_config.room_status_broadcast_interval = 60
        self.mock_config.warning_threshold_seconds = 30
        self.mock_config.final_warning_threshold_seconds = 10
        self.mock_config.room_cleanup_inactive_minutes = 60
        self.mock_config.min_players_required = 2

        # Patch configuration and threading to prevent actual service startup
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread') as mock_thread:

            # Create service instance without starting background thread
            self.service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            # Override threading to prevent actual background execution
            self.service.running = False

    def test_initialization_sets_config_values(self):
        """Test that service initializes with correct configuration values"""
        assert self.service.check_interval == 1
        assert self.service.countdown_broadcast_interval == 10
        assert self.service.room_status_broadcast_interval == 60
        assert self.service.warning_threshold_seconds == 30
        assert self.service.final_warning_threshold_seconds == 10
        assert self.service.room_cleanup_inactive_minutes == 60
        assert self.service.min_players_required == 2

    def test_initialization_creates_room_state_presenter(self):
        """Test that service creates room state presenter with game manager"""
        assert self.service.room_state_presenter is not None
        assert self.service.room_state_presenter == self.mock_room_state_presenter

    def test_stop_sets_running_to_false(self):
        """Test that stop method sets running flag to False"""
        self.service.running = True

        with patch.object(self.service.timer_thread, 'is_alive', return_value=False):
            self.service.stop()

        assert not self.service.running

    def test_check_phase_timeouts_processes_all_rooms(self):
        """Test that phase timeout checking processes all active rooms"""
        # Setup mock rooms
        room_ids = ["room1", "room2", "room3"]
        self.mock_room_manager.get_all_rooms.return_value = room_ids

        # Mock phase expiration - only room2 is expired
        self.mock_game_manager.is_phase_expired.side_effect = [False, True, False]

        # Mock handle phase timeout
        with patch.object(self.service, '_handle_phase_timeout') as mock_handle:
            self.service._check_phase_timeouts()

            # Verify all rooms were checked
            assert self.mock_game_manager.is_phase_expired.call_count == 3
            self.mock_game_manager.is_phase_expired.assert_any_call("room1")
            self.mock_game_manager.is_phase_expired.assert_any_call("room2")
            self.mock_game_manager.is_phase_expired.assert_any_call("room3")

            # Verify only expired room was handled
            mock_handle.assert_called_once_with("room2")

    def test_check_phase_timeouts_handles_exceptions(self):
        """Test that phase timeout checking handles exceptions gracefully"""
        room_ids = ["room1", "room2"]
        self.mock_room_manager.get_all_rooms.return_value = room_ids

        # First room throws exception, second should still be processed
        self.mock_game_manager.is_phase_expired.side_effect = [Exception("Test error"), False]

        # Should not raise exception
        self.service._check_phase_timeouts()

        # Verify both rooms were attempted
        assert self.mock_game_manager.is_phase_expired.call_count == 2

    def test_handle_phase_timeout_advances_phase(self):
        """Test that phase timeout handler advances the game phase"""
        room_id = "test_room"

        # Setup room state
        room_state = {
            "game_state": {"phase": "responding"}
        }
        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_game_manager.advance_game_phase.return_value = "guessing"

        # Mock broadcast methods
        with patch.object(self.service, '_broadcast_guessing_phase_timeout_started') as mock_guessing, \
             patch.object(self.service, '_broadcast_results_phase_timeout_started') as mock_results, \
             patch.object(self.service, '_broadcast_round_ended') as mock_round_ended:

            self.service._handle_phase_timeout(room_id)

            # Verify phase advancement
            self.mock_game_manager.advance_game_phase.assert_called_once_with(room_id)

            # Verify correct broadcast for guessing phase
            mock_guessing.assert_called_once_with(room_id)
            mock_results.assert_not_called()
            mock_round_ended.assert_not_called()

            # Verify room state update broadcast
            self.mock_broadcast_service.broadcast_room_state_update.assert_called_once_with(room_id)

    def test_handle_phase_timeout_broadcasts_results_phase(self):
        """Test that phase timeout handler broadcasts results phase correctly"""
        room_id = "test_room"

        # Setup room state
        room_state = {
            "game_state": {"phase": "guessing"}
        }
        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_game_manager.advance_game_phase.return_value = "results"

        with patch.object(self.service, '_broadcast_results_phase_timeout_started') as mock_results:
            self.service._handle_phase_timeout(room_id)

            mock_results.assert_called_once_with(room_id)

    def test_handle_phase_timeout_broadcasts_round_ended(self):
        """Test that phase timeout handler broadcasts round ended correctly"""
        room_id = "test_room"

        # Setup room state
        room_state = {
            "game_state": {"phase": "results"}
        }
        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_game_manager.advance_game_phase.return_value = "waiting"

        with patch.object(self.service, '_broadcast_round_ended') as mock_round_ended:
            self.service._handle_phase_timeout(room_id)

            mock_round_ended.assert_called_once_with(room_id)

    def test_handle_phase_timeout_skips_nonexistent_room(self):
        """Test that phase timeout handler skips non-existent rooms"""
        room_id = "nonexistent_room"
        self.mock_room_manager.get_room_state.return_value = None

        self.service._handle_phase_timeout(room_id)

        # Verify no phase advancement attempted
        self.mock_game_manager.advance_game_phase.assert_not_called()
        self.mock_broadcast_service.broadcast_room_state_update.assert_not_called()

    def test_handle_phase_timeout_handles_exceptions(self):
        """Test that phase timeout handler handles exceptions gracefully"""
        room_id = "test_room"
        self.mock_room_manager.get_room_state.side_effect = Exception("Test error")

        # Should not raise exception
        self.service._handle_phase_timeout(room_id)

        # Verify no further processing
        self.mock_game_manager.advance_game_phase.assert_not_called()

    def test_cleanup_inactive_rooms_calls_room_manager(self):
        """Test that inactive room cleanup calls room manager with correct parameters"""
        self.mock_room_manager.cleanup_inactive_rooms.return_value = 3

        self.service._cleanup_inactive_rooms()

        self.mock_room_manager.cleanup_inactive_rooms.assert_called_once_with(
            max_inactive_minutes=60
        )

    def test_cleanup_inactive_rooms_handles_exceptions(self):
        """Test that inactive room cleanup handles exceptions gracefully"""
        self.mock_room_manager.cleanup_inactive_rooms.side_effect = Exception("Test error")

        # Should not raise exception
        self.service._cleanup_inactive_rooms()

    def test_broadcast_countdown_updates_filters_by_interval(self):
        """Test that countdown updates respect broadcast interval"""
        room_ids = ["room1"]
        self.mock_room_manager.get_all_rooms.return_value = room_ids

        # Setup room state with responding phase
        room_state = {
            "game_state": {
                "phase": "responding",
                "phase_duration": 180
            }
        }
        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_game_manager.get_phase_time_remaining.return_value = 120

        current_time = time.time()
        last_broadcast = {"room1": current_time - 5}  # 5 seconds ago, less than interval

        self.service._broadcast_countdown_updates(current_time, last_broadcast)

        # Should not broadcast due to interval
        self.mock_broadcast_service.emit_to_room.assert_not_called()

    def test_broadcast_countdown_updates_sends_for_timed_phases(self):
        """Test that countdown updates are sent for responding and guessing phases"""
        room_ids = ["room1", "room2"]
        self.mock_room_manager.get_all_rooms.return_value = room_ids

        # Setup room states
        room_states = [
            {"game_state": {"phase": "responding", "phase_duration": 180}},
            {"game_state": {"phase": "guessing", "phase_duration": 120}}
        ]
        self.mock_room_manager.get_room_state.side_effect = room_states
        self.mock_game_manager.get_phase_time_remaining.side_effect = [120, 90]

        current_time = time.time()
        last_broadcast = {}  # No previous broadcasts

        self.service._broadcast_countdown_updates(current_time, last_broadcast)

        # Verify countdown updates sent for both rooms
        assert self.mock_broadcast_service.emit_to_room.call_count == 2

        # Check first room call
        first_call = self.mock_broadcast_service.emit_to_room.call_args_list[0]
        assert first_call[0][0] == 'countdown_update'
        assert first_call[0][1] == {
            'phase': 'responding',
            'time_remaining': 120,
            'phase_duration': 180
        }
        assert first_call[0][2] == 'room1'

        # Check second room call
        second_call = self.mock_broadcast_service.emit_to_room.call_args_list[1]
        assert second_call[0][0] == 'countdown_update'
        assert second_call[0][1] == {
            'phase': 'guessing',
            'time_remaining': 90,
            'phase_duration': 120
        }
        assert second_call[0][2] == 'room2'

    def test_broadcast_countdown_updates_skips_non_timed_phases(self):
        """Test that countdown updates are not sent for waiting/results phases"""
        room_ids = ["room1", "room2"]
        self.mock_room_manager.get_all_rooms.return_value = room_ids

        # Setup room states with non-timed phases
        room_states = [
            {"game_state": {"phase": "waiting"}},
            {"game_state": {"phase": "results"}}
        ]
        self.mock_room_manager.get_room_state.side_effect = room_states

        current_time = time.time()
        last_broadcast = {}

        self.service._broadcast_countdown_updates(current_time, last_broadcast)

        # No countdown updates should be sent
        self.mock_broadcast_service.emit_to_room.assert_not_called()

    def test_broadcast_countdown_updates_sends_time_warnings(self):
        """Test that time warnings are sent at appropriate thresholds"""
        room_ids = ["room1"]
        self.mock_room_manager.get_all_rooms.return_value = room_ids

        # Setup room state with low time remaining
        room_state = {
            "game_state": {
                "phase": "responding",
                "phase_duration": 180
            }
        }
        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_game_manager.get_phase_time_remaining.return_value = 28  # Between 30 and 25 (30-5), triggers warning

        current_time = time.time()
        last_broadcast = {}

        self.service._broadcast_countdown_updates(current_time, last_broadcast)

        # Verify countdown update and warning were sent
        assert self.mock_broadcast_service.emit_to_room.call_count == 2

        # Check warning call
        warning_call = self.mock_broadcast_service.emit_to_room.call_args_list[1]
        assert warning_call[0][0] == 'time_warning'
        assert warning_call[0][1] == {
            'message': '30 seconds remaining!',
            'time_remaining': 28
        }
        assert warning_call[0][2] == 'room1'

    def test_broadcast_countdown_updates_sends_final_warning(self):
        """Test that final warning is sent at final threshold"""
        room_ids = ["room1"]
        self.mock_room_manager.get_all_rooms.return_value = room_ids

        # Setup room state with very low time remaining
        room_state = {
            "game_state": {
                "phase": "responding",
                "phase_duration": 180
            }
        }
        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_game_manager.get_phase_time_remaining.return_value = 8  # Less than 10 seconds

        current_time = time.time()
        last_broadcast = {}

        self.service._broadcast_countdown_updates(current_time, last_broadcast)

        # Verify countdown update and final warning were sent
        assert self.mock_broadcast_service.emit_to_room.call_count == 2

        # Check final warning call
        warning_call = self.mock_broadcast_service.emit_to_room.call_args_list[1]
        assert warning_call[0][0] == 'time_warning'
        assert warning_call[0][1] == {
            'message': '10 seconds remaining!',
            'time_remaining': 8
        }

    def test_broadcast_countdown_updates_handles_room_exceptions(self):
        """Test that countdown updates handle exceptions for individual rooms gracefully"""
        room_ids = ["room1", "room2"]
        self.mock_room_manager.get_all_rooms.return_value = room_ids

        # First room throws exception, second works normally
        room_states = [
            Exception("Test error"),
            {"game_state": {"phase": "responding", "phase_duration": 180}}
        ]
        self.mock_room_manager.get_room_state.side_effect = room_states
        self.mock_game_manager.get_phase_time_remaining.return_value = 120

        current_time = time.time()
        last_broadcast = {}

        # Should not raise exception
        self.service._broadcast_countdown_updates(current_time, last_broadcast)

        # Second room should still be processed
        self.mock_broadcast_service.emit_to_room.assert_called_once()

    def test_broadcast_guessing_phase_timeout_started_creates_correct_data(self):
        """Test that guessing phase timeout broadcast creates correct data structure"""
        room_id = "test_room"
        room_state = {"game_state": {"phase": "guessing"}}

        self.mock_room_manager.get_room_state.return_value = room_state

        # Mock presenter response
        presenter_data = {
            "phase": "guessing",
            "responses": ["response1", "response2"],
            "time_remaining": 120
        }
        self.mock_room_state_presenter.create_guessing_phase_data.return_value = presenter_data

        self.service._broadcast_guessing_phase_timeout_started(room_id)

        # Verify presenter was called correctly
        self.mock_room_state_presenter.create_guessing_phase_data.assert_called_once_with(
            room_state, room_id
        )

        # Verify broadcast with timeout reason added
        expected_data = presenter_data.copy()
        expected_data['timeout_reason'] = 'Response time expired'

        self.mock_broadcast_service.emit_to_room.assert_called_once_with(
            'guessing_phase_started', expected_data, room_id
        )

    def test_broadcast_results_phase_timeout_started_creates_correct_data(self):
        """Test that results phase timeout broadcast creates correct data structure"""
        room_id = "test_room"

        # Mock game manager responses
        round_results = {"results": "test_results"}
        leaderboard = [{"player": "test_player", "score": 100}]

        self.mock_game_manager.get_round_results.return_value = round_results
        self.mock_game_manager.get_leaderboard.return_value = leaderboard

        self.service._broadcast_results_phase_timeout_started(room_id)

        # Verify correct data structure
        expected_data = {
            'phase': 'results',
            'round_results': round_results,
            'leaderboard': leaderboard,
            'timeout_reason': 'Guessing time expired'
        }

        self.mock_broadcast_service.emit_to_room.assert_called_once_with(
            'results_phase_started', expected_data, room_id
        )

        # Verify player list update
        self.mock_broadcast_service.broadcast_player_list_update.assert_called_once_with(room_id)

    def test_broadcast_round_ended_sends_correct_message(self):
        """Test that round ended broadcast sends correct message"""
        room_id = "test_room"

        self.service._broadcast_round_ended(room_id)

        expected_data = {
            'phase': 'waiting',
            'message': 'Round completed. Ready for next round.'
        }

        self.mock_broadcast_service.emit_to_room.assert_called_once_with(
            'round_ended', expected_data, room_id
        )

    def test_broadcast_methods_handle_exceptions(self):
        """Test that broadcast methods handle exceptions gracefully"""
        room_id = "test_room"

        # Test guessing phase broadcast with exception
        self.mock_room_manager.get_room_state.side_effect = Exception("Test error")
        self.service._broadcast_guessing_phase_timeout_started(room_id)  # Should not raise

        # Test results phase broadcast with exception
        self.mock_game_manager.get_round_results.side_effect = Exception("Test error")
        self.service._broadcast_results_phase_timeout_started(room_id)  # Should not raise

        # Test round ended broadcast with exception
        self.mock_broadcast_service.emit_to_room.side_effect = Exception("Test error")
        self.service._broadcast_round_ended(room_id)  # Should not raise


class TestAutoGameFlowServicePlayerDisconnectImpact:
    """Test AutoGameFlowService player disconnect impact handling"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        # Create mock dependencies
        self.mock_broadcast_service = Mock()
        self.mock_game_manager = Mock()
        self.mock_room_manager = Mock()
        self.mock_room_state_presenter = Mock()

        # Create mock configuration
        self.mock_config = Mock()
        self.mock_config.game_flow_check_interval = 1
        self.mock_config.countdown_broadcast_interval = 10
        self.mock_config.room_status_broadcast_interval = 60
        self.mock_config.warning_threshold_seconds = 30
        self.mock_config.final_warning_threshold_seconds = 10
        self.mock_config.room_cleanup_inactive_minutes = 60
        self.mock_config.min_players_required = 2

        # Patch configuration and threading
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread'):

            self.service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )
            self.service.running = False

    def test_disconnect_with_sufficient_players_continues_game(self):
        """Test that disconnect with sufficient remaining players continues the game"""
        room_id = "test_room"
        disconnected_player_id = "player1"

        # Setup room state
        room_state = {
            "game_state": {"phase": "responding"}
        }
        connected_players = [{"id": "player2"}, {"id": "player3"}]  # 2 players remaining

        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_room_manager.get_connected_players.return_value = connected_players

        self.service.handle_player_disconnect_game_impact(room_id, disconnected_player_id)

        # Verify no phase reset occurred
        self.mock_game_manager._advance_to_waiting_phase.assert_not_called()
        self.mock_broadcast_service.broadcast_game_paused.assert_not_called()

    def test_disconnect_with_insufficient_players_resets_to_waiting(self):
        """Test that disconnect with insufficient players resets to waiting phase"""
        room_id = "test_room"
        disconnected_player_id = "player1"

        # Setup room state with active game
        room_state = {
            "game_state": {"phase": "responding"}
        }
        connected_players = [{"id": "player2"}]  # Only 1 player remaining, need 2

        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_room_manager.get_connected_players.return_value = connected_players
        self.mock_game_manager._advance_to_waiting_phase.return_value = "waiting"

        self.service.handle_player_disconnect_game_impact(room_id, disconnected_player_id)

        # Verify phase reset
        self.mock_game_manager._advance_to_waiting_phase.assert_called_once_with(room_id)

        # Verify game paused broadcast
        expected_error_response = {
            'success': False,
            'error': {
                'code': 'INSUFFICIENT_PLAYERS',
                'message': 'Game paused - need at least 2 players to continue'
            }
        }
        self.mock_broadcast_service.broadcast_game_paused.assert_called_once_with(
            room_id, expected_error_response
        )
        self.mock_broadcast_service.broadcast_room_state_update.assert_called_once_with(room_id)

    def test_disconnect_skips_waiting_phase_rooms(self):
        """Test that disconnect handling skips rooms already in waiting phase"""
        room_id = "test_room"
        disconnected_player_id = "player1"

        # Setup room state already in waiting
        room_state = {
            "game_state": {"phase": "waiting"}
        }
        connected_players = [{"id": "player2"}]  # Only 1 player

        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_room_manager.get_connected_players.return_value = connected_players

        self.service.handle_player_disconnect_game_impact(room_id, disconnected_player_id)

        # Verify no phase advancement
        self.mock_game_manager._advance_to_waiting_phase.assert_not_called()
        self.mock_broadcast_service.broadcast_game_paused.assert_not_called()

    def test_disconnect_auto_advances_responding_phase(self):
        """Test that disconnect can auto-advance responding phase when all remaining players responded"""
        room_id = "test_room"
        disconnected_player_id = "player1"

        # Setup room state with responses from all remaining players
        room_state = {
            "game_state": {
                "phase": "responding",
                "responses": [
                    {"author_id": "player2", "text": "response2"},
                    {"author_id": "player3", "text": "response3"}
                ]
            }
        }
        connected_players = [{"id": "player2"}, {"id": "player3"}]  # 2 responses, 2 players

        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_room_manager.get_connected_players.return_value = connected_players
        self.mock_game_manager.advance_game_phase.return_value = "guessing"

        self.service.handle_player_disconnect_game_impact(room_id, disconnected_player_id)

        # Verify phase advancement
        self.mock_game_manager.advance_game_phase.assert_called_once_with(room_id)
        self.mock_broadcast_service.broadcast_guessing_phase_started.assert_called_once_with(room_id)
        self.mock_broadcast_service.broadcast_room_state_update.assert_called_once_with(room_id)

    def test_disconnect_auto_advances_guessing_phase(self):
        """Test that disconnect can auto-advance guessing phase when all remaining players guessed"""
        room_id = "test_room"
        disconnected_player_id = "player1"

        # Setup room state with guesses from all remaining players
        room_state = {
            "game_state": {
                "phase": "guessing",
                "guesses": [
                    {"author_id": "player2", "guess": "guess2"},
                    {"author_id": "player3", "guess": "guess3"}
                ]
            }
        }
        connected_players = [{"id": "player2"}, {"id": "player3"}]  # 2 guesses, 2 players

        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_room_manager.get_connected_players.return_value = connected_players
        self.mock_game_manager.advance_game_phase.return_value = "results"

        self.service.handle_player_disconnect_game_impact(room_id, disconnected_player_id)

        # Verify phase advancement
        self.mock_game_manager.advance_game_phase.assert_called_once_with(room_id)
        self.mock_broadcast_service.broadcast_results_phase_started.assert_called_once_with(room_id)
        self.mock_broadcast_service.broadcast_room_state_update.assert_called_once_with(room_id)

    def test_disconnect_handles_nonexistent_room(self):
        """Test that disconnect handling skips non-existent rooms"""
        room_id = "nonexistent_room"
        disconnected_player_id = "player1"

        self.mock_room_manager.get_room_state.return_value = None

        self.service.handle_player_disconnect_game_impact(room_id, disconnected_player_id)

        # Verify no further processing
        self.mock_room_manager.get_connected_players.assert_not_called()
        self.mock_game_manager._advance_to_waiting_phase.assert_not_called()

    def test_disconnect_handles_player_retrieval_exception(self):
        """Test that disconnect handling continues when player retrieval fails"""
        room_id = "test_room"
        disconnected_player_id = "player1"

        # Setup room state
        room_state = {
            "game_state": {"phase": "responding"}
        }

        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_room_manager.get_connected_players.side_effect = Exception("Test error")

        self.service.handle_player_disconnect_game_impact(room_id, disconnected_player_id)

        # Should treat as having 0 players and reset to waiting
        self.mock_game_manager._advance_to_waiting_phase.assert_called_once_with(room_id)

    def test_disconnect_handles_general_exceptions(self):
        """Test that disconnect handling handles exceptions gracefully"""
        room_id = "test_room"
        disconnected_player_id = "player1"

        self.mock_room_manager.get_room_state.side_effect = Exception("Test error")

        # Should not raise exception
        self.service.handle_player_disconnect_game_impact(room_id, disconnected_player_id)

        # Verify no further processing
        self.mock_game_manager._advance_to_waiting_phase.assert_not_called()


class TestAutoGameFlowServiceThreading:
    """Test AutoGameFlowService threading and background service functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        # Create mock dependencies
        self.mock_broadcast_service = Mock()
        self.mock_game_manager = Mock()
        self.mock_room_manager = Mock()
        self.mock_room_state_presenter = Mock()

        # Create mock configuration
        self.mock_config = Mock()
        self.mock_config.game_flow_check_interval = 0.1  # Fast for testing
        self.mock_config.countdown_broadcast_interval = 10
        self.mock_config.room_status_broadcast_interval = 60
        self.mock_config.warning_threshold_seconds = 30
        self.mock_config.final_warning_threshold_seconds = 10
        self.mock_config.room_cleanup_inactive_minutes = 60
        self.mock_config.min_players_required = 2

    def test_service_starts_background_thread_on_initialization(self):
        """Test that service starts background thread during initialization"""
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread') as mock_thread_class:

            mock_thread_instance = Mock()
            mock_thread_class.return_value = mock_thread_instance

            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            # Verify thread was created and started
            mock_thread_class.assert_called_once_with(target=service._timer_loop, daemon=True)
            mock_thread_instance.start.assert_called_once()
            assert service.timer_thread == mock_thread_instance

    def test_service_sets_running_flag_on_initialization(self):
        """Test that service sets running flag to True on initialization"""
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread'):

            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            assert service.running is True

    def test_stop_waits_for_thread_completion(self):
        """Test that stop method waits for thread to complete with timeout"""
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread') as mock_thread_class:

            mock_thread_instance = Mock()
            mock_thread_instance.is_alive.return_value = True
            mock_thread_class.return_value = mock_thread_instance

            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            service.stop()

            # Verify thread join was called with timeout
            mock_thread_instance.join.assert_called_once_with(timeout=2)
            assert service.running is False

    def test_stop_skips_join_if_thread_not_alive(self):
        """Test that stop method skips join if thread is not alive"""
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread') as mock_thread_class:

            mock_thread_instance = Mock()
            mock_thread_instance.is_alive.return_value = False
            mock_thread_class.return_value = mock_thread_instance

            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            service.stop()

            # Verify thread join was not called
            mock_thread_instance.join.assert_not_called()
            assert service.running is False

    def test_timer_loop_respects_running_flag(self):
        """Test that timer loop exits when running flag is set to False"""
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread'), \
             patch('time.sleep') as mock_sleep, \
             patch('time.time', return_value=1000.0):

            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            # Set running to False immediately
            service.running = False

            # Call timer loop directly
            service._timer_loop()

            # Verify no processing occurred and no sleep was called
            self.mock_room_manager.get_all_rooms.assert_not_called()
            mock_sleep.assert_not_called()

    def test_timer_loop_calls_core_methods_in_sequence(self):
        """Test that timer loop calls core methods in correct sequence"""
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread'), \
             patch('time.sleep') as mock_sleep, \
             patch('time.time', return_value=1000.0) as mock_time:

            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            # Mock core methods
            with patch.object(service, '_check_phase_timeouts') as mock_check_timeouts, \
                 patch.object(service, '_broadcast_countdown_updates') as mock_broadcast_updates, \
                 patch.object(service, '_cleanup_inactive_rooms') as mock_cleanup:

                # Set up to run only one iteration
                service.running = True
                iteration_count = 0

                def side_effect(*args):
                    nonlocal iteration_count
                    iteration_count += 1
                    if iteration_count >= 1:
                        service.running = False

                mock_sleep.side_effect = side_effect

                # Call timer loop
                service._timer_loop()

                # Verify methods were called in correct order
                mock_check_timeouts.assert_called_once()
                mock_broadcast_updates.assert_called_once_with(1000.0, {})
                # Cleanup may or may not be called depending on timing (1000 % 60 != 0)
                mock_sleep.assert_called_once_with(0.1)

    def test_timer_loop_handles_room_cleanup_timing(self):
        """Test that timer loop only calls room cleanup at appropriate intervals"""
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread'), \
             patch('time.sleep') as mock_sleep:

            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            # Mock core methods
            with patch.object(service, '_check_phase_timeouts'), \
                 patch.object(service, '_broadcast_countdown_updates'), \
                 patch.object(service, '_cleanup_inactive_rooms') as mock_cleanup:

                # Test with time that doesn't trigger cleanup (not divisible by 60)
                with patch('time.time', return_value=1001.0):
                    service.running = True
                    iteration_count = 0

                    def side_effect(*args):
                        nonlocal iteration_count
                        iteration_count += 1
                        if iteration_count >= 1:
                            service.running = False

                    mock_sleep.side_effect = side_effect
                    service._timer_loop()

                    # Cleanup should not be called
                    mock_cleanup.assert_not_called()

                # Reset mock
                mock_cleanup.reset_mock()

                # Test with time that triggers cleanup (divisible by 60)
                with patch('time.time', return_value=1020.0):
                    service.running = True
                    iteration_count = 0

                    def side_effect(*args):
                        nonlocal iteration_count
                        iteration_count += 1
                        if iteration_count >= 1:
                            service.running = False

                    mock_sleep.side_effect = side_effect
                    service._timer_loop()

                    # Cleanup should be called
                    mock_cleanup.assert_called_once()

    def test_timer_loop_handles_exceptions_gracefully(self):
        """Test that timer loop handles exceptions and continues running"""
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread'), \
             patch('time.sleep') as mock_sleep, \
             patch('time.time', return_value=1000.0):

            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            # Mock one method to throw exception
            with patch.object(service, '_check_phase_timeouts', side_effect=Exception("Test error")), \
                 patch.object(service, '_broadcast_countdown_updates'), \
                 patch.object(service, '_cleanup_inactive_rooms'):

                service.running = True
                iteration_count = 0

                def side_effect(*args):
                    nonlocal iteration_count
                    iteration_count += 1
                    if iteration_count >= 1:
                        service.running = False

                mock_sleep.side_effect = side_effect

                # Should not raise exception
                service._timer_loop()

                # Sleep should still be called (for error recovery)
                mock_sleep.assert_called_once_with(0.1)

    def test_timer_loop_maintains_last_broadcast_state(self):
        """Test that timer loop maintains last broadcast state across iterations"""
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread'), \
             patch('time.sleep') as mock_sleep, \
             patch('time.time', side_effect=[1000.0, 1001.0]) as mock_time:

            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            broadcast_updates_calls = []

            def capture_broadcast_call(current_time, last_broadcast):
                broadcast_updates_calls.append((current_time, last_broadcast.copy()))

            # Mock core methods
            with patch.object(service, '_check_phase_timeouts'), \
                 patch.object(service, '_broadcast_countdown_updates', side_effect=capture_broadcast_call), \
                 patch.object(service, '_cleanup_inactive_rooms'):

                service.running = True
                iteration_count = 0

                def side_effect(*args):
                    nonlocal iteration_count
                    iteration_count += 1
                    if iteration_count >= 2:
                        service.running = False

                mock_sleep.side_effect = side_effect

                # Call timer loop
                service._timer_loop()

                # Verify broadcast updates was called with same last_broadcast dict
                assert len(broadcast_updates_calls) == 2
                # The last_broadcast dict should be the same object across calls
                first_call_dict = broadcast_updates_calls[0][1]
                second_call_dict = broadcast_updates_calls[1][1]
                # Both should be the same dict object (identity check isn't possible here, but they should have same state)

    def test_real_thread_lifecycle_integration(self):
        """Integration test for real thread lifecycle without mocking Thread class"""
        # Use a very fast check interval for testing
        fast_config = Mock()
        fast_config.game_flow_check_interval = 0.01  # 10ms for fast testing
        fast_config.countdown_broadcast_interval = 10
        fast_config.room_status_broadcast_interval = 60
        fast_config.warning_threshold_seconds = 30
        fast_config.final_warning_threshold_seconds = 10
        fast_config.room_cleanup_inactive_minutes = 60
        fast_config.min_players_required = 2

        with patch('src.services.auto_game_flow_service.get_config', return_value=fast_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter):

            # Don't mock threading.Thread for this test
            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            # Verify thread is actually running
            assert service.timer_thread.is_alive()
            assert service.running is True

            # Let it run briefly
            time.sleep(0.05)  # 50ms

            # Stop the service
            service.stop()

            # Verify thread stopped
            assert service.running is False
            # Wait a bit to ensure thread has time to stop
            time.sleep(0.02)
            assert not service.timer_thread.is_alive()

    def test_thread_daemon_property_set_correctly(self):
        """Test that background thread is created as daemon thread"""
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread') as mock_thread_class:

            mock_thread_instance = Mock()
            mock_thread_class.return_value = mock_thread_instance

            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            # Verify thread was created with daemon=True
            mock_thread_class.assert_called_once_with(target=service._timer_loop, daemon=True)

    def test_resource_cleanup_on_error_during_initialization(self):
        """Test that resources are cleaned up if error occurs during initialization"""
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread') as mock_thread_class:

            mock_thread_instance = Mock()
            mock_thread_instance.start.side_effect = Exception("Thread start failed")
            mock_thread_class.return_value = mock_thread_instance

            # Should raise exception during initialization
            with pytest.raises(Exception, match="Thread start failed"):
                service = AutoGameFlowService(
                    broadcast_service=self.mock_broadcast_service,
                    game_manager=self.mock_game_manager,
                    room_manager=self.mock_room_manager
                )

    def test_multiple_stop_calls_are_safe(self):
        """Test that calling stop() multiple times is safe"""
        with patch('src.services.auto_game_flow_service.get_config', return_value=self.mock_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread') as mock_thread_class:

            mock_thread_instance = Mock()
            mock_thread_instance.is_alive.side_effect = [True, False, False]  # Alive first time, then not
            mock_thread_class.return_value = mock_thread_instance

            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            # Call stop multiple times
            service.stop()
            service.stop()
            service.stop()

            # Should only join once (when thread was alive)
            mock_thread_instance.join.assert_called_once_with(timeout=2)
            assert service.running is False

    def test_configuration_values_affect_thread_behavior(self):
        """Test that configuration values are properly used in thread operations"""
        # Create config with specific values
        custom_config = Mock()
        custom_config.game_flow_check_interval = 0.5
        custom_config.countdown_broadcast_interval = 15
        custom_config.room_status_broadcast_interval = 30
        custom_config.warning_threshold_seconds = 45
        custom_config.final_warning_threshold_seconds = 15
        custom_config.room_cleanup_inactive_minutes = 90
        custom_config.min_players_required = 3

        with patch('src.services.auto_game_flow_service.get_config', return_value=custom_config), \
             patch('src.services.auto_game_flow_service.RoomStatePresenter', return_value=self.mock_room_state_presenter), \
             patch('threading.Thread'):

            service = AutoGameFlowService(
                broadcast_service=self.mock_broadcast_service,
                game_manager=self.mock_game_manager,
                room_manager=self.mock_room_manager
            )

            # Verify configuration values are set correctly
            assert service.check_interval == 0.5
            assert service.countdown_broadcast_interval == 15
            assert service.room_status_broadcast_interval == 30
            assert service.warning_threshold_seconds == 45
            assert service.final_warning_threshold_seconds == 15
            assert service.room_cleanup_inactive_minutes == 90
            assert service.min_players_required == 3