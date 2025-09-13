"""
Game Flow Service for LLMpostor Game

Handles game round management, phase transitions, and player submissions.
Extracted from GameManager to follow Single Responsibility Principle.
"""

import logging
import random
from datetime import datetime
from typing import Dict, Optional, Tuple

try:
    from ..core.game_phases import GamePhase
    from ..config.game_settings import get_game_settings
except ImportError:
    from src.core.game_phases import GamePhase
    from src.config.game_settings import get_game_settings

logger = logging.getLogger(__name__)


class GameFlowService:
    """Manages game flow, round management, and phase transitions."""
    
    def __init__(self, room_manager, scoring_service=None):
        self.room_manager = room_manager
        self.scoring_service = scoring_service
        self.game_settings = get_game_settings()
        self.PHASE_DURATIONS = self.game_settings.phase_durations
    
    def start_new_round(self, room_id: str, prompt_data: Dict) -> bool:
        """
        Start a new game round with the given prompt.
        
        Args:
            room_id: ID of the room
            prompt_data: Dict containing prompt info (id, prompt, model, llm_response)
            
        Returns:
            True if round was started, False if room doesn't exist or invalid state
        """
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return False
        
        # Can only start new round from waiting or results phase
        current_phase = room["game_state"]["phase"]
        if current_phase not in ["waiting", "results"]:
            return False
        
        # Update game state for new round
        game_state = room["game_state"]
        game_state["phase"] = GamePhase.RESPONDING.value
        game_state["current_prompt"] = prompt_data
        game_state["responses"] = []
        game_state["guesses"] = {}
        game_state["round_number"] += 1
        game_state["phase_start_time"] = datetime.now()
        game_state["phase_duration"] = self.PHASE_DURATIONS[GamePhase.RESPONDING]
        
        # Update room in manager
        return self.room_manager.update_game_state(room_id, game_state)
    
    def submit_player_response(self, room_id: str, player_id: str, response_text: str) -> bool:
        """
        Submit a player's response for the current round.
        
        Args:
            room_id: ID of the room
            player_id: ID of the player
            response_text: The player's response text
            
        Returns:
            True if response was accepted, False otherwise
        """
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return False
        
        # Check if we're in responding phase
        if room["game_state"]["phase"] != GamePhase.RESPONDING.value:
            return False
        
        # Check if player exists and is connected
        player = room["players"].get(player_id)
        if not player or not player["connected"]:
            return False
        
        # Check if player already submitted a response
        responses = room["game_state"]["responses"]
        if self._player_has_submitted_response(responses, player_id):
            return False
        
        # Add response
        response_data = {
            "text": response_text.strip(),
            "author_id": player_id,
            "is_llm": False
        }
        responses.append(response_data)
        
        # Update room
        success = self.room_manager.update_game_state(room_id, room["game_state"])
        
        # Check if all players have responded
        if success:
            connected_players = self.room_manager.get_connected_players(room_id)
            if len(responses) >= len(connected_players):
                self.advance_to_guessing_phase(room_id)
        
        return success
    
    def submit_player_guess(self, room_id: str, player_id: str, guess_index: int) -> bool:
        """
        Submit a player's guess for which response is the LLM.
        
        Args:
            room_id: ID of the room
            player_id: ID of the player
            guess_index: Index of the response they think is from LLM
            
        Returns:
            True if guess was accepted, False otherwise
        """
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return False
        
        # Check if we're in guessing phase
        if room["game_state"]["phase"] != GamePhase.GUESSING.value:
            return False
        
        # Check if player exists and is connected
        player = room["players"].get(player_id)
        if not player or not player["connected"]:
            return False
        
        # Validate guess index
        responses = room["game_state"]["responses"]
        if guess_index < 0 or guess_index >= len(responses):
            return False
        
        # Check if player already submitted a guess
        if player_id in room["game_state"]["guesses"]:
            return False
        
        # Record guess
        room["game_state"]["guesses"][player_id] = guess_index
        
        # Update room
        success = self.room_manager.update_game_state(room_id, room["game_state"])
        
        # Check if all players have guessed - trigger automatic advancement
        if success:
            connected_players = self.room_manager.get_connected_players(room_id)
            guesses = room["game_state"]["guesses"]
            if len(guesses) >= len(connected_players):
                # All players have guessed, advance to results phase
                if self.scoring_service:
                    results_success = self.advance_to_results_phase(room_id, self.scoring_service)
                    return results_success
        
        return success
    
    def advance_to_guessing_phase(self, room_id: str) -> bool:
        """Advance to guessing phase and add LLM response."""
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return False
        
        # Add LLM response to the mix
        llm_response = {
            "text": room["game_state"]["current_prompt"]["llm_response"],
            "author_id": None,
            "is_llm": True
        }
        room["game_state"]["responses"].append(llm_response)
        
        # Shuffle responses for anonymity
        random.shuffle(room["game_state"]["responses"])
        
        # Update phase
        room["game_state"]["phase"] = GamePhase.GUESSING.value
        room["game_state"]["phase_start_time"] = datetime.now()
        room["game_state"]["phase_duration"] = self.PHASE_DURATIONS[GamePhase.GUESSING]
        room["game_state"]["guesses"] = {}
        
        return self.room_manager.update_game_state(room_id, room["game_state"])
    
    def advance_to_results_phase(self, room_id: str, scoring_service) -> bool:
        """Advance to results phase and calculate scores."""
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return False
        
        # Calculate and update scores using scoring service
        round_scores = scoring_service.calculate_round_scores(room)
        
        # Update phase
        room["game_state"]["phase"] = GamePhase.RESULTS.value
        room["game_state"]["phase_start_time"] = datetime.now()
        room["game_state"]["phase_duration"] = self.PHASE_DURATIONS[GamePhase.RESULTS]
        
        # Update game state in room manager
        game_state_success = self.room_manager.update_game_state(room_id, room["game_state"])
        
        # Update player scores in room manager
        if game_state_success:
            for player_id, player_data in room["players"].items():
                self.room_manager.update_player_score(room_id, player_id, player_data["score"])
        
        return game_state_success
    
    def advance_to_waiting_phase(self, room_id: str) -> bool:
        """Advance to waiting phase for next round."""
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return False
        
        # Reset for next round
        room["game_state"]["phase"] = GamePhase.WAITING.value
        room["game_state"]["current_prompt"] = None
        room["game_state"]["responses"] = []
        room["game_state"]["guesses"] = {}
        room["game_state"]["phase_start_time"] = None
        room["game_state"]["phase_duration"] = 0
        
        return self.room_manager.update_game_state(room_id, room["game_state"])
    
    def advance_game_phase(self, room_id: str, scoring_service=None) -> Optional[str]:
        """
        Manually advance the game phase (used for timeouts).
        
        Args:
            room_id: ID of the room
            scoring_service: Optional scoring service (uses injected one if not provided)
            
        Returns:
            New phase name or None if room doesn't exist
        """
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return None
        
        current_phase = room["game_state"]["phase"]
        
        # Use provided scoring_service or fall back to injected one
        scoring_svc = scoring_service or self.scoring_service
        
        if current_phase == GamePhase.RESPONDING.value:
            if self.advance_to_guessing_phase(room_id):
                return GamePhase.GUESSING.value
        elif current_phase == GamePhase.GUESSING.value:
            if scoring_svc and self.advance_to_results_phase(room_id, scoring_svc):
                return GamePhase.RESULTS.value
        elif current_phase == GamePhase.RESULTS.value:
            if self.advance_to_waiting_phase(room_id):
                return GamePhase.WAITING.value
        
        return current_phase
    
    def can_start_round(self, room_id: str) -> Tuple[bool, str]:
        """
        Check if a new round can be started.
        
        Args:
            room_id: ID of the room
            
        Returns:
            Tuple of (can_start, reason)
        """
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return False, "Room does not exist"
        
        connected_players = self.room_manager.get_connected_players(room_id)
        if len(connected_players) < 2:
            return False, "Need at least 2 players to start"
        
        current_phase = room["game_state"]["phase"]
        if current_phase not in ["waiting", "results"]:
            return False, f"Cannot start round during {current_phase} phase"
        
        return True, "Ready to start"
    
    def is_phase_expired(self, room_id: str) -> bool:
        """
        Check if the current phase has expired based on time limit.
        
        Args:
            room_id: ID of the room
            
        Returns:
            True if phase has expired, False otherwise
        """
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return False
        
        game_state = room["game_state"]
        phase_start = game_state.get("phase_start_time")
        phase_duration = game_state.get("phase_duration", 0)
        
        if not phase_start or phase_duration <= 0:
            return False
        
        elapsed = datetime.now() - phase_start
        return elapsed.total_seconds() >= phase_duration
    
    def get_phase_time_remaining(self, room_id: str) -> int:
        """
        Get remaining time in seconds for the current phase.
        
        Args:
            room_id: ID of the room
            
        Returns:
            Seconds remaining, or 0 if expired or no active phase
        """
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return 0
        
        game_state = room["game_state"]
        phase_start = game_state.get("phase_start_time")
        phase_duration = game_state.get("phase_duration", 0)
        
        if not phase_start or phase_duration <= 0:
            return 0
        
        elapsed = datetime.now() - phase_start
        remaining = phase_duration - elapsed.total_seconds()
        return max(0, int(remaining))
    
    def _player_has_submitted_response(self, responses: list, player_id: str) -> bool:
        """Check if player has already submitted a response."""
        for response in responses:
            if response.get("author_id") == player_id:
                return True
        return False