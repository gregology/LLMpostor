"""
Socket.IO event handlers for the LLMpostor game.
"""

import logging
from flask import request
from flask_socketio import emit, join_room, leave_room

from src.error_handler import ErrorCode, ValidationError, with_error_handling
from src.services.rate_limit_service import prevent_event_overflow

logger = logging.getLogger(__name__)

# Global references to services - will be set by registration function
room_manager = None
game_manager = None
content_manager = None
error_handler = None
session_service = None
broadcast_service = None
auto_flow_service = None
app_config = None
allowed_origins_env = None
socketio = None


def register_socket_handlers(socketio_instance, services, config):
    """Register all socket handlers with the SocketIO instance."""
    global room_manager, game_manager, content_manager, error_handler
    global session_service, broadcast_service, auto_flow_service
    global app_config, allowed_origins_env, socketio
    
    # Store service references
    room_manager = services['room_manager']
    game_manager = services['game_manager']
    content_manager = services['content_manager']
    error_handler = services['error_handler']
    session_service = services['session_service']
    broadcast_service = services['broadcast_service']
    auto_flow_service = services['auto_flow_service']
    app_config = config['app_config']
    allowed_origins_env = config['allowed_origins_env']
    socketio = socketio_instance
    
    # Register all handlers
    socketio.on_event('connect', handle_connect)
    socketio.on_event('disconnect', handle_disconnect)
    socketio.on_event('join_room', handle_join_room)
    socketio.on_event('leave_room', handle_leave_room)
    socketio.on_event('get_room_state', handle_get_room_state)
    socketio.on_event('start_round', handle_start_round)
    socketio.on_event('submit_response', handle_submit_response)
    socketio.on_event('submit_guess', handle_submit_guess)
    socketio.on_event('get_round_results', handle_get_round_results)
    socketio.on_event('get_leaderboard', handle_get_leaderboard)
    socketio.on_event('get_time_remaining', handle_get_time_remaining)


def handle_connect():
    """Handle client connection with optional Origin enforcement in production."""
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


def handle_disconnect():
    """Handle client disconnection with game flow cleanup."""
    logger.info(f'Client disconnected: {request.sid}')
    
    # Handle player leaving room on disconnect
    session_info = session_service.get_session(request.sid)
    if session_info:
        room_id = session_info['room_id']
        player_id = session_info['player_id']
        player_name = session_info['player_name']
        
        # Remove player from room
        if room_manager.remove_player_from_room(room_id, player_id):
            logger.info(f'Player {player_name} ({player_id}) removed from room {room_id} due to disconnect')
            
            # Check if this affects the current game phase
            auto_flow_service.handle_player_disconnect_game_impact(room_id, player_id)
            
            # Broadcast updated player list to remaining players
            broadcast_service.broadcast_player_list_update(room_id)
            broadcast_service.broadcast_room_state_update(room_id)
        
        # Clean up session
        session_service.remove_session(request.sid)


