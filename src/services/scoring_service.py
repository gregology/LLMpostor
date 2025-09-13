"""
Scoring Service for LLMpostor Game

Handles score calculation and validation logic for game rounds.
Extracted from GameManager to follow Single Responsibility Principle.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class ScoringService:
    """Manages scoring calculation for game rounds."""
    
    def __init__(self):
        pass
    
    def calculate_round_scores(self, room: Dict) -> Dict[str, int]:
        """
        Calculate scores for the current round.
        
        Args:
            room: Room data containing game state and players
        
        Returns:
            Dict mapping player_id to points earned this round
        """
        round_scores: Dict[str, int] = {}
        responses = room["game_state"]["responses"]
        guesses = room["game_state"]["guesses"]
        
        # Find the LLM response index
        llm_response_index = self._find_llm_response_index(responses)
        if llm_response_index is None:
            logger.warning("No LLM response found for scoring calculation")
            return round_scores
        
        # Score guessing: 1 point for correctly identifying LLM response
        round_scores.update(self._calculate_guess_scores(guesses, llm_response_index, room["players"]))
        
        # Score deception: 5 points for each guess received on your response
        round_scores.update(self._calculate_deception_scores(guesses, responses, room["players"]))
        
        return round_scores
    
    def _find_llm_response_index(self, responses: List[Dict]) -> int:
        """Find the index of the LLM response."""
        for i, response in enumerate(responses):
            if response["is_llm"]:
                return i
        return None
    
    def _calculate_guess_scores(self, guesses: Dict[str, int], llm_response_index: int, players: Dict) -> Dict[str, int]:
        """Calculate scores for correct LLM guesses."""
        guess_scores = {}
        for player_id, guess_index in guesses.items():
            if guess_index == llm_response_index:
                guess_scores[player_id] = guess_scores.get(player_id, 0) + 1
                # Update player score if player still exists in room
                if player_id in players:
                    players[player_id]["score"] += 1
        return guess_scores
    
    def _calculate_deception_scores(self, guesses: Dict[str, int], responses: List[Dict], players: Dict) -> Dict[str, int]:
        """Calculate scores for successful deception (votes received)."""
        deception_scores = {}
        for player_id, guess_index in guesses.items():
            guessed_response = responses[guess_index]
            if not guessed_response["is_llm"]:
                author_id = guessed_response["author_id"]
                if author_id and author_id != player_id:  # Can't vote for yourself
                    deception_scores[author_id] = deception_scores.get(author_id, 0) + 5
                    # Update player score if player still exists in room
                    if author_id in players:
                        players[author_id]["score"] += 5
        return deception_scores
    
    def get_scoring_summary(self, room: Dict) -> Dict:
        """
        Get a summary of scoring rules and current game statistics.
        
        Args:
            room: Room data containing game state and players
            
        Returns:
            Dict containing scoring information
        """
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
    
    def get_leaderboard(self, players: List[Dict]) -> List[Dict]:
        """
        Get the current leaderboard for players.
        
        Args:
            players: List of player data dicts
            
        Returns:
            List of player dicts sorted by score (highest first)
        """
        if not players:
            return []
        
        # Sort by score descending, then by name for ties
        leaderboard = sorted(players, key=lambda p: (-p["score"], p["name"]))
        
        # Add rank information
        for i, player in enumerate(leaderboard):
            player["rank"] = i + 1
        
        return leaderboard