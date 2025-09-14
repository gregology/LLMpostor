"""
Base Handler Classes

This module provides base classes for Socket.IO handlers with common patterns
for validation, error handling, session management, and response formatting.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from flask import request
from flask_socketio import emit, join_room, leave_room

from src.container import get_container
from src.core.errors import ErrorCode, ValidationError

logger = logging.getLogger(__name__)


class BaseHandler(ABC):
    """
    Abstract base class for all Socket.IO handlers.

    Provides common functionality like service access, session management,
    validation patterns, and standardized response formatting.
    """

    def __init__(self):
        self._container = get_container()

    @property
    def room_manager(self):
        """Get the room manager service."""
        return self._container.get_service('room_manager')

    @property
    def game_manager(self):
        """Get the game manager service."""
        return self._container.get_service('game_manager')

    @property
    def content_manager(self):
        """Get the content manager service."""
        return self._container.get_service('content_manager')

    @property
    def validation_service(self):
        """Get the validation service."""
        return self._container.get_service('validation_service')

    @property
    def error_response_factory(self):
        """Get the error response factory service."""
        return self._container.get_service('error_response_factory')

    @property
    def session_service(self):
        """Get the session service."""
        return self._container.get_service('session_service')

    @property
    def broadcast_service(self):
        """Get the broadcast service."""
        return self._container.get_service('broadcast_service')

    @property
    def auto_flow_service(self):
        """Get the auto flow service."""
        return self._container.get_service('auto_flow_service')

    @property
    def app_config(self):
        """Get the app configuration."""
        return self._container.get_config('app_config')

    def get_current_session(self) -> Optional[Dict[str, Any]]:
        """Get the current session info for the requesting client."""
        return self.session_service.get_session(request.sid)  # type: ignore[attr-defined]

    def require_session(self) -> Dict[str, Any]:
        """
        Get the current session info, raising an error if not in a room.

        Returns:
            Session info dictionary

        Raises:
            ValidationError: If the player is not in a room
        """
        session_info = self.get_current_session()
        if not session_info:
            raise ValidationError(
                ErrorCode.NOT_IN_ROOM,
                'You are not currently in a room'
            )
        return session_info

    def validate_data_dict(self, data: Any, required_fields: Optional[list] = None) -> Dict[str, Any]:
        """
        Validate that data is a dictionary and contains required fields.

        Args:
            data: The data to validate
            required_fields: List of required field names

        Returns:
            The validated data dictionary

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(data, dict):
            raise ValidationError(
                ErrorCode.INVALID_DATA,
                "Invalid data format - expected dictionary"
            )

        if required_fields:
            for field in required_fields:
                if field not in data:
                    # Use specific error codes for common missing fields
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
                    else:
                        raise ValidationError(
                            ErrorCode.INVALID_DATA,
                            f"Missing required field: {field}"
                        )

        return data

    def emit_success(self, event_name: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit a success response to the requesting client.

        Args:
            event_name: The name of the event to emit
            data: Optional data to include in the response
        """
        response = self.error_response_factory.create_success_response(data or {})
        emit(event_name, response)

    def emit_error(self, event_name: str, error_code: ErrorCode, message: str) -> None:
        """
        Emit an error response to the requesting client.

        Args:
            event_name: The name of the event to emit
            error_code: The error code
            message: The error message
        """
        response = self.error_response_factory.create_error_response(error_code, message)
        emit(event_name, response)

    def log_handler_start(self, handler_name: str, data: Any = None) -> None:
        """Log the start of handler execution."""
        logger.info(f'{handler_name} called by client: {request.sid}')  # type: ignore[attr-defined]
        if data:
            logger.debug(f'{handler_name} data: {data}')

    def log_handler_success(self, handler_name: str, message: Optional[str] = None) -> None:
        """Log successful handler completion."""
        log_msg = f'{handler_name} completed successfully for client: {request.sid}'  # type: ignore[attr-defined]
        if message:
            log_msg += f' - {message}'
        logger.info(log_msg)


class RoomHandlerMixin:
    """
    Mixin for handlers that deal with room operations.

    Provides common room-related functionality like joining/leaving
    Socket.IO rooms and broadcasting to room members.
    """

    def join_socketio_room(self, room_id: str) -> None:
        """Join a Socket.IO room for broadcasting."""
        join_room(room_id)
        logger.debug(f'Client {request.sid} joined Socket.IO room: {room_id}')  # type: ignore[attr-defined]

    def leave_socketio_room(self, room_id: str) -> None:
        """Leave a Socket.IO room."""
        leave_room(room_id)
        logger.debug(f'Client {request.sid} left Socket.IO room: {room_id}')  # type: ignore[attr-defined]

    def broadcast_to_room(self, room_id: str, event_name: str, data: Dict[str, Any]) -> None:
        """
        Broadcast an event to all clients in a room.

        Args:
            room_id: The room to broadcast to
            event_name: The event name
            data: The data to broadcast
        """
        emit(event_name, data, to=room_id)
        logger.debug(f'Broadcasted {event_name} to room: {room_id}')


class GameHandlerMixin:
    """
    Mixin for handlers that deal with game operations.

    Provides common game-related functionality like phase validation,
    game state checking, and common game operation patterns.
    """

    # Type hints for expected attributes from BaseHandler
    game_manager: Any  # Will be injected by container

    def validate_game_phase(self, room_id: str, required_phase: str) -> Dict[str, Any]:
        """
        Validate that a game is in the required phase.

        Args:
            room_id: The room ID
            required_phase: The required phase name

        Returns:
            The current game state

        Raises:
            ValidationError: If the game is not in the required phase
        """
        game_state = self.game_manager.get_game_state(room_id)
        if not game_state:
            raise ValidationError(
                ErrorCode.ROOM_NOT_FOUND,
                'Room not found or game not active'
            )

        if game_state['phase'] != required_phase:
            raise ValidationError(
                ErrorCode.WRONG_PHASE,
                f'Action only allowed during {required_phase} phase'
            )

        return game_state

    def check_phase_not_expired(self, room_id: str) -> None:
        """
        Check that the current game phase has not expired.

        Args:
            room_id: The room ID

        Raises:
            ValidationError: If the phase has expired
        """
        if self.game_manager.is_phase_expired(room_id):
            raise ValidationError(
                ErrorCode.PHASE_EXPIRED,
                'Current phase has expired'
            )

    def check_can_start_round(self, room_id: str) -> None:
        """
        Check if a new round can be started.

        Args:
            room_id: The room ID

        Raises:
            ValidationError: If a round cannot be started
        """
        can_start, reason = self.game_manager.can_start_round(room_id)
        if not can_start:
            raise ValidationError(
                ErrorCode.CANNOT_START_ROUND,
                reason
            )


class ValidationHandlerMixin:
    """
    Mixin for handlers that need common validation patterns.

    Provides standardized validation methods for common data types
    used across multiple handlers.
    """

    # Type hints for expected attributes from BaseHandler
    validation_service: Any  # Will be injected by container

    def validate_data_dict(self, data: Any, required_fields: Optional[list] = None) -> Dict[str, Any]:
        """Expected to be implemented by BaseHandler"""
        raise NotImplementedError("This method should be provided by BaseHandler")

    def validate_room_join_data(self, data: Any) -> tuple[str, str]:
        """
        Validate room join data and extract room_id and player_name.

        Args:
            data: The data to validate

        Returns:
            Tuple of (room_id, player_name)

        Raises:
            ValidationError: If validation fails
        """
        validated_data = self.validate_data_dict(data, ['room_id', 'player_name'])
        room_id = self.validation_service.validate_room_id(validated_data['room_id'])
        player_name = self.validation_service.validate_player_name(validated_data['player_name'])
        return room_id, player_name

    def validate_response_data(self, data: Any) -> str:
        """
        Validate response submission data and extract response text.

        Args:
            data: The data to validate

        Returns:
            The validated response text

        Raises:
            ValidationError: If validation fails
        """
        validated_data = self.validate_data_dict(data, ['response'])
        return self.validation_service.validate_response_text(validated_data['response'])

    def validate_guess_data(self, data: Any, max_index: int) -> int:
        """
        Validate guess submission data and extract guess index.

        Args:
            data: The data to validate
            max_index: The maximum allowed index

        Returns:
            The validated guess index

        Raises:
            ValidationError: If validation fails
        """
        validated_data = self.validate_data_dict(data, ['guess_index'])
        return self.validation_service.validate_guess_index(
            validated_data['guess_index'],
            max_index
        )


class BaseRoomHandler(BaseHandler, RoomHandlerMixin, ValidationHandlerMixin):
    """Base class for handlers that deal with room operations."""
    pass


class BaseGameHandler(BaseHandler, GameHandlerMixin, ValidationHandlerMixin):
    """Base class for handlers that deal with game operations."""
    pass


class BaseInfoHandler(BaseHandler):
    """Base class for handlers that provide information/status."""
    pass