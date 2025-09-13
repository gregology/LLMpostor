"""
Room Connection Handler

This module handles Socket.IO events related to room connections,
including joining rooms, leaving rooms, and getting room state.
"""

import logging
from flask import request

from src.core.errors import ErrorCode, ValidationError
from src.services.error_response_factory import with_error_handling
from src.services.rate_limit_service import prevent_event_overflow
from .base_handler import BaseRoomHandler

logger = logging.getLogger(__name__)


class RoomConnectionHandler(BaseRoomHandler):
    """Handler for room connection operations like join, leave, and state retrieval."""

    @prevent_event_overflow('join_room')
    @with_error_handling
    def handle_join_room(self, data):
        """
        Handle player joining a room.

        Expected data format:
        {
            'room_id': 'room_name',
            'player_name': 'display_name'
        }
        """
        self.log_handler_start('handle_join_room', data)

        # Validate and extract data
        room_id, player_name = self.validate_room_join_data(data)

        # Check if player is already in a room
        if self.session_service.has_session(request.sid):
            raise ValidationError(
                ErrorCode.ALREADY_IN_ROOM,
                'You are already in a room. Disconnect first.'
            )

        # Add player to room
        try:
            player_data = self.room_manager.add_player_to_room(room_id, player_name, request.sid)

            # Join Socket.IO room for broadcasting
            self.join_socketio_room(room_id)

            # Store session info
            self.session_service.create_session(request.sid, room_id, player_data['player_id'], player_name)

            self.log_handler_success(
                'handle_join_room',
                f'Player {player_name} ({player_data["player_id"]}) joined room {room_id}'
            )

            # Send success response to joining player
            self.emit_success('room_joined', {
                'room_id': room_id,
                'player_id': player_data['player_id'],
                'player_name': player_name,
                'message': f'Successfully joined room {room_id}'
            })

            # Broadcast player list update to all players in room
            self.broadcast_service.broadcast_player_list_update(room_id)

            # Send current room state to joining player
            self.broadcast_service.send_room_state_to_player(room_id, request.sid)

        except ValueError as e:
            # Handle room manager specific errors (e.g., duplicate player name)
            raise ValidationError(
                ErrorCode.PLAYER_NAME_TAKEN,
                str(e)
            )

    @with_error_handling
    def handle_leave_room(self, data=None):
        """Handle player leaving their current room."""
        self.log_handler_start('handle_leave_room', data)

        # Check if player is in a room
        session_info = self.require_session()

        room_id = session_info['room_id']
        player_id = session_info['player_id']
        player_name = session_info['player_name']

        # Remove player from room
        if self.room_manager.remove_player_from_room(room_id, player_id):
            # Leave Socket.IO room
            self.leave_socketio_room(room_id)

            # Clean up session
            self.session_service.remove_session(request.sid)

            self.log_handler_success(
                'handle_leave_room',
                f'Player {player_name} ({player_id}) left room {room_id}'
            )

            # Send confirmation to leaving player
            self.emit_success('room_left', {
                'message': f'Successfully left room {room_id}'
            })

            # Broadcast updated player list to remaining players
            self.broadcast_service.broadcast_player_list_update(room_id)
            self.broadcast_service.broadcast_room_state_update(room_id)
        else:
            raise ValidationError(
                ErrorCode.LEAVE_FAILED,
                'Failed to leave room'
            )

    @prevent_event_overflow('get_room_state')
    @with_error_handling
    def handle_get_room_state(self, data=None):
        """Handle request for current room state."""
        self.log_handler_start('handle_get_room_state', data)

        # Check if player is in a room
        session_info = self.require_session()
        room_id = session_info['room_id']

        # Send room state to requesting player
        self.broadcast_service.send_room_state_to_player(room_id, request.sid)

        self.log_handler_success('handle_get_room_state')