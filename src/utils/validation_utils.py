"""
Validation utilities for common patterns used across handlers.

This module provides utility functions for validation patterns that are repeated
across multiple handlers, complementing the ValidationService with higher-level
validation workflows.
"""

import logging
from typing import Dict, Any, Optional, List
from src.core.errors import ErrorCode, ValidationError

logger = logging.getLogger(__name__)


def validate_dict_structure(data: Any, required_fields: List[str]) -> Dict[str, Any]:
    """
    Validate that data is a dictionary with required fields.
    
    Args:
        data: Data to validate
        required_fields: List of required field names
        
    Returns:
        Validated data dictionary
        
    Raises:
        ValidationError: If data structure is invalid
    """
    if not isinstance(data, dict):
        raise ValidationError(
            ErrorCode.INVALID_DATA,
            "Invalid data format - expected dictionary"
        )
    
    # Check for missing required fields
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        # Provide specific error messages for common fields
        if len(missing_fields) == 1:
            field = missing_fields[0]
            if field == 'room_id':
                raise ValidationError(
                    ErrorCode.MISSING_ROOM_ID,
                    "Room ID is required"
                )
            elif field == 'player_name':
                raise ValidationError(
                    ErrorCode.MISSING_PLAYER_NAME,
                    "Player name is required"
                )
            elif field == 'response':
                raise ValidationError(
                    ErrorCode.EMPTY_RESPONSE,
                    "Response is required"
                )
            elif field == 'guess_index':
                raise ValidationError(
                    ErrorCode.MISSING_GUESS,
                    "Guess index is required"
                )
        
        # Generic error for multiple missing fields or other fields
        raise ValidationError(
            ErrorCode.INVALID_DATA,
            f"Missing required fields: {', '.join(missing_fields)}"
        )
    
    return data


def validate_session_exists(session_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate that a player session exists.
    
    Args:
        session_info: Session information from session service
        
    Returns:
        Valid session info
        
    Raises:
        ValidationError: If session doesn't exist
    """
    if not session_info:
        raise ValidationError(
            ErrorCode.NOT_IN_ROOM,
            'You are not currently in a room'
        )
    
    return session_info


def validate_game_phase(game_state: Optional[Dict[str, Any]], expected_phase: str) -> Dict[str, Any]:
    """
    Validate that the game is in the expected phase.
    
    Args:
        game_state: Current game state
        expected_phase: Expected phase name
        
    Returns:
        Valid game state
        
    Raises:
        ValidationError: If game is not in expected phase
    """
    if not game_state:
        raise ValidationError(
            ErrorCode.ROOM_NOT_FOUND,
            'Room not found or game not started'
        )
    
    current_phase = game_state.get('phase')
    if current_phase != expected_phase:
        phase_messages = {
            'responding': 'Responses can only be submitted during the responding phase',
            'guessing': 'Guesses can only be submitted during the guessing phase',
            'results': 'Results are only available during the results phase',
            'waiting': 'This action can only be performed while waiting for players'
        }
        
        message = phase_messages.get(expected_phase, f'Game must be in {expected_phase} phase')
        raise ValidationError(
            ErrorCode.WRONG_PHASE,
            message
        )
    
    return game_state


def validate_phase_not_expired(game_manager, room_id: str) -> None:
    """
    Validate that the current game phase has not expired.
    
    Args:
        game_manager: Game manager instance
        room_id: Room identifier
        
    Raises:
        ValidationError: If phase has expired
    """
    if game_manager.is_phase_expired(room_id):
        raise ValidationError(
            ErrorCode.PHASE_EXPIRED,
            'The current phase has expired'
        )


def validate_join_room_data(data: Any) -> Dict[str, str]:
    """
    Validate data for join room operation.
    
    Args:
        data: Raw data from client
        
    Returns:
        Dictionary with validated room_id and player_name
        
    Raises:
        ValidationError: If data is invalid
    """
    validated = validate_dict_structure(data, ['room_id', 'player_name'])
    return {
        'room_id': validated['room_id'],
        'player_name': validated['player_name']
    }


def validate_submit_response_data(data: Any) -> Dict[str, str]:
    """
    Validate data for submit response operation.
    
    Args:
        data: Raw data from client
        
    Returns:
        Dictionary with validated response
        
    Raises:
        ValidationError: If data is invalid
    """
    validated = validate_dict_structure(data, ['response'])
    return {
        'response': validated['response']
    }


def validate_submit_guess_data(data: Any) -> Dict[str, int]:
    """
    Validate data for submit guess operation.
    
    Args:
        data: Raw data from client
        
    Returns:
        Dictionary with validated guess_index
        
    Raises:
        ValidationError: If data is invalid
    """
    validated = validate_dict_structure(data, ['guess_index'])
    return {
        'guess_index': validated['guess_index']
    }