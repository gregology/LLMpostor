"""
LLMpostor - A multiplayer guessing game where players try to identify AI-generated responses.
Main Flask application entry point with Socket.IO initialization.
"""

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import logging
import atexit

# Import game modules
from src.room_manager import RoomManager
from src.game_manager import GameManager
from src.content_manager import ContentManager
from src.error_handler import ErrorHandler, ErrorCode, ValidationError, with_error_handling

# Import services
from src.services.broadcast_service import BroadcastService
from src.services.session_service import SessionService
from src.services.auto_game_flow_service import AutoGameFlowService

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize Socket.IO with CORS enabled for development
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize game managers
room_manager = RoomManager()
game_manager = GameManager(room_manager)
content_manager = ContentManager()
error_handler = ErrorHandler()

# Initialize services
session_service = SessionService()
broadcast_service = BroadcastService(socketio, room_manager, game_manager, error_handler)

# Load prompts on startup
try:
    content_manager.load_prompts_from_yaml()
    logger.info(f"Loaded {content_manager.get_prompt_count()} prompts from YAML")
except Exception as e:
    logger.error(f"Failed to load prompts: {e}")
    # Continue without prompts for now - will handle gracefully

# Session management is now handled by session_service

# Initialize auto game flow service
auto_flow_service = AutoGameFlowService(broadcast_service, game_manager, room_manager)

@app.route('/')
def index():
    """Serve the main game interface."""
    return render_template('index.html')

@app.route('/api/find-available-room')
def find_available_room():
    """Find a room that's waiting for players."""
    try:
        room_ids = room_manager.get_all_rooms()
        
        for room_id in room_ids:
            room_state = room_manager.get_room_state(room_id)
            if (room_state and 
                room_state.get('game_state', {}).get('phase') == 'waiting' and 
                len(room_state.get('players', {})) >= 1 and  # Has at least 1 player
                len(room_state.get('players', {})) < 8):     # But not full
                logger.info(f'Found available room: {room_id} with {len(room_state.get("players", {}))} players')
                return {'room_id': room_id}
        
        # No available rooms found
        return {'room_id': None}
    except Exception as e:
        logger.error(f'Error finding available room: {e}')
        return {'room_id': None}

@app.route('/<room_id>')
def room(room_id):
    """Serve the game interface for a specific room."""
    from src.error_handler import ErrorHandler
    return render_template('game.html', room_id=room_id, max_response_length=ErrorHandler.MAX_RESPONSE_LENGTH)

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info(f'Client connected: {request.sid}')
    emit('connected', {'status': 'Connected to LLMpostor server'})

@socketio.on('disconnect')
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

# Player disconnect game impact handling is now in auto_flow_service

@socketio.on('join_room')
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
    room_id = ErrorHandler.validate_room_id(data['room_id'])
    player_name = ErrorHandler.validate_player_name(data['player_name'])
    
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
        emit('room_joined', ErrorHandler.create_success_response({
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

@socketio.on('leave_room')
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
        emit('room_left', ErrorHandler.create_success_response({
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

@socketio.on('get_room_state')
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

@socketio.on('start_round')
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
            'llm_response': prompt_data.response
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
        
        emit('round_started', ErrorHandler.create_success_response({
            'message': 'Round started successfully'
        }))
    else:
        raise ValidationError(
            ErrorCode.START_ROUND_FAILED,
            'Failed to start round'
        )

@socketio.on('submit_response')
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
    response_text = ErrorHandler.validate_response_text(data['response'])
    
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
        emit('response_submitted', ErrorHandler.create_success_response({
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

@socketio.on('submit_guess')
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
    guess_index = ErrorHandler.validate_guess_index(data['guess_index'], len(filtered_responses))
    
    # Map the filtered index to the actual response index
    actual_response_index = filtered_responses[guess_index]
    
    # Submit the guess with the actual response index
    if game_manager.submit_player_guess(room_id, player_id, actual_response_index):
        logger.info(f'Player {player_id} submitted guess {guess_index} in room {room_id}')
        
        # Send confirmation to submitting player
        emit('guess_submitted', ErrorHandler.create_success_response({
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

@socketio.on('get_round_results')
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

@socketio.on('get_leaderboard')
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

@socketio.on('get_time_remaining')
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
        emit('time_remaining', ErrorHandler.create_success_response({
            'time_remaining': time_remaining,
            'phase': game_state['phase'],
            'phase_duration': game_state.get('phase_duration', 0)
        }))
    else:
        raise ValidationError(
            ErrorCode.ROOM_NOT_FOUND,
            'Room not found'
        )

# All broadcast functions have been moved to broadcast_service

def cleanup_on_exit():
    """Clean up resources on application exit."""
    logger.info("Shutting down LLMpostor server...")
    auto_flow_service.stop()

atexit.register(cleanup_on_exit)

if __name__ == '__main__':
    # Run the application
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Starting LLMpostor server on port {port}")
    try:
        socketio.run(app, host='0.0.0.0', port=port, debug=debug)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        cleanup_on_exit()
