"""
LLMposter - A multiplayer guessing game where players try to identify AI-generated responses.
Main Flask application entry point with Socket.IO initialization.
"""

from flask import Flask, render_template, request
from flask_socketio import SocketIO
import os
from datetime import datetime
import logging
import time

# Import game modules
from src.room_manager import RoomManager
from src.game_manager import GameManager
from src.content_manager import ContentManager
from src.error_handler import ErrorHandler, ErrorCode, ValidationError, with_error_handling
from src.auto_game_flow_manager import AutoGameFlowManager
from config import config
from src.socket_handlers import register_handlers
from src.broadcast_manager import BroadcastManager
from src.session_manager import SessionManager

# Initialize Flask app
app = Flask(__name__)
config_name = os.getenv('FLASK_ENV', 'development')
app.config.from_object(config[config_name])


# Initialize Socket.IO with CORS enabled for development
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize game managers
room_manager = RoomManager()
game_manager = GameManager(room_manager, broadcast_manager)
content_manager = ContentManager()
session_manager = SessionManager()

# Initialize broadcast manager
broadcast_manager = BroadcastManager(socketio, room_manager, game_manager)

# Register Socket.IO handlers
register_handlers(socketio, app, room_manager, game_manager, content_manager, session_manager, broadcast_manager)

# Initialize automatic game flow manager
auto_flow_manager = AutoGameFlowManager(socketio, game_manager, room_manager, broadcast_manager)

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
