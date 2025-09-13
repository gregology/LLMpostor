"""
Game State Transition Service for LLMpostor Game

Handles game state management and validation logic.
Extracted from GameManager to follow Single Responsibility Principle.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class GameStateTransitionService:
    """Manages game state transitions and state access."""
    
    def __init__(self, room_manager):
        self.room_manager = room_manager
    
    def get_game_state(self, room_id: str) -> Optional[Dict]:
        """
        Get the current game state for a room.
        
        Args:
            room_id: ID of the room
            
        Returns:
            Game state dict or None if room doesn't exist
        """
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return None
        
        return room["game_state"].copy()
    
    def validate_phase_transition(self, current_phase: str, new_phase: str) -> bool:
        """
        Validate that a phase transition is allowed.
        
        Args:
            current_phase: Current game phase
            new_phase: Requested new phase
            
        Returns:
            True if transition is valid, False otherwise
        """
        valid_transitions = {
            "waiting": ["responding", "waiting"],
            "responding": ["guessing", "waiting", "responding"],
            "guessing": ["results", "responding", "waiting"],
            "results": ["waiting", "responding"]
        }
        
        return new_phase in valid_transitions.get(current_phase, [])
    
    def is_valid_game_state(self, game_state: Dict) -> bool:
        """
        Validate that a game state has all required fields.
        
        Args:
            game_state: Game state to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['phase', 'current_prompt', 'responses', 'guesses', 'round_number']
        
        for field in required_fields:
            if field not in game_state:
                return False
        
        return True
    
    def get_phase_info(self, room_id: str) -> Optional[Dict]:
        """
        Get information about the current phase.
        
        Args:
            room_id: ID of the room
            
        Returns:
            Dict with phase information or None if room doesn't exist
        """
        game_state = self.get_game_state(room_id)
        if not game_state:
            return None
        
        return {
            "phase": game_state["phase"],
            "round_number": game_state["round_number"],
            "phase_start_time": game_state.get("phase_start_time"),
            "phase_duration": game_state.get("phase_duration", 0)
        }