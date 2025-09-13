"""
Game Action Handler

This module handles Socket.IO events related to game actions,
including starting rounds, submitting responses, and submitting guesses.
"""

import logging
from flask import request

from src.core.errors import ErrorCode, ValidationError
from src.services.error_response_factory import with_error_handling
from src.services.rate_limit_service import prevent_event_overflow
from .base_handler import BaseGameHandler

logger = logging.getLogger(__name__)


class GameActionHandler(BaseGameHandler):
    """Handler for game action operations like starting rounds and submitting responses/guesses."""

    @prevent_event_overflow('start_round')
    @with_error_handling
    def handle_start_round(self, data=None):
        """
        Handle request to start a new game round.
        Only works if player is in a room and game is in waiting or results phase.
        """
        self.log_handler_start('handle_start_round', data)

        # Check if player is in a room
        session_info = self.require_session()
        room_id = session_info['room_id']

        # Check if round can be started
        self.check_can_start_round(room_id)

        # Check if content manager has prompts loaded
        self._validate_content_available()

        # Get random prompt
        prompt_dict = self._get_random_prompt()

        # Start the round
        if self.game_manager.start_new_round(room_id, prompt_dict):
            self.log_handler_success(
                'handle_start_round',
                f'Started new round in room {room_id} with prompt {prompt_dict["id"]}'
            )

            # Broadcast round start to all players in room
            self.broadcast_service.broadcast_round_started(room_id)
            self.broadcast_service.broadcast_room_state_update(room_id)

            self.emit_success('round_started', {
                'message': 'Round started successfully'
            })
        else:
            raise ValidationError(
                ErrorCode.START_ROUND_FAILED,
                'Failed to start round'
            )

    @prevent_event_overflow('submit_response')
    @with_error_handling
    def handle_submit_response(self, data):
        """
        Handle player response submission during responding phase.

        Expected data format:
        {
            'response': 'player response text'
        }
        """
        self.log_handler_start('handle_submit_response', data)

        # Check if player is in a room first
        session_info = self.require_session()

        # Validate and extract response text
        response_text = self.validate_response_data(data)

        room_id = session_info['room_id']
        player_id = session_info['player_id']

        # Validate game state and phase
        self.validate_game_phase(room_id, 'responding')
        self.check_phase_not_expired(room_id)

        # Submit the response
        if self.game_manager.submit_player_response(room_id, player_id, response_text):
            self.log_handler_success(
                'handle_submit_response',
                f'Player {player_id} submitted response in room {room_id}'
            )

            # Send confirmation to submitting player
            self.emit_success('response_submitted', {
                'message': 'Response submitted successfully'
            })

            # Check if phase changed to guessing (all players responded)
            updated_game_state = self.game_manager.get_game_state(room_id)
            if updated_game_state and updated_game_state['phase'] == 'guessing':
                # Broadcast guessing phase start
                self.broadcast_service.broadcast_guessing_phase_started(room_id)
            else:
                # Broadcast response count update to all players (without revealing content)
                self.broadcast_service.broadcast_response_submitted(room_id)

            self.broadcast_service.broadcast_room_state_update(room_id)
        else:
            raise ValidationError(
                ErrorCode.SUBMIT_FAILED,
                'Failed to submit response. You may have already submitted or the game state has changed.'
            )

    @prevent_event_overflow('submit_guess')
    @with_error_handling
    def handle_submit_guess(self, data):
        """
        Handle player guess submission during guessing phase.

        Expected data format:
        {
            'guess_index': 0  # Index of the response they think is from LLM
        }
        """
        self.log_handler_start('handle_submit_guess', data)

        # Check if player is in a room
        session_info = self.require_session()

        room_id = session_info['room_id']
        player_id = session_info['player_id']

        # Check if game is in guessing phase first
        game_state = self.validate_game_phase(room_id, 'guessing')
        self.check_phase_not_expired(room_id)

        # Get the filtered responses for validation
        responses = game_state.get('responses', [])
        filtered_responses = [i for i, response in enumerate(responses) if response['author_id'] != player_id]

        # Validate guess data
        guess_index = self.validate_guess_data(data, len(filtered_responses))

        # Map the filtered index to the actual response index
        actual_response_index = filtered_responses[guess_index]

        # Submit the guess with the actual response index
        if self.game_manager.submit_player_guess(room_id, player_id, actual_response_index):
            self.log_handler_success(
                'handle_submit_guess',
                f'Player {player_id} submitted guess {guess_index} in room {room_id}'
            )

            # Send confirmation to submitting player
            self.emit_success('guess_submitted', {
                'message': 'Guess submitted successfully',
                'guess_index': guess_index  # This is the filtered index the player sees
            })

            # Check if phase changed to results (all players guessed)
            updated_game_state = self.game_manager.get_game_state(room_id)
            if updated_game_state and updated_game_state['phase'] == 'results':
                # Broadcast results phase start
                self.broadcast_service.broadcast_results_phase_started(room_id)
            else:
                # Broadcast guess count update to all players (without revealing content)
                self.broadcast_service.broadcast_guess_submitted(room_id)

            self.broadcast_service.broadcast_room_state_update(room_id)
        else:
            raise ValidationError(
                ErrorCode.SUBMIT_GUESS_FAILED,
                'Failed to submit guess. You may have already guessed or the game state has changed.'
            )

    def _validate_content_available(self):
        """Validate that content manager has prompts available."""
        if not self.content_manager.is_loaded() or self.content_manager.get_prompt_count() == 0:
            raise ValidationError(
                ErrorCode.NO_PROMPTS_AVAILABLE,
                'No prompts are available to start a round'
            )

    def _get_random_prompt(self):
        """Get a random prompt from the content manager."""
        try:
            prompt_data = self.content_manager.get_random_prompt_response()
            return {
                'id': prompt_data.id,
                'prompt': prompt_data.prompt,
                'model': prompt_data.model,
                'llm_response': prompt_data.get_response()
            }
        except Exception as e:
            logger.error(f'Error getting random prompt: {e}')
            raise ValidationError(
                ErrorCode.PROMPT_ERROR,
                'Failed to get prompt for round'
            )