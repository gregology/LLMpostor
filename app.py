"""
LLMpostor - A multiplayer guessing game where players try to identify AI-generated responses.
Main Flask application entry point with Socket.IO initialization.
"""

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import logging
import atexit
import time
import threading
from collections import defaultdict, deque
from functools import wraps

# Import error handling utilities (still needed for decorators and validation)
from src.error_handler import ErrorCode, ValidationError, with_error_handling

# Import service container and configuration factory
from container import configure_container, get_container
from config_factory import load_config

# Initialize Flask app
app = Flask(__name__)

# Load configuration using Configuration Factory
app_config = load_config()
from config_factory import ConfigurationFactory
config_factory = ConfigurationFactory()
app.config.update(config_factory.get_flask_config())

# Initialize Socket.IO with CORS enabled for development
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure service container with dependencies
container = configure_container(socketio=socketio, config=config_factory.to_dict())

# Get services from container
room_manager = container.get('RoomManager')
game_manager = container.get('GameManager')
content_manager = container.get('ContentManager')
error_handler = container.get('ErrorHandler')
session_service = container.get('SessionService')
broadcast_service = container.get('BroadcastService')
auto_flow_service = container.get('AutoGameFlowService')

# Event Queue Overflow Prevention System
class EventQueueManager:
    """Manages event queues and prevents overflow/flooding attacks."""
    
    def __init__(self):
        self.client_queues = defaultdict(lambda: deque(maxlen=50))  # Max 50 events per client
        self.client_rates = defaultdict(lambda: deque(maxlen=100))  # Track last 100 events
        self.global_event_count = 0
        self.global_event_window = deque(maxlen=1000)  # Track last 1000 global events
        self.blocked_clients = {}  # Temporarily blocked clients
        self.lock = threading.RLock()
        
        # Rate limiting configuration
        self.max_events_per_second = 10  # Max events per client per second
        self.max_events_per_minute = 100  # Max events per client per minute
        self.global_max_events_per_second = 100  # Global rate limit
        self.block_duration = 60  # Block duration in seconds
    
    def _is_testing(self):
        """Check if we're in a testing environment at runtime"""
        import sys
        return (
            os.environ.get('TESTING') == '1' or 
            'pytest' in os.environ.get('_', '') or
            'pytest' in sys.modules or
            any('pytest' in arg for arg in sys.argv) or
            'test' in sys.argv[0].lower() if sys.argv else False
        )
        
    def is_client_blocked(self, client_id: str) -> bool:
        """Check if a client is currently blocked."""
        with self.lock:
            if client_id in self.blocked_clients:
                if time.time() - self.blocked_clients[client_id] > self.block_duration:
                    del self.blocked_clients[client_id]
                    logger.info(f"Unblocked client {client_id}")
                    return False
                return True
            return False
    
    def block_client(self, client_id: str, reason: str = "Rate limit exceeded"):
        """Block a client for a specified duration."""
        with self.lock:
            self.blocked_clients[client_id] = time.time()
            logger.warning(f"Blocked client {client_id}: {reason}")
    
    def can_process_event(self, client_id: str, event_type: str) -> bool:
        """Check if an event can be processed without causing overflow."""
        # If we're in testing, bypass all rate limiting
        if self._is_testing():
            return True
            
        with self.lock:
            current_time = time.time()
            
            # Check if client is blocked
            if self.is_client_blocked(client_id):
                return False
            
            # Check global rate limit
            self.global_event_window.append(current_time)
            recent_global_events = sum(1 for t in self.global_event_window 
                                     if current_time - t <= 1)
            
            if recent_global_events > self.global_max_events_per_second:
                logger.warning(f"Global rate limit exceeded: {recent_global_events} events/sec")
                return False
            
            # Check client-specific rate limits
            client_events = self.client_rates[client_id]
            client_events.append(current_time)
            
            # Check events per second
            recent_events = sum(1 for t in client_events if current_time - t <= 1)
            if recent_events > self.max_events_per_second:
                self.block_client(client_id, f"Too many events per second: {recent_events}")
                return False
            
            # Check events per minute
            minute_events = sum(1 for t in client_events if current_time - t <= 60)
            if minute_events > self.max_events_per_minute:
                self.block_client(client_id, f"Too many events per minute: {minute_events}")
                return False
            
            # Add to client queue
            queue = self.client_queues[client_id]
            if len(queue) >= queue.maxlen:
                logger.warning(f"Client {client_id} queue near capacity: {len(queue)}")
            
            queue.append({
                'event_type': event_type,
                'timestamp': current_time
            })
            
            self.global_event_count += 1
            return True
    
    def get_queue_stats(self, client_id: str = None) -> dict:
        """Get queue statistics for monitoring."""
        with self.lock:
            if client_id:
                return {
                    'queue_length': len(self.client_queues[client_id]),
                    'recent_events': len(self.client_rates[client_id]),
                    'blocked': self.is_client_blocked(client_id)
                }
            
            return {
                'total_clients': len(self.client_queues),
                'blocked_clients': len(self.blocked_clients),
                'global_event_count': self.global_event_count,
                'global_recent_events': len(self.global_event_window)
            }

# Initialize event queue manager
event_queue_manager = EventQueueManager()

def prevent_event_overflow(event_type: str = "generic"):
    """Decorator to prevent event queue overflow and implement rate limiting."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            client_id = request.sid
            
            # Check if event can be processed (respects the disabled flag for testing)
            if not event_queue_manager.can_process_event(client_id, event_type):
                logger.warning(f"Event {event_type} blocked for client {client_id}")
                emit('error', {
                    'success': False,
                    'error': {
                        'code': ErrorCode.RATE_LIMITED.value,
                        'message': 'Too many requests. Please slow down.',
                        'details': {'retry_after': 60}
                    }
                })
                return
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {event_type} handler: {e}")
                emit('error', {
                    'success': False,
                    'error': {
                        'code': ErrorCode.INTERNAL_ERROR.value,
                        'message': 'An internal error occurred',
                        'details': {}
                    }
                })
        
        return wrapper
    return decorator

# Load prompts on startup
try:
    content_manager.load_prompts_from_yaml()
    logger.info(f"Loaded {content_manager.get_prompt_count()} prompts from YAML")
except Exception as e:
    logger.error(f"Failed to load prompts: {e}")
    # Continue without prompts for now - will handle gracefully

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
    return render_template('game.html', room_id=room_id, max_response_length=error_handler.MAX_RESPONSE_LENGTH)

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

@socketio.on('get_room_state')
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

@socketio.on('start_round')
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
        
        emit('round_started', error_handler.create_success_response({
            'message': 'Round started successfully'
        }))
    else:
        raise ValidationError(
            ErrorCode.START_ROUND_FAILED,
            'Failed to start round'
        )

@socketio.on('submit_response')
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

@socketio.on('submit_guess')
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

# All broadcast functions have been moved to broadcast_service

def cleanup_on_exit():
    """Clean up resources on application exit."""
    logger.info("Shutting down LLMpostor server...")
    auto_flow_service.stop()

atexit.register(cleanup_on_exit)

if __name__ == '__main__':
    # Run the application using configuration
    logger.info(f"Starting LLMpostor server on {app_config.host}:{app_config.port}")
    try:
        socketio.run(app, host=app_config.host, port=app_config.port, debug=app_config.debug)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        cleanup_on_exit()
