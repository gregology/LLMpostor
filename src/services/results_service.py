"""
Results Service for LLMpostor Game

Handles results formatting and presentation for game rounds.
Extracted from GameManager to follow Single Responsibility Principle.
"""

import logging
from typing import Dict, Optional, List

try:
    from ..core.game_phases import GamePhase
except ImportError:
    from src.core.game_phases import GamePhase

logger = logging.getLogger(__name__)


class ResultsService:
    """Manages results formatting and presentation."""
    
    def __init__(self, room_manager):
        self.room_manager = room_manager
    
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
        llm_response_index, llm_response = self._find_llm_response(responses)
        
        # Prepare response details with authorship revealed
        response_details = self._build_response_details(responses, guesses, players)
        
        # Calculate scoring breakdown for each player
        player_results = self._build_player_results(players, guesses, llm_response_index, response_details)
        
        # Create correct response object for frontend
        correct_response = self._build_correct_response(llm_response, llm_response_index, game_state)
        
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
    
    def _find_llm_response(self, responses: List[Dict]) -> tuple:
        """Find the LLM response and its index."""
        llm_response_index = None
        llm_response = None
        for i, response in enumerate(responses):
            if response["is_llm"]:
                llm_response_index = i
                llm_response = response
                break
        return llm_response_index, llm_response
    
    def _build_response_details(self, responses: List[Dict], guesses: Dict[str, int], players: Dict[str, Dict]) -> List[Dict]:
        """Build detailed response information with vote counts."""
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
        
        return response_details
    
    def _build_player_results(self, players: Dict[str, Dict], guesses: Dict[str, int], 
                            llm_response_index: int, response_details: List[Dict]) -> Dict[str, Dict]:
        """Build player results with scoring breakdown."""
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
        
        return player_results
    
    def _build_correct_response(self, llm_response: Optional[Dict], llm_response_index: Optional[int], 
                              game_state: Dict) -> Optional[Dict]:
        """Build correct response object for frontend."""
        if llm_response and llm_response_index is not None:
            return {
                "text": llm_response["text"],
                "model": game_state["current_prompt"]["model"] if game_state["current_prompt"] else "Unknown",
                "index": llm_response_index
            }
        return None