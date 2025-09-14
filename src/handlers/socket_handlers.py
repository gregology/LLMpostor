"""
Socket.IO event handlers for the LLMpostor game.

This module provides the main registration function and connection/disconnection handlers
for the new handler architecture using dependency injection and event routing.
"""

import logging
import os
from flask import request
from flask_socketio import emit

from container import get_container
from src.services.error_response_factory import with_error_handling
from .socket_event_router import setup_router, get_router
from .room_connection_handler import RoomConnectionHandler
from .game_action_handler import GameActionHandler
from .game_info_handler import GameInfoHandler

logger = logging.getLogger(__name__)


def register_socket_handlers(socketio_instance, services, config):
    """Register all socket handlers with the SocketIO instance using the new architecture."""

    # Services are already registered via the main container

    # Set up the event router
    router = setup_router(socketio_instance)

    # Create handler instances
    room_handler = RoomConnectionHandler()
    game_handler = GameActionHandler()
    info_handler = GameInfoHandler()

    # Register connection/disconnection handlers directly with socketio
    # (these don't go through the router since they have special behavior)
    socketio_instance.on_event('connect', handle_connect)
    socketio_instance.on_event('disconnect', handle_disconnect)

    # Register room connection handlers with router
    router.register_route('join_room', room_handler.handle_join_room)
    router.register_route('leave_room', room_handler.handle_leave_room)
    router.register_route('get_room_state', room_handler.handle_get_room_state)

    # Register game action handlers with router
    router.register_route('start_round', game_handler.handle_start_round)
    router.register_route('submit_response', game_handler.handle_submit_response)
    router.register_route('submit_guess', game_handler.handle_submit_guess)

    # Register game info handlers with router
    router.register_route('get_round_results', info_handler.handle_get_round_results)
    router.register_route('get_leaderboard', info_handler.handle_get_leaderboard)
    router.register_route('get_time_remaining', info_handler.handle_get_time_remaining)

    # Register all routes with SocketIO
    router.register_with_socketio()

    # Update exported handlers for test compatibility
    _update_exported_handlers(router)

    logger.info(f"Registered {len(router.get_registered_events())} socket event handlers")


def handle_connect(auth=None):
    """Handle client connection with optional Origin enforcement in production."""
    container = get_container()
    app_config = container._get_app_config()
    allowed_origins_env = os.environ.get('SOCKETIO_CORS_ALLOWED_ORIGINS', '')

    origin = request.headers.get('Origin')
    # Enforce Origin in production if a CORS allowlist is configured
    if app_config.is_production:
        if allowed_origins_env:
            allowed = {o.strip() for o in allowed_origins_env.split(',') if o.strip()}
            if origin and origin not in allowed:
                logger.warning(f'Rejecting connection from disallowed Origin: {origin}')
                return False  # Reject the connection
    logger.info(f'Client connected: {request.sid} from Origin: {origin}')
    emit('connected', {'status': 'Connected to LLMpostor server'})


def handle_disconnect(reason=None):
    """Handle client disconnection with game flow cleanup."""
    container = get_container()
    session_service = container.get('SessionService')
    room_manager = container.get('RoomManager')
    auto_flow_service = container.get('AutoGameFlowService')
    broadcast_service = container.get('BroadcastService')

    logger.info(f'Client disconnected: {request.sid}')

    # Handle player leaving room on disconnect
    session_info = session_service.get_session(request.sid)
    if session_info:
        room_id = session_info['room_id']
        player_id = session_info['player_id']
        player_name = session_info['player_name']

        # Mark player as disconnected (preserves scores for reconnection)
        if room_manager.disconnect_player_from_room(room_id, player_id):
            logger.info(f'Player {player_name} ({player_id}) disconnected from room {room_id} (scores preserved)')

            # Check if this affects the current game phase
            auto_flow_service.handle_player_disconnect_game_impact(room_id, player_id)

            # Broadcast updated player list to remaining players
            broadcast_service.broadcast_player_list_update(room_id)
            broadcast_service.broadcast_room_state_update(room_id)

        # Clean up session
        session_service.remove_session(request.sid)


# Export handler functions for backward compatibility with tests
# These are created during registration and stored as globals for test access
handle_join_room = None
handle_leave_room = None
handle_get_room_state = None
handle_start_round = None
handle_submit_response = None
handle_submit_guess = None
handle_get_round_results = None
handle_get_leaderboard = None
handle_get_time_remaining = None


def _update_exported_handlers(router):
    """Update the exported handler functions for test compatibility."""
    global handle_join_room, handle_leave_room, handle_get_room_state
    global handle_start_round, handle_submit_response, handle_submit_guess
    global handle_get_round_results, handle_get_leaderboard, handle_get_time_remaining

    # Create handler instances
    room_handler = RoomConnectionHandler()
    game_handler = GameActionHandler()
    info_handler = GameInfoHandler()

    # Export handler methods for test compatibility
    handle_join_room = room_handler.handle_join_room
    handle_leave_room = room_handler.handle_leave_room
    handle_get_room_state = room_handler.handle_get_room_state
    handle_start_round = game_handler.handle_start_round
    handle_submit_response = game_handler.handle_submit_response
    handle_submit_guess = game_handler.handle_submit_guess
    handle_get_round_results = info_handler.handle_get_round_results
    handle_get_leaderboard = info_handler.handle_get_leaderboard
    handle_get_time_remaining = info_handler.handle_get_time_remaining