@prevent_event_overflow('join_room')
@with_error_handling
def handle_join_room(data):
    """
    Handle player joining a room.
    
    Expected data format:
    {
        'room_id': 'room_name',
        'player_name': 'display_name'
    }
    """
    # Validate input data structure first
    if not isinstance(data, dict):
        raise ValidationError(
            ErrorCode.INVALID_DATA,
            "Invalid data format - expected dictionary"
        )
    
    # Check for specific missing fields to provide better error messages
    if 'room_id' not in data:
        raise ValidationError(
            ErrorCode.MISSING_ROOM_ID,
            "Room ID is required"
        )
    
    if 'player_name' not in data:
        raise ValidationError(
            ErrorCode.MISSING_PLAYER_NAME,
            "Player name is required"
        )
    
    # Validate and sanitize room ID and player name
    room_id = error_handler.validate_room_id(data['room_id'])
    player_name = error_handler.validate_player_name(data['player_name'])
    
    # Check if player is already in a room
    if session_service.has_session(request.sid):
        raise ValidationError(
            ErrorCode.ALREADY_IN_ROOM,
            'You are already in a room. Disconnect first.'
        )
    
    # Add player to room
    try:
        player_data = room_manager.add_player_to_room(room_id, player_name, request.sid)
        
        # Join Socket.IO room for broadcasting
        join_room(room_id)
        
        # Store session info
        session_service.create_session(request.sid, room_id, player_data['player_id'], player_name)
        
        logger.info(f'Player {player_name} ({player_data["player_id"]}) joined room {room_id}')
        
        # Send success response to joining player
        emit('room_joined', error_handler.create_success_response({
            'room_id': room_id,
            'player_id': player_data['player_id'],
            'player_name': player_name,
            'message': f'Successfully joined room {room_id}'
        }))
        
        # Broadcast player list update to all players in room
        broadcast_service.broadcast_player_list_update(room_id)
        
        # Send current room state to joining player
        broadcast_service.send_room_state_to_player(room_id, request.sid)
        
    except ValueError as e:
        # Handle room manager specific errors (e.g., duplicate player name)
        raise ValidationError(
            ErrorCode.PLAYER_NAME_TAKEN,
            str(e)
        )


@with_error_handling
def handle_leave_room(data=None):
    """Handle player leaving their current room."""
    # Check if player is in a room
    session_info = session_service.get_session(request.sid)
    if not session_info:
        raise ValidationError(
            ErrorCode.NOT_IN_ROOM,
            'You are not currently in a room'
        )
    
    room_id = session_info['room_id']
    player_id = session_info['player_id']
    player_name = session_info['player_name']
    
    # Remove player from room
    if room_manager.remove_player_from_room(room_id, player_id):
        # Leave Socket.IO room
        leave_room(room_id)
        
        # Clean up session
        session_service.remove_session(request.sid)
        
        logger.info(f'Player {player_name} ({player_id}) left room {room_id}')
        
        # Send confirmation to leaving player
        emit('room_left', error_handler.create_success_response({
            'message': f'Successfully left room {room_id}'
        }))
        
        # Broadcast updated player list to remaining players
        broadcast_service.broadcast_player_list_update(room_id)
        broadcast_service.broadcast_room_state_update(room_id)
    else:
        raise ValidationError(
            ErrorCode.LEAVE_FAILED,
            'Failed to leave room'
        )


@prevent_event_overflow('get_room_state')
@with_error_handling
def handle_get_room_state(data=None):
    """Handle request for current room state."""
    # Check if player is in a room
    session_info = session_service.get_session(request.sid)
    if not session_info:
        raise ValidationError(
            ErrorCode.NOT_IN_ROOM,
            'You are not currently in a room'
        )
    
    room_id = session_info['room_id']
    broadcast_service.send_room_state_to_player(room_id, request.sid)


