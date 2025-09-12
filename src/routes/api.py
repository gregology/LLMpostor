"""
REST API endpoints for the LLMpostor application.
"""

import logging
from flask import Blueprint, render_template

logger = logging.getLogger(__name__)

# Global references to services - will be set by registration function
room_manager = None


def create_api_blueprint(services):
    """Create and configure the API Blueprint with service dependencies."""
    global room_manager
    
    # Store service references
    room_manager = services['room_manager']
    
    # Create the blueprint
    api = Blueprint('api', __name__)
    
    @api.route('/')
    def index():
        """Serve the main game interface."""
        return render_template('index.html')

    @api.route('/api/find-available-room')
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

    @api.route('/<room_id>')
    def room(room_id):
        """Serve the game interface for a specific room."""
        # Get max response length from validation service
        from src.services.validation_service import ValidationService
        validation_service = ValidationService()
        max_response_length = validation_service.get_max_response_length()
        return render_template('game.html', room_id=room_id, max_response_length=max_response_length)
    
    return api
