"""
Game Info Handler

This module handles Socket.IO events related to game information,
including getting round results, leaderboard, and time remaining.
"""

import logging

from src.core.errors import ErrorCode, ValidationError
from src.services.error_response_factory import with_error_handling
from .base_handler import BaseInfoHandler

logger = logging.getLogger(__name__)


class GameInfoHandler(BaseInfoHandler):
    """Handler for game information operations like results, leaderboard, and timing."""

    @with_error_handling
    def handle_get_round_results(self, data=None):
        """Handle request for detailed round results."""
        self.log_handler_start('handle_get_round_results', data)

        session_info = self.require_session()
        room_id = session_info['room_id']

        round_results = self.game_manager.get_round_results(room_id)

        if round_results:
            self.emit_success('round_results', {
                'results': round_results
            })
            self.log_handler_success('handle_get_round_results', 'Round results sent')
        else:
            raise ValidationError(
                ErrorCode.NO_RESULTS_AVAILABLE,
                'No round results available. Game must be in results phase.'
            )

    @with_error_handling
    def handle_get_leaderboard(self, data=None):
        """Handle request for current leaderboard."""
        self.log_handler_start('handle_get_leaderboard', data)

        session_info = self.require_session()
        room_id = session_info['room_id']

        leaderboard = self.game_manager.get_leaderboard(room_id)
        scoring_summary = self.game_manager.get_scoring_summary(room_id)

        self.emit_success('leaderboard', {
            'leaderboard': leaderboard,
            'scoring_summary': scoring_summary
        })

        self.log_handler_success('handle_get_leaderboard', 'Leaderboard sent')

    @with_error_handling
    def handle_get_time_remaining(self, data=None):
        """Handle request for current phase time remaining."""
        self.log_handler_start('handle_get_time_remaining', data)

        session_info = self.require_session()
        room_id = session_info['room_id']

        time_remaining = self.game_manager.get_phase_time_remaining(room_id)
        game_state = self.game_manager.get_game_state(room_id)

        if game_state:
            self.emit_success('time_remaining', {
                'time_remaining': time_remaining,
                'phase': game_state['phase'],
                'phase_duration': game_state.get('phase_duration', 0)
            })
            self.log_handler_success('handle_get_time_remaining', 'Time remaining sent')
        else:
            raise ValidationError(
                ErrorCode.ROOM_NOT_FOUND,
                'Room not found'
            )