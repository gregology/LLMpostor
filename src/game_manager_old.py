"""
Game Manager for LLMpostor Game

Handles game state transitions, scoring logic, and game flow.
Works with RoomManager to manage game sessions.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
import random

try:
    from .room_manager import RoomManager
    from .config.game_settings import get_game_settings
    from .core.game_phases import GamePhase
except ImportError:
    from room_manager import RoomManager
    from src.config.game_settings import get_game_settings
    from src.core.game_phases import GamePhase


class GameManager:
    """Manages game state transitions and scoring logic."""
    
    def __init__(self, room_manager: RoomManager):
        self.room_manager = room_manager
        self.game_settings = get_game_settings()
        
        # Phase durations from configuration
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
        self.room_manager.update_game_state(room_id, game_state)
        return True
    
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
        for response in responses:
            if response.get("author_id") == player_id:
                return False  # Already submitted
        
        # Add response
        response_data = {
            "text": response_text.strip(),
            "author_id": player_id,
            "is_llm": False
        }
        responses.append(response_data)
        
        # Update room
        self.room_manager.update_game_state(room_id, room["game_state"])
        
        # Check if all players have responded
        connected_players = self.room_manager.get_connected_players(room_id)
        if len(responses) >= len(connected_players):
            self._advance_to_guessing_phase(room_id)
        
        return True
    
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
            return False  # Already submitted
        
        # Record guess
        room["game_state"]["guesses"][player_id] = guess_index
        
        # Update room
        self.room_manager.update_game_state(room_id, room["game_state"])
        
        # Check if all players have guessed
        connected_players = self.room_manager.get_connected_players(room_id)
        guesses = room["game_state"]["guesses"]
        if len(guesses) >= len(connected_players):
            self._advance_to_results_phase(room_id)
        
        return True
    
    def advance_game_phase(self, room_id: str) -> Optional[str]:
        """
        Manually advance the game phase (used for timeouts).
        
        Args:
            room_id: ID of the room
            
        Returns:
            New phase name or None if room doesn't exist
        """
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return None
        
        current_phase = room["game_state"]["phase"]
        
        if current_phase == GamePhase.RESPONDING.value:
            return self._advance_to_guessing_phase(room_id)
        elif current_phase == GamePhase.GUESSING.value:
            return self._advance_to_results_phase(room_id)
        elif current_phase == GamePhase.RESULTS.value:
            return self._advance_to_waiting_phase(room_id)
        
        return current_phase
    
    def _advance_to_guessing_phase(self, room_id: str) -> str:
        """Advance to guessing phase and add LLM response."""
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return GamePhase.WAITING.value
        
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
        
        self.room_manager.update_game_state(room_id, room["game_state"])
        return GamePhase.GUESSING.value
    
    def _advance_to_results_phase(self, room_id: str) -> str:
        """Advance to results phase and calculate scores."""
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return GamePhase.WAITING.value
        
        # Calculate and update scores
        self._calculate_round_scores(room_id, room)
        
        # Update phase
        room["game_state"]["phase"] = GamePhase.RESULTS.value
        room["game_state"]["phase_start_time"] = datetime.now()
        room["game_state"]["phase_duration"] = self.PHASE_DURATIONS[GamePhase.RESULTS]
        
        # Update game state in room manager
        self.room_manager.update_game_state(room_id, room["game_state"])
        
        # Update player scores in room manager
        for player_id, player_data in room["players"].items():
            self.room_manager.update_player_score(room_id, player_id, player_data["score"])
        
        return GamePhase.RESULTS.value
    
    def _advance_to_waiting_phase(self, room_id: str) -> str:
        """Advance to waiting phase for next round."""
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return GamePhase.WAITING.value
        
        # Reset for next round
        room["game_state"]["phase"] = GamePhase.WAITING.value
        room["game_state"]["current_prompt"] = None
        room["game_state"]["responses"] = []
        room["game_state"]["guesses"] = {}
        room["game_state"]["phase_start_time"] = None
        room["game_state"]["phase_duration"] = 0
        
        self.room_manager.update_game_state(room_id, room["game_state"])
        return GamePhase.WAITING.value
    
    def _calculate_round_scores(self, room_id: str, room: Dict) -> Dict[str, int]:
        """
        Calculate scores for the current round.
        
        Returns:
            Dict mapping player_id to points earned this round
        """
        round_scores: Dict[str, int] = {}
        responses = room["game_state"]["responses"]
        guesses = room["game_state"]["guesses"]
        
        # Find the LLM response index
        llm_response_index = None
        for i, response in enumerate(responses):
            if response["is_llm"]:
                llm_response_index = i
                break
        
        if llm_response_index is None:
            return round_scores
        
        # Score guessing: 1 point for correctly identifying LLM response
        for player_id, guess_index in guesses.items():
            if guess_index == llm_response_index:
                round_scores[player_id] = round_scores.get(player_id, 0) + 1
                # Only update score if player still exists in room
                if player_id in room["players"]:
                    room["players"][player_id]["score"] += 1
        
        # Score deception: 5 points for each guess received on your response
        for player_id, guess_index in guesses.items():
            guessed_response = responses[guess_index]
            if not guessed_response["is_llm"]:
                author_id = guessed_response["author_id"]
                if author_id and author_id != player_id:  # Can't vote for yourself
                    round_scores[author_id] = round_scores.get(author_id, 0) + 5
                    # Only update score if player still exists in room
                    if author_id in room["players"]:
                        room["players"][author_id]["score"] += 5
        
        return round_scores
    
    def get_round_results(self, room_id: str) -> Optional[Dict]:
        """
        Get detailed results for the current round including scoring breakdown.
        
        Args:
            room_id: ID of the room
            
        Returns:
            Dict containing round results or None if room doesn't exist or not in results phase
        """
        room = self.room_manager.get_room_state(room_id)
        if not room or room["game_state"]["phase"] != GamePhase.RESULTS.value:
            return None
        
        game_state = room["game_state"]
        responses = game_state["responses"]
        guesses = game_state["guesses"]
        players = room["players"]
        
        # Find the LLM response
        llm_response_index = None
        llm_response = None
        for i, response in enumerate(responses):
            if response["is_llm"]:
                llm_response_index = i
                llm_response = response
                break
        
        # Prepare response details with authorship revealed
        response_details = []
        for i, response in enumerate(responses):
            response_info = {
                "index": i,
                "text": response["text"],
                "is_llm": response["is_llm"],
                "votes_received": 0,
                "voters": []
            }
            
            if not response["is_llm"] and response["author_id"] in players:
                response_info["author_name"] = players[response["author_id"]]["name"]
                response_info["author_id"] = response["author_id"]
            
            # Count votes for this response
            for voter_id, voted_index in guesses.items():
                if voted_index == i and voter_id in players:
                    response_info["votes_received"] += 1
                    response_info["voters"].append(players[voter_id]["name"])
            
            response_details.append(response_info)
        
        # Calculate scoring breakdown for each player
        player_results = {}
        for player_id, player_data in players.items():
            if not player_data["connected"]:
                continue
                
            player_result = {
                "player_id": player_id,
                "name": player_data["name"],
                "total_score": player_data["score"],
                "round_points": 0,
                "correct_guess": False,
                "deception_points": 0,
                "guess_target": None,
                "response_votes": 0
            }
            
            # Check if player made a correct guess
            if player_id in guesses:
                guess_index = guesses[player_id]
                player_result["guess_target"] = guess_index
                if guess_index == llm_response_index:
                    player_result["correct_guess"] = True
                    player_result["round_points"] += 1
            
            # Count deception points (votes received on their response)
            for response in response_details:
                if (not response["is_llm"] and 
                    response.get("author_id") == player_id):
                    player_result["response_votes"] = response["votes_received"]
                    player_result["deception_points"] = response["votes_received"] * 5
                    player_result["round_points"] += response["votes_received"] * 5
                    break
            
            player_results[player_id] = player_result
        
        # Create correct response object for frontend
        correct_response = None
        if llm_response and llm_response_index is not None:
            correct_response = {
                "text": llm_response["text"],
                "model": game_state["current_prompt"]["model"] if game_state["current_prompt"] else "Unknown",
                "index": llm_response_index
            }

        return {
            "round_number": game_state["round_number"],
            "llm_response_index": llm_response_index,
            "llm_model": game_state["current_prompt"]["model"] if game_state["current_prompt"] else "Unknown",
            "correct_response": correct_response,
            "responses": response_details,
            "player_results": player_results,
            "total_players": len([p for p in players.values() if p["connected"]]),
            "total_guesses": len(guesses)
        }
    
    def get_scoring_summary(self, room_id: str) -> Optional[Dict]:
        """
        Get a summary of scoring rules and current game statistics.
        
        Args:
            room_id: ID of the room
            
        Returns:
            Dict containing scoring information or None if room doesn't exist
        """
        room = self.room_manager.get_room_state(room_id)
        if not room:
            return None
        
        game_state = room["game_state"]
        players = room["players"]
        
        # Calculate game statistics
        connected_players = [p for p in players.values() if p["connected"]]
        total_rounds = game_state["round_number"] if game_state["phase"] != "waiting" else game_state["round_number"] - 1
        
        # Find highest scorer
        highest_score = 0
        leaders = []
        for player in connected_players:
            if player["score"] > highest_score:
                highest_score = player["score"]
                leaders = [player["name"]]
            elif player["score"] == highest_score:
                leaders.append(player["name"])
        
        return {
            "scoring_rules": {
                "correct_llm_guess": 1,
                "deception_point": 5,
                "description": "Earn 1 point for correctly identifying the LLM response, and 5 points for each player who mistakes your response for the LLM."
            },
            "game_stats": {
                "total_rounds": total_rounds,
                "active_players": len(connected_players),
                "highest_score": highest_score,
                "current_leaders": leaders
            }
        }
    
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
    
    def get_leaderboard(self, room_id: str) -> List[Dict]:
        """
        Get the current leaderboard for a room.
        
        Args:
            room_id: ID of the room
            
        Returns:
            List of player dicts sorted by score (highest first)
        """
        players = self.room_manager.get_room_players(room_id)
        if not players:
            return []
        
        # Sort by score descending, then by name for ties
        leaderboard = sorted(players, key=lambda p: (-p["score"], p["name"]))
        
        # Add rank information
        for i, player in enumerate(leaderboard):
            player["rank"] = i + 1
        
        return leaderboard
    
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