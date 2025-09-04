"""
LLMposter - A multiplayer guessing game where players try to identify AI-generated responses.
Main Flask application entry point with Socket.IO initialization.
"""

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
from datetime import datetime
import logging
import threading
import time

# Import game modules
from src.room_manager import RoomManager
from src.game_manager import GameManager
from src.content_manager import ContentManager
from src.error_handler import ErrorHandler, ErrorCode, ValidationError, with_error_handling

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize Socket.IO with CORS enabled for development
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize game managers
room_manager = RoomManager()
game_manager = GameManager(room_manager)
content_manager = ContentManager()

# Load prompts on startup
try:
    content_manager.load_prompts_from_yaml()
    logger.info(f"Loaded {content_manager.get_prompt_count()} prompts from YAML")
except Exception as e:
    logger.error(f"Failed to load prompts: {e}")
    # Continue without prompts for now - will handle gracefully

# Store player sessions (socket_id -> player_info)
player_sessions = {}

# Automatic game flow management
class AutoGameFlowManager:
    """Manages automatic phase transitions and timing."""
    
    def __init__(self, socketio, game_manager, room_manager):
        self.socketio = socketio
        self.game_manager = game_manager
        self.room_manager = room_manager
        self.running = True
        self.check_interval = 1  # Check every second
        
        # Start background thread for automatic phase management
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()
        
        logger.info("AutoGameFlowManager started")
    
    def stop(self):
        """Stop the automatic game flow manager."""
        self.running = False
        if self.timer_thread.is_alive():
            self.timer_thread.join(timeout=2)
        logger.info("AutoGameFlowManager stopped")
    
    def _timer_loop(self):
        """Main timer loop that checks for phase transitions."""
        last_countdown_broadcast = {}  # room_id -> last_broadcast_time
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check for phase timeouts
                self._check_phase_timeouts()
                
                # Broadcast countdown updates (every 10 seconds for active phases)
                self._broadcast_countdown_updates(current_time, last_countdown_broadcast)
                
                # Clean up inactive rooms (less frequently)
                if int(current_time) % 60 == 0:  # Every minute
                    self._cleanup_inactive_rooms()
                
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in timer loop: {e}")
                time.sleep(self.check_interval)
    
    def _broadcast_countdown_updates(self, current_time: float, last_broadcast: dict):
        """Broadcast countdown updates to active rooms."""
        room_ids = self.room_manager.get_all_rooms()
        
        for room_id in room_ids:
            try:
                # Only broadcast every 10 seconds to avoid spam
                if room_id in last_broadcast and current_time - last_broadcast[room_id] < 10:
                    continue
                
                room_state = self.room_manager.get_room_state(room_id)
                if not room_state:
                    continue
                
                game_state = room_state["game_state"]
                current_phase = game_state["phase"]
                
                # Only broadcast for timed phases
                if current_phase in ["responding", "guessing"]:
                    time_remaining = self.game_manager.get_phase_time_remaining(room_id)
                    
                    # Broadcast countdown update
                    countdown_data = {
                        'phase': current_phase,
                        'time_remaining': time_remaining,
                        'phase_duration': game_state.get('phase_duration', 0)
                    }
                    
                    self.socketio.emit('countdown_update', countdown_data, room=room_id)
                    last_broadcast[room_id] = current_time
                    
                    # Special warnings for low time
                    if time_remaining <= 30 and time_remaining > 25:
                        self.socketio.emit('time_warning', {
                            'message': '30 seconds remaining!',
                            'time_remaining': time_remaining
                        }, room=room_id)
                    elif time_remaining <= 10 and time_remaining > 5:
                        self.socketio.emit('time_warning', {
                            'message': '10 seconds remaining!',
                            'time_remaining': time_remaining
                        }, room=room_id)
                
            except Exception as e:
                logger.error(f"Error broadcasting countdown for room {room_id}: {e}")
    
    def _check_phase_timeouts(self):
        """Check all active rooms for phase timeouts and advance if needed."""
        room_ids = self.room_manager.get_all_rooms()
        
        for room_id in room_ids:
            try:
                if self.game_manager.is_phase_expired(room_id):
                    self._handle_phase_timeout(room_id)
            except Exception as e:
                logger.error(f"Error checking phase timeout for room {room_id}: {e}")
    
    def _handle_phase_timeout(self, room_id: str):
        """Handle phase timeout by advancing to next phase."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                return
            
            current_phase = room_state["game_state"]["phase"]
            logger.info(f"Phase timeout in room {room_id}, current phase: {current_phase}")
            
            # Advance phase
            new_phase = self.game_manager.advance_game_phase(room_id)
            
            if new_phase != current_phase:
                logger.info(f"Advanced room {room_id} from {current_phase} to {new_phase}")
                
                # Broadcast phase change to all players in room
                if new_phase == "guessing":
                    self._broadcast_guessing_phase_started(room_id)
                elif new_phase == "results":
                    self._broadcast_results_phase_started(room_id)
                elif new_phase == "waiting":
                    self._broadcast_round_ended(room_id)
                
                # Always broadcast room state update
                _broadcast_room_state_update(room_id)
                
        except Exception as e:
            logger.error(f"Error handling phase timeout for room {room_id}: {e}")
    
    def _cleanup_inactive_rooms(self):
        """Clean up rooms that have been inactive for too long."""
        try:
            # Clean up rooms inactive for more than 1 hour
            cleaned_count = self.room_manager.cleanup_inactive_rooms(max_inactive_minutes=60)
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} inactive rooms")
        except Exception as e:
            logger.error(f"Error cleaning up inactive rooms: {e}")
    
    def _broadcast_guessing_phase_started(self, room_id: str):
        """Broadcast guessing phase start with timeout notification."""
        try:
            room_state = self.room_manager.get_room_state(room_id)
            if not room_state:
                return
            
            game_state = room_state['game_state']
            
            guessing_info = {
                'phase': 'guessing',
                'responses': [],
                'round_number': game_state['round_number'],
                'phase_duration': game_state['phase_duration'],
                'time_remaining': self.game_manager.get_phase_time_remaining(room_id),
                'timeout_reason': 'Response time expired'
            }
            
            # Add anonymized responses
            for i, response in enumerate(game_state['responses']):
                guessing_info['responses'].append({
                    'index': i,
                    'text': response['text']
                })
            
            self.socketio.emit('guessing_phase_started', guessing_info, room=room_id)
            logger.debug(f'Broadcasted guessing phase start (timeout) to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting guessing phase start: {e}')
    
    def _broadcast_results_phase_started(self, room_id: str):
        """Broadcast results phase start with timeout notification."""
        try:
            round_results = self.game_manager.get_round_results(room_id)
            leaderboard = self.game_manager.get_leaderboard(room_id)
            
            if round_results:
                results_info = {
                    'phase': 'results',
                    'round_results': round_results,
                    'leaderboard': leaderboard,
                    'timeout_reason': 'Guessing time expired'
                }
                
                self.socketio.emit('results_phase_started', results_info, room=room_id)
                
                # Broadcast updated player list with new scores
                _broadcast_player_list_update(room_id)
                
                logger.debug(f'Broadcasted results phase start (timeout) to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting results phase start: {e}')
    
    def _broadcast_round_ended(self, room_id: str):
        """Broadcast round end notification."""
        try:
            self.socketio.emit('round_ended', {
                'phase': 'waiting',
                'message': 'Round completed. Ready for next round.'
            }, room=room_id)
            logger.debug(f'Broadcasted round end to room {room_id}')
            
        except Exception as e:
            logger.error(f'Error broadcasting round end: {e}')

# Initialize automatic game flow manager
auto_flow_manager = AutoGameFlowManager(socketio, game_manager, room_manager)

@app.route('/')
def index():
    """Serve the main game interface."""
    return render_template('index.html')

@app.route('/<room_id>')
def room(room_id):
    """Serve the game interface for a specific room."""
    return render_template('game.html', room_id=room_id)

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info(f'Client connected: {request.sid}')
    emit('connected', {'status': 'Connected to LLMposter server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection with game flow cleanup."""
    logger.info(f'Client disconnected: {request.sid}')
    
    # Handle player leaving room on disconnect
    session_info = player_sessions.get(request.sid)
    if session_info:
        room_id = session_info['room_id']
        player_id = session_info['player_id']
        player_name = session_info['player_name']
        
        # Remove player from room
        if room_manager.remove_player_from_room(room_id, player_id):
            logger.info(f'Player {player_name} ({player_id}) removed from room {room_id} due to disconnect')
            
            # Check if this affects the current game phase
            _handle_player_disconnect_game_impact(room_id, player_id)
            
            # Broadcast updated player list to remaining players
            _broadcast_player_list_update(room_id)
            _broadcast_room_state_update(room_id)
        
        # Clean up session
        del player_sessions[request.sid]

