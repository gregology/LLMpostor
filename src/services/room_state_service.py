"""
Room State Service for LLMpostor Game

Handles room state validation, consistency checking, and game state updates.
Extracted from RoomManager to follow Single Responsibility Principle.
"""

import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class RoomStateService:
    """Manages room state validation and game state transitions."""
    
    def __init__(self, room_lifecycle_service, concurrency_control_service):
        self.room_lifecycle_service = room_lifecycle_service
        self.concurrency_control_service = concurrency_control_service
    
    def get_room_state(self, room_id: str) -> Optional[Dict]:
        """
        Get the current state of a room.
        
        Args:
            room_id: ID of the room
            
        Returns:
            Room data dict or None if room doesn't exist
        """
        room = self.room_lifecycle_service.get_room_data(room_id)
        if room:
            return room.copy()
        return None
    
    def validate_room_state_consistency(self, room_id: str) -> bool:
        """Validate that room state is consistent and not corrupted."""
        room = self.room_lifecycle_service.get_room_data(room_id)
        if not room:
            return False
        
        try:
            # Check required fields
            required_fields = ['room_id', 'players', 'game_state', 'created_at', 'last_activity']
            for field in required_fields:
                if field not in room:
                    return False
            
            # Validate game state structure
            game_state = room['game_state']
            required_game_fields = ['phase', 'current_prompt', 'responses', 'guesses', 'round_number']
            for field in required_game_fields:
                if field not in game_state:
                    return False
            
            # Validate player data consistency
            for player_id, player in room['players'].items():
                if not isinstance(player, dict):
                    return False
                if 'player_id' not in player or player['player_id'] != player_id:
                    return False
            
            return True
        except Exception:
            return False
    
    def validate_game_state_transition(self, room: Dict, game_state: Dict, room_id: str) -> bool:
        """Validate that a game state transition is valid."""
        current_phase = room["game_state"].get("phase", "waiting")
        new_phase = game_state.get("phase", current_phase)
        
        # Define valid phase transitions to prevent invalid state changes
        valid_transitions = {
            "waiting": ["responding", "waiting"],
            "responding": ["guessing", "waiting", "responding"],
            "guessing": ["results", "responding", "waiting", "guessing"],
            "results": ["waiting", "responding"]
        }
        
        if new_phase not in valid_transitions.get(current_phase, []):
            logger.warning(f"Invalid game state transition in room {room_id}: {current_phase} -> {new_phase}")
            logger.debug(f"Current room phase: {room['game_state']['phase']}, new game_state phase: {game_state['phase']}")
            return False
        
        # Validate game state consistency
        try:
            required_fields = ['phase', 'current_prompt', 'responses', 'guesses', 'round_number']
            for field in required_fields:
                if field not in game_state:
                    logger.warning(f"Missing required field {field} in game state update for room {room_id}")
                    return False
        except Exception as e:
            logger.error(f"Game state validation error for room {room_id}: {e}")
            return False
        
        return True
    
    def update_room_game_state(self, room: Dict, game_state: Dict) -> None:
        """Update room's game state."""
        room["game_state"] = game_state.copy()
        room["last_activity"] = datetime.now()
    
    def update_game_state(self, room_id: str, game_state: Dict) -> bool:
        """
        Update the game state for a room with race condition protection.
        
        Args:
            room_id: ID of the room
            game_state: New game state dict
            
        Returns:
            True if room was updated, False if room doesn't exist
        """
        with self.concurrency_control_service.room_operation(room_id):
            room = self.room_lifecycle_service.get_room_data(room_id)
            if not room:
                return False
            
            if not self.validate_game_state_transition(room, game_state, room_id):
                return False
            
            self.update_room_game_state(room, game_state)
            
            if not self.validate_room_state_consistency(room_id):
                logger.error(f"Room state became inconsistent after game state update in {room_id}")
                return False
            
            return True
    
    def update_room_activity(self, room_id: str) -> bool:
        """
        Update the last activity timestamp for a room.
        
        Args:
            room_id: ID of the room
            
        Returns:
            True if room was updated, False if room doesn't exist
        """
        with self.concurrency_control_service.room_operation(room_id):
            room = self.room_lifecycle_service.get_room_data(room_id)
            if not room:
                return False
            
            room["last_activity"] = datetime.now()
            return True
    
    def validate_room_consistency(self, room_id: str) -> None:
        """Validate room state consistency, raising ValueError if invalid."""
        if not self.validate_room_state_consistency(room_id):
            raise ValueError(f"Room {room_id} is in an inconsistent state")