@prevent_event_overflow('start_round')
@with_error_handling
def handle_start_round(data=None):
    """
    Handle request to start a new game round.
    Only works if player is in a room and game is in waiting or results phase.
    """
    # Check if player is in a room
    session_info = session_service.get_session(request.sid)
    if not session_info:
        raise ValidationError(
            ErrorCode.NOT_IN_ROOM,
            'You are not currently in a room'
        )
    
    room_id = session_info['room_id']
    
    # Check if round can be started
    can_start, reason = game_manager.can_start_round(room_id)
    if not can_start:
        raise ValidationError(
            ErrorCode.CANNOT_START_ROUND,
            reason
        )
    
    # Check if content manager has prompts loaded
    if not content_manager.is_loaded() or content_manager.get_prompt_count() == 0:
        raise ValidationError(
            ErrorCode.NO_PROMPTS_AVAILABLE,
            'No prompts are available to start a round'
        )
    
    # Get random prompt
    try:
        prompt_data = content_manager.get_random_prompt_response()
        prompt_dict = {
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
    
    # Start the round
    if game_manager.start_new_round(room_id, prompt_dict):
        logger.info(f'Started new round in room {room_id} with prompt {prompt_data.id}')
        
        # Broadcast round start to all players in room
        broadcast_service.broadcast_round_started(room_id)
        broadcast_service.broadcast_room_state_update(room_id)
        
        emit('round_started', error_handler.create_success_response({
            'message': 'Round started successfully'
        }))
    else:
        raise ValidationError(
            ErrorCode.START_ROUND_FAILED,
            'Failed to start round'
        )


@prevent_event_overflow('submit_response')
@with_error_handling
def handle_submit_response(data):
    """
    Handle player response submission during responding phase.
    
    Expected data format:
    {
        'response': 'player response text'
    }
    """
    # Check if player is in a room first
    session_info = session_service.get_session(request.sid)
    if not session_info:
        raise ValidationError(
            ErrorCode.NOT_IN_ROOM,
            'You are not currently in a room'
        )
    
    # Validate input data structure
    if not isinstance(data, dict):
        raise ValidationError(
            ErrorCode.INVALID_DATA,
            "Invalid data format - expected dictionary"
        )
    
    if 'response' not in data:
        raise ValidationError(
            ErrorCode.EMPTY_RESPONSE,
            "Response is required"
        )
    
    # Validate and sanitize response text
    response_text = error_handler.validate_response_text(data['response'])
    
    room_id = session_info['room_id']
    player_id = session_info['player_id']
    
    # Check if game is in responding phase
    game_state = game_manager.get_game_state(room_id)
    if not game_state or game_state['phase'] != 'responding':
        raise ValidationError(
            ErrorCode.WRONG_PHASE,
            'Responses can only be submitted during the responding phase'
        )
    
    # Check if phase has expired
    if game_manager.is_phase_expired(room_id):
        raise ValidationError(
            ErrorCode.PHASE_EXPIRED,
            'Response phase has expired'
        )
    
    # Submit the response
    if game_manager.submit_player_response(room_id, player_id, response_text):
        logger.info(f'Player {player_id} submitted response in room {room_id}')
        
        # Send confirmation to submitting player
        emit('response_submitted', error_handler.create_success_response({
            'message': 'Response submitted successfully'
        }))
        
        # Check if phase changed to guessing (all players responded)
        updated_game_state = game_manager.get_game_state(room_id)
        if updated_game_state and updated_game_state['phase'] == 'guessing':
            # Broadcast guessing phase start
            broadcast_service.broadcast_guessing_phase_started(room_id)
        else:
            # Broadcast response count update to all players (without revealing content)
            broadcast_service.broadcast_response_submitted(room_id)
        
        broadcast_service.broadcast_room_state_update(room_id)
    else:
        raise ValidationError(
            ErrorCode.SUBMIT_FAILED,
            'Failed to submit response. You may have already submitted or the game state has changed.'
        )


@prevent_event_overflow('submit_guess')
@with_error_handling
def handle_submit_guess(data):
    """
    Handle player guess submission during guessing phase.
    
    Expected data format:
    {
        'guess_index': 0  # Index of the response they think is from LLM
    }
    """
    # Check if player is in a room
    session_info = session_service.get_session(request.sid)
    if not session_info:
        raise ValidationError(
            ErrorCode.NOT_IN_ROOM,
            'You are not currently in a room'
        )
    
    room_id = session_info['room_id']
    player_id = session_info['player_id']
    
    # Check if game is in guessing phase first
    game_state = game_manager.get_game_state(room_id)
    if not game_state or game_state['phase'] != 'guessing':
        raise ValidationError(
            ErrorCode.WRONG_PHASE,
            'Guesses can only be submitted during the guessing phase'
        )
    
    # Check if phase has expired
    if game_manager.is_phase_expired(room_id):
        raise ValidationError(
            ErrorCode.PHASE_EXPIRED,
            'Guessing phase has expired'
        )
    
    # Now validate input data structure
    if not isinstance(data, dict):
        raise ValidationError(
            ErrorCode.INVALID_DATA,
            "Invalid data format - expected dictionary"
        )
    
    if 'guess_index' not in data:
        raise ValidationError(
            ErrorCode.MISSING_GUESS,
            "Guess index is required"
        )
    
    # Map the filtered index back to the original response index
    responses = game_state.get('responses', [])
    filtered_responses = [i for i, response in enumerate(responses) if response['author_id'] != player_id]
    
    # Validate guess index against filtered responses
    guess_index = error_handler.validate_guess_index(data['guess_index'], len(filtered_responses))
    
    # Map the filtered index to the actual response index
    actual_response_index = filtered_responses[guess_index]
    
    # Submit the guess with the actual response index
    if game_manager.submit_player_guess(room_id, player_id, actual_response_index):
        logger.info(f'Player {player_id} submitted guess {guess_index} in room {room_id}')
        
        # Send confirmation to submitting player
        emit('guess_submitted', error_handler.create_success_response({
            'message': 'Guess submitted successfully',
            'guess_index': guess_index  # This is the filtered index the player sees
        }))
        
        # Check if phase changed to results (all players guessed)
        updated_game_state = game_manager.get_game_state(room_id)
        if updated_game_state and updated_game_state['phase'] == 'results':
            # Broadcast results phase start
            broadcast_service.broadcast_results_phase_started(room_id)
        else:
            # Broadcast guess count update to all players (without revealing content)
            broadcast_service.broadcast_guess_submitted(room_id)
        
        broadcast_service.broadcast_room_state_update(room_id)
    else:
        raise ValidationError(
            ErrorCode.SUBMIT_GUESS_FAILED,
            'Failed to submit guess. You may have already guessed or the game state has changed.'
        )


def handle_get_round_results(data=None):
    """Handle request for detailed round results."""
    try:
        session_info = session_service.get_session(request.sid)
        if not session_info:
            emit('error', {
                'code': 'NOT_IN_ROOM',
                'message': 'You are not currently in a room'
            })
            return
        
        room_id = session_info['room_id']
        round_results = game_manager.get_round_results(room_id)
        
        if round_results:
            emit('round_results', {
                'success': True,
                'results': round_results
            })
        else:
            emit('error', {
                'code': 'NO_RESULTS_AVAILABLE',
                'message': 'No round results available. Game must be in results phase.'
            })
            
    except Exception as e:
        logger.error(f'Error in get_round_results: {e}')
        emit('error', {
            'code': 'INTERNAL_ERROR',
            'message': 'An internal error occurred'
        })


def handle_get_leaderboard(data=None):
    """Handle request for current leaderboard."""
    try:
        session_info = session_service.get_session(request.sid)
        if not session_info:
            emit('error', {
                'code': 'NOT_IN_ROOM',
                'message': 'You are not currently in a room'
            })
            return
        
        room_id = session_info['room_id']
        leaderboard = game_manager.get_leaderboard(room_id)
        scoring_summary = game_manager.get_scoring_summary(room_id)
        
        emit('leaderboard', {
            'success': True,
            'leaderboard': leaderboard,
            'scoring_summary': scoring_summary
        })
            
    except Exception as e:
        logger.error(f'Error in get_leaderboard: {e}')
        emit('error', {
            'code': 'INTERNAL_ERROR',
            'message': 'An internal error occurred'
        })


@with_error_handling
def handle_get_time_remaining(data=None):
    """Handle request for current phase time remaining."""
    session_info = session_service.get_session(request.sid)
    if not session_info:
        raise ValidationError(
            ErrorCode.NOT_IN_ROOM,
            'You are not currently in a room'
        )
    
    room_id = session_info['room_id']
    time_remaining = game_manager.get_phase_time_remaining(room_id)
    game_state = game_manager.get_game_state(room_id)
    
    if game_state:
        emit('time_remaining', error_handler.create_success_response({
            'time_remaining': time_remaining,
            'phase': game_state['phase'],
            'phase_duration': game_state.get('phase_duration', 0)
        }))
    else:
        raise ValidationError(
            ErrorCode.ROOM_NOT_FOUND,
            'Room not found'
        )