def _handle_player_disconnect_game_impact(room_id: str, disconnected_player_id: str):
    """Handle the impact of player disconnection on game flow."""
    try:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            logger.warning(f"Room {room_id} not found during disconnect handling")
            return
        
        game_state = room_state.get("game_state", {})
        current_phase = game_state.get("phase", "waiting")
        
        try:
            connected_players = room_manager.get_connected_players(room_id)
        except Exception as e:
            logger.error(f"Error getting connected players for room {room_id}: {e}")
            connected_players = []
        
        logger.info(f"Handling disconnect impact for player {disconnected_player_id} in room {room_id}, "
                   f"phase: {current_phase}, remaining players: {len(connected_players)}")
        
        # If only one player left, reset to waiting phase
        if len(connected_players) < 2:
            if current_phase != "waiting":
                logger.info(f"Resetting room {room_id} to waiting phase due to insufficient players")
                # Force reset to waiting phase
                room_state["game_state"]["phase"] = "waiting"
                room_state["game_state"]["current_prompt"] = None
                room_state["game_state"]["responses"] = []
                room_state["game_state"]["guesses"] = {}
                room_state["game_state"]["phase_start_time"] = None
                room_state["game_state"]["phase_duration"] = 0
                room_manager.update_game_state(room_id, room_state["game_state"])
                _broadcast_room_state_update(room_id)
                
                # Notify remaining players with detailed message
                socketio.emit('game_paused', ErrorHandler.create_error_response(
                    ErrorCode.INSUFFICIENT_PLAYERS,
                    'Game paused - need at least 2 players to continue',
                    {
                        'reason': 'player_disconnect',
                        'disconnected_player': disconnected_player_id,
                        'remaining_players': len(connected_players)
                    }
                ), room=room_id)
            return
        
        # Check if we can auto-advance phases due to disconnection
        if current_phase == "responding":
            # Check if all remaining connected players have submitted responses
            responses = game_state.get("responses", [])
            submitted_players = {r["author_id"] for r in responses if r.get("author_id")}
            connected_player_ids = {p["player_id"] for p in connected_players if "player_id" in p}
            
            logger.debug(f"Response phase check - submitted: {len(submitted_players)}, "
                        f"connected: {len(connected_player_ids)}")
            
            if submitted_players.issuperset(connected_player_ids):
                logger.info(f"Auto-advancing room {room_id} to guessing phase after disconnect")
                new_phase = game_manager.advance_game_phase(room_id)
                if new_phase == "guessing":
                    _broadcast_guessing_phase_started(room_id)
                _broadcast_room_state_update(room_id)
                
                # Notify players about auto-advance
                socketio.emit('phase_auto_advanced', {
                    'message': 'Moving to guessing phase - all remaining players have responded',
                    'new_phase': new_phase,
                    'reason': 'player_disconnect'
                }, room=room_id)
        
        elif current_phase == "guessing":
            try:
                # Check if all remaining connected players have submitted guesses
                guesses = game_state.get("guesses", {})
                if not isinstance(guesses, dict):
                    guesses = {}
                
                connected_player_ids = set()
                for p in connected_players:
                    if isinstance(p, dict) and "player_id" in p:
                        connected_player_ids.add(p["player_id"])
                
                # Remove any guesses from the disconnected player
                if disconnected_player_id in guesses:
                    logger.info(f"Removing guess from disconnected player {disconnected_player_id}")
                    del guesses[disconnected_player_id]
                    game_state["guesses"] = guesses
                    room_manager.update_game_state(room_id, game_state)
                
                guessed_players = set(guesses.keys()) if guesses else set()
                
                logger.debug(f"Guessing phase check - guessed: {len(guessed_players)}, "
                            f"connected: {len(connected_player_ids)}")
                
                if guessed_players.issuperset(connected_player_ids) and len(connected_player_ids) > 0:
                    logger.info(f"Auto-advancing room {room_id} to results phase after disconnect")
                    new_phase = game_manager.advance_game_phase(room_id)
                    if new_phase == "results":
                        _broadcast_results_phase_started(room_id)
                    _broadcast_room_state_update(room_id)
                    
                    # Notify players about auto-advance
                    socketio.emit('phase_auto_advanced', {
                        'message': 'Moving to results - all remaining players have guessed',
                        'new_phase': new_phase,
                        'reason': 'player_disconnect'
                    }, room=room_id)
            except Exception as e:
                logger.error(f"Error in guessing phase disconnect handling: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Don't raise to prevent the disconnect from failing completely
                pass
        
        # Broadcast player disconnect notification to remaining players
        socketio.emit('player_disconnected', {
            'message': f'A player has disconnected',
            'remaining_players': len(connected_players),
            'phase': current_phase
        }, room=room_id)
        
    except Exception as e:
        logger.error(f"Error handling player disconnect impact: {e}")
        ErrorHandler.log_error_context(
            "Player disconnect handling",
            room_id=room_id,
            disconnected_player_id=disconnected_player_id,
            error=str(e)
        )

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
    if request.sid in player_sessions:
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
        player_sessions[request.sid] = {
            'room_id': room_id,
            'player_id': player_data['player_id'],
            'player_name': player_name
        }
        
        logger.info(f'Player {player_name} ({player_data["player_id"]}) joined room {room_id}')
        
        # Send success response to joining player
        emit('room_joined', ErrorHandler.create_success_response({
            'room_id': room_id,
            'player_id': player_data['player_id'],
            'player_name': player_name,
            'message': f'Successfully joined room {room_id}'
        }))
        
        # Broadcast player list update to all players in room
        _broadcast_player_list_update(room_id)
        
        # Send current room state to joining player
        _send_room_state_to_player(room_id, request.sid)
        
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
    session_info = player_sessions.get(request.sid)
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
        del player_sessions[request.sid]
        
        logger.info(f'Player {player_name} ({player_id}) left room {room_id}')
        
        # Send confirmation to leaving player
        emit('room_left', ErrorHandler.create_success_response({
            'message': f'Successfully left room {room_id}'
        }))
        
        # Broadcast updated player list to remaining players
        _broadcast_player_list_update(room_id)
        _broadcast_room_state_update(room_id)
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
    session_info = player_sessions.get(request.sid)
    if not session_info:
        raise ValidationError(
            ErrorCode.NOT_IN_ROOM,
            'You are not currently in a room'
        )
    
    room_id = session_info['room_id']
    _send_room_state_to_player(room_id, request.sid)

@socketio.on('start_round')
@with_error_handling
def handle_start_round(data=None):
    """
    Handle request to start a new game round.
    Only works if player is in a room and game is in waiting or results phase.
    """
    # Check if player is in a room
    session_info = player_sessions.get(request.sid)
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
        _broadcast_round_started(room_id)
        _broadcast_room_state_update(room_id)
        
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
    session_info = player_sessions.get(request.sid)
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
            _broadcast_guessing_phase_started(room_id)
        else:
            # Broadcast response count update to all players (without revealing content)
            _broadcast_response_submitted(room_id)
        
        _broadcast_room_state_update(room_id)
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
    session_info = player_sessions.get(request.sid)
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
            _broadcast_results_phase_started(room_id)
        else:
            # Broadcast guess count update to all players (without revealing content)
            _broadcast_guess_submitted(room_id)
        
        _broadcast_room_state_update(room_id)
    else:
        raise ValidationError(
            ErrorCode.SUBMIT_GUESS_FAILED,
            'Failed to submit guess. You may have already guessed or the game state has changed.'
        )

@socketio.on('get_round_results')
def handle_get_round_results(data=None):
    """Handle request for detailed round results."""
    try:
        session_info = player_sessions.get(request.sid)
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
        session_info = player_sessions.get(request.sid)
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
    session_info = player_sessions.get(request.sid)
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

def _broadcast_player_list_update(room_id: str):
    """Broadcast updated player list to all players in room."""
    try:
        players = room_manager.get_room_players(room_id)
        connected_players = room_manager.get_connected_players(room_id)
        
        # Prepare player list data (without sensitive info)
        player_list = []
        for player in players:
            player_list.append({
                'player_id': player['player_id'],
                'name': player['name'],
                'score': player['score'],
                'connected': player['connected']
            })
        
        socketio.emit('player_list_updated', {
            'players': player_list,
            'connected_count': len(connected_players),
            'total_count': len(players)
        }, room=room_id)
        
        logger.debug(f'Broadcasted player list update to room {room_id}')
        
    except Exception as e:
        logger.error(f'Error broadcasting player list update: {e}')

def _broadcast_room_state_update(room_id: str):
    """Broadcast current room state to all players in room."""
    try:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return
        
        game_state = room_state['game_state']
        
        # Prepare safe game state data (hide sensitive info during certain phases)
        safe_game_state = {
            'phase': game_state['phase'],
            'round_number': game_state['round_number'],
            'phase_start_time': game_state['phase_start_time'].isoformat() if game_state['phase_start_time'] else None,
            'phase_duration': game_state['phase_duration']
        }
        
        # Add phase-specific data
        if game_state['phase'] in ['responding', 'guessing', 'results']:
            if game_state['current_prompt']:
                safe_game_state['current_prompt'] = {
                    'id': game_state['current_prompt']['id'],
                    'prompt': game_state['current_prompt']['prompt'],
                    'model': game_state['current_prompt']['model']
                }
        
        if game_state['phase'] == 'responding':
            # Show response count and time remaining during responding phase
            safe_game_state['response_count'] = len(game_state['responses'])
            safe_game_state['time_remaining'] = game_manager.get_phase_time_remaining(room_id)
        
        if game_state['phase'] == 'results':
            # Show responses (with authorship revealed in results phase)
            safe_game_state['responses'] = []
            for i, response in enumerate(game_state['responses']):
                response_data = {
                    'index': i,
                    'text': response['text'],
                    'is_llm': response['is_llm']
                }
                if not response['is_llm']:
                    # Find player name for human responses
                    author_id = response['author_id']
                    players = room_state['players']
                    if author_id in players:
                        response_data['author_name'] = players[author_id]['name']
                
                safe_game_state['responses'].append(response_data)
        
        if game_state['phase'] == 'guessing':
            # Show guess count and time remaining during guessing phase
            safe_game_state['guess_count'] = len(game_state['guesses'])
            safe_game_state['time_remaining'] = game_manager.get_phase_time_remaining(room_id)
        
        if game_state['phase'] == 'results':
            # Show guessing results and detailed round results
            safe_game_state['guesses'] = {}
            players = room_state['players']
            for player_id, guess_index in game_state['guesses'].items():
                if player_id in players:
                    player_name = players[player_id]['name']
                    safe_game_state['guesses'][player_name] = guess_index
            
            # Include detailed round results
            round_results = game_manager.get_round_results(room_id)
            if round_results:
                safe_game_state['round_results'] = round_results
        
        # During guessing phase, send personalized room states (excluding own responses)
        if game_state['phase'] == 'guessing':
            for player_id in room_state['players']:
                player = room_state['players'][player_id]
                if not player.get('connected', False):
                    continue
                
                # Create personalized game state for this player
                personalized_game_state = safe_game_state.copy()
                personalized_game_state['responses'] = []
                
                # Filter out this player's own response
                for i, response in enumerate(game_state['responses']):
                    if response['author_id'] != player_id:
                        personalized_game_state['responses'].append({
                            'index': i,
                            'text': response['text']
                        })
                
                socketio.emit('room_state_updated', personalized_game_state, room=player['socket_id'])
        else:
            # For all other phases, broadcast normally
            socketio.emit('room_state_updated', safe_game_state, room=room_id)
        
        logger.debug(f'Broadcasted room state update to room {room_id}')
        
    except Exception as e:
        logger.error(f'Error broadcasting room state update: {e}')

def _send_room_state_to_player(room_id: str, socket_id: str):
    """Send current room state to a specific player."""
    try:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            socketio.emit('error', {
                'code': 'ROOM_NOT_FOUND',
                'message': 'Room not found'
            }, room=socket_id)
            return
        
        # Get player list
        players = room_manager.get_room_players(room_id)
        connected_players = room_manager.get_connected_players(room_id)
        
        player_list = []
        for player in players:
            player_list.append({
                'player_id': player['player_id'],
                'name': player['name'],
                'score': player['score'],
                'connected': player['connected']
            })
        
        # Get game state
        game_state = room_state['game_state']
        safe_game_state = {
            'phase': game_state['phase'],
            'round_number': game_state['round_number'],
            'phase_start_time': game_state['phase_start_time'].isoformat() if game_state['phase_start_time'] else None,
            'phase_duration': game_state['phase_duration']
        }
        
        # Add phase-specific data
        if game_state['phase'] in ['responding', 'guessing', 'results']:
            if game_state['current_prompt']:
                safe_game_state['current_prompt'] = {
                    'id': game_state['current_prompt']['id'],
                    'prompt': game_state['current_prompt']['prompt'],
                    'model': game_state['current_prompt']['model']
                }
        
        if game_state['phase'] in ['responding']:
            # Show response count without revealing content
            safe_game_state['response_count'] = len(game_state['responses'])
            safe_game_state['time_remaining'] = game_manager.get_phase_time_remaining(room_id)
        
        # Get leaderboard for room state
        leaderboard = game_manager.get_leaderboard(room_id)
        
        # Send comprehensive room state
        socketio.emit('room_state', {
            'room_id': room_id,
            'players': player_list,
            'connected_count': len(connected_players),
            'total_count': len(players),
            'game_state': safe_game_state,
            'leaderboard': leaderboard
        }, room=socket_id)
        
        logger.debug(f'Sent room state to player {socket_id} in room {room_id}')
        
    except Exception as e:
        logger.error(f'Error sending room state to player: {e}')

def _broadcast_round_started(room_id: str):
    """Broadcast round start notification to all players in room."""
    try:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return
        
        game_state = room_state['game_state']
        if game_state['current_prompt']:
            prompt_info = {
                'id': game_state['current_prompt']['id'],
                'prompt': game_state['current_prompt']['prompt'],
                'model': game_state['current_prompt']['model'],
                'round_number': game_state['round_number'],
                'phase_duration': game_state['phase_duration']
            }
            
            socketio.emit('round_started', prompt_info, room=room_id)
            logger.debug(f'Broadcasted round start to room {room_id}')
        
    except Exception as e:
        logger.error(f'Error broadcasting round start: {e}')

def _broadcast_response_submitted(room_id: str):
    """Broadcast response submission notification to all players in room."""
    try:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return
        
        game_state = room_state['game_state']
        connected_players = room_manager.get_connected_players(room_id)
        
        response_info = {
            'response_count': len(game_state['responses']),
            'total_players': len(connected_players),
            'time_remaining': game_manager.get_phase_time_remaining(room_id)
        }
        
        socketio.emit('response_submitted', response_info, room=room_id)
        logger.debug(f'Broadcasted response submission to room {room_id}')
        
    except Exception as e:
        logger.error(f'Error broadcasting response submission: {e}')

def _broadcast_guess_submitted(room_id: str):
    """Broadcast guess submission notification to all players in room."""
    try:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return
        
        game_state = room_state['game_state']
        connected_players = room_manager.get_connected_players(room_id)
        
        guess_info = {
            'guess_count': len(game_state['guesses']),
            'total_players': len(connected_players),
            'time_remaining': game_manager.get_phase_time_remaining(room_id)
        }
        
        socketio.emit('guess_submitted', guess_info, room=room_id)
        logger.debug(f'Broadcasted guess submission to room {room_id}')
        
    except Exception as e:
        logger.error(f'Error broadcasting guess submission: {e}')

def _broadcast_guessing_phase_started(room_id: str):
    """Broadcast guessing phase start notification to all players in room."""
    try:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return
        
        game_state = room_state['game_state']
        
        # Send personalized responses to each player (excluding their own response)
        for player_id in room_state['players']:
            player = room_state['players'][player_id]
            if not player.get('connected', False):
                continue
                
            # Filter out this player's own response
            filtered_responses = []
            for i, response in enumerate(game_state['responses']):
                if response['author_id'] != player_id:
                    filtered_responses.append({
                        'index': i,
                        'text': response['text']
                    })
            
            guessing_info = {
                'phase': 'guessing',
                'responses': filtered_responses,
                'round_number': game_state['round_number'],
                'phase_duration': game_state['phase_duration'],
                'time_remaining': game_manager.get_phase_time_remaining(room_id)
            }
            
            socketio.emit('guessing_phase_started', guessing_info, room=player['socket_id'])
        
        logger.debug(f'Broadcasted guessing phase start to room {room_id}')
        
    except Exception as e:
        logger.error(f'Error broadcasting guessing phase start: {e}')

def _broadcast_results_phase_started(room_id: str):
    """Broadcast results phase start notification to all players in room."""
    try:
        # Get comprehensive round results
        round_results = game_manager.get_round_results(room_id)
        if not round_results:
            return
        
        # Get updated leaderboard
        leaderboard = game_manager.get_leaderboard(room_id)
        
        # Get scoring summary
        scoring_summary = game_manager.get_scoring_summary(room_id)
        
        results_info = {
            'phase': 'results',
            'round_results': round_results,
            'leaderboard': leaderboard,
            'scoring_summary': scoring_summary,
            'phase_duration': 30  # Results phase duration
        }
        
        socketio.emit('results_phase_started', results_info, room=room_id)
        
        # Broadcast updated player list with new scores
        _broadcast_player_list_update(room_id)
        
        logger.debug(f'Broadcasted results phase start to room {room_id}')
        
    except Exception as e:
        logger.error(f'Error broadcasting results phase start: {e}')

def cleanup_on_exit():
    """Clean up resources on application exit."""
    logger.info("Shutting down LLMposter server...")
    auto_flow_manager.stop()

import atexit
atexit.register(cleanup_on_exit)

if __name__ == '__main__':
    # Run the application
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Starting LLMposter server on port {port}")
    try:
        socketio.run(app, host='0.0.0.0', port=port, debug=debug)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        cleanup_on_exit()
