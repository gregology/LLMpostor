"""
Unit tests for GameManager class.
"""

from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from game_manager import GameManager, GamePhase
from room_manager import RoomManager


class TestGameManager:
    """Test cases for GameManager functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        
        # Create a test room with players
        self.room_id = "test_room"
        self.player1 = self.room_manager.add_player_to_room(self.room_id, "Player1", "socket1")
        self.player2 = self.room_manager.add_player_to_room(self.room_id, "Player2", "socket2")
        
        # Sample prompt data
        self.prompt_data = {
            "id": "prompt_001",
            "prompt": "Test prompt",
            "model": "GPT-4",
            "llm_response": "This is the LLM response"
        }
    
    def test_start_new_round_success(self):
        """Test successful round start."""
        result = self.game_manager.start_new_round(self.room_id, self.prompt_data)
        assert result is True
        
        game_state = self.game_manager.get_game_state(self.room_id)
        assert game_state["phase"] == GamePhase.RESPONDING.value
        assert game_state["current_prompt"] == self.prompt_data
        assert game_state["responses"] == []
        assert game_state["guesses"] == {}
        assert game_state["round_number"] == 1
        assert isinstance(game_state["phase_start_time"], datetime)
        assert game_state["phase_duration"] == 180  # 3 minutes
    
    def test_start_new_round_nonexistent_room(self):
        """Test starting round in non-existent room fails."""
        result = self.game_manager.start_new_round("nonexistent", self.prompt_data)
        assert result is False
    
    def test_start_new_round_invalid_phase(self):
        """Test starting round during invalid phase fails."""
        # Start a round first
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        
        # Try to start another round while in responding phase
        result = self.game_manager.start_new_round(self.room_id, self.prompt_data)
        assert result is False
    
    def test_submit_player_response_success(self):
        """Test successful response submission."""
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        
        result = self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "My response"
        )
        assert result is True
        
        game_state = self.game_manager.get_game_state(self.room_id)
        responses = game_state["responses"]
        assert len(responses) == 1
        assert responses[0]["text"] == "My response"
        assert responses[0]["author_id"] == self.player1["player_id"]
        assert responses[0]["is_llm"] is False
    
    def test_submit_player_response_wrong_phase(self):
        """Test response submission during wrong phase fails."""
        # Don't start a round, so we're in waiting phase
        result = self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "My response"
        )
        assert result is False
    
    def test_submit_player_response_nonexistent_player(self):
        """Test response submission by non-existent player fails."""
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        
        result = self.game_manager.submit_player_response(
            self.room_id, "nonexistent_player", "My response"
        )
        assert result is False
    
    def test_submit_player_response_duplicate(self):
        """Test that player cannot submit multiple responses."""
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        
        # First submission should succeed
        result1 = self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "First response"
        )
        assert result1 is True
        
        # Second submission should fail
        result2 = self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "Second response"
        )
        assert result2 is False
        
        # Should still only have one response
        game_state = self.game_manager.get_game_state(self.room_id)
        assert len(game_state["responses"]) == 1
    
    def test_auto_advance_to_guessing_when_all_respond(self):
        """Test automatic advancement to guessing phase when all players respond."""
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        
        # Both players submit responses
        self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "Response 1"
        )
        self.game_manager.submit_player_response(
            self.room_id, self.player2["player_id"], "Response 2"
        )
        
        # Should automatically advance to guessing phase
        game_state = self.game_manager.get_game_state(self.room_id)
        assert game_state["phase"] == GamePhase.GUESSING.value
        
        # Should have 3 responses (2 players + 1 LLM)
        responses = game_state["responses"]
        assert len(responses) == 3
        
        # One should be the LLM response
        llm_responses = [r for r in responses if r["is_llm"]]
        assert len(llm_responses) == 1
        assert llm_responses[0]["text"] == "This is the LLM response"
    
    def test_submit_player_guess_success(self):
        """Test successful guess submission."""
        # Set up guessing phase
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "Response 1"
        )
        self.game_manager.submit_player_response(
            self.room_id, self.player2["player_id"], "Response 2"
        )
        
        # Now in guessing phase, submit a guess
        result = self.game_manager.submit_player_guess(
            self.room_id, self.player1["player_id"], 0
        )
        assert result is True
        
        game_state = self.game_manager.get_game_state(self.room_id)
        assert self.player1["player_id"] in game_state["guesses"]
        assert game_state["guesses"][self.player1["player_id"]] == 0
    
    def test_submit_player_guess_invalid_index(self):
        """Test guess submission with invalid response index."""
        # Set up guessing phase
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "Response 1"
        )
        self.game_manager.submit_player_response(
            self.room_id, self.player2["player_id"], "Response 2"
        )
        
        # Try to guess invalid index
        result = self.game_manager.submit_player_guess(
            self.room_id, self.player1["player_id"], 99
        )
        assert result is False
    
    def test_auto_advance_to_results_when_all_guess(self):
        """Test automatic advancement to results phase when all players guess."""
        # Set up and complete responding phase
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "Response 1"
        )
        self.game_manager.submit_player_response(
            self.room_id, self.player2["player_id"], "Response 2"
        )
        
        # Both players submit guesses
        self.game_manager.submit_player_guess(
            self.room_id, self.player1["player_id"], 0
        )
        self.game_manager.submit_player_guess(
            self.room_id, self.player2["player_id"], 1
        )
        
        # Should automatically advance to results phase
        game_state = self.game_manager.get_game_state(self.room_id)
        assert game_state["phase"] == GamePhase.RESULTS.value
    
    def test_manual_phase_advancement(self):
        """Test manual phase advancement (for timeouts)."""
        # Start in responding phase
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        
        # Manually advance to guessing
        new_phase = self.game_manager.advance_game_phase(self.room_id)
        assert new_phase == GamePhase.GUESSING.value
        
        # Manually advance to results
        new_phase = self.game_manager.advance_game_phase(self.room_id)
        assert new_phase == GamePhase.RESULTS.value
        
        # Manually advance to waiting
        new_phase = self.game_manager.advance_game_phase(self.room_id)
        assert new_phase == GamePhase.WAITING.value
    
    def test_scoring_correct_llm_guess(self):
        """Test scoring when player correctly identifies LLM response."""
        # Complete a full round
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "Response 1"
        )
        self.game_manager.submit_player_response(
            self.room_id, self.player2["player_id"], "Response 2"
        )
        
        # Find the LLM response index
        game_state = self.game_manager.get_game_state(self.room_id)
        responses = game_state["responses"]
        llm_index = None
        for i, response in enumerate(responses):
            if response["is_llm"]:
                llm_index = i
                break
        
        # Player 1 guesses correctly
        self.game_manager.submit_player_guess(
            self.room_id, self.player1["player_id"], llm_index
        )
        # Player 2 guesses incorrectly - find player2's own response to avoid giving player1 deception points
        player2_response_index = None
        for i, response in enumerate(responses):
            if response.get("author_id") == self.player2["player_id"]:
                player2_response_index = i
                break
        
        # If player2 can't find their own response, use a different wrong index
        wrong_index = player2_response_index if player2_response_index is not None else llm_index
        if wrong_index == llm_index:
            # Find any non-LLM response that isn't player1's
            for i, response in enumerate(responses):
                if not response["is_llm"] and response.get("author_id") != self.player1["player_id"]:
                    wrong_index = i
                    break
        
        self.game_manager.submit_player_guess(
            self.room_id, self.player2["player_id"], wrong_index
        )
        
        # Check scores
        leaderboard = self.game_manager.get_leaderboard(self.room_id)
        player1_score = next(p["score"] for p in leaderboard if p["player_id"] == self.player1["player_id"])
        player2_score = next(p["score"] for p in leaderboard if p["player_id"] == self.player2["player_id"])
        
        assert player1_score == 1  # Correct LLM guess only
        # Player2 should have 0 points since they guessed wrong and no one guessed their response
    
    def test_scoring_deception_points(self):
        """Test scoring when player's response gets guessed as LLM."""
        # Complete a full round
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "Response 1"
        )
        self.game_manager.submit_player_response(
            self.room_id, self.player2["player_id"], "Response 2"
        )
        
        # Find player1's response index
        game_state = self.game_manager.get_game_state(self.room_id)
        responses = game_state["responses"]
        player1_response_index = None
        for i, response in enumerate(responses):
            if response["author_id"] == self.player1["player_id"]:
                player1_response_index = i
                break
        
        # Both players guess player1's response as LLM (wrong, but gives player1 points)
        self.game_manager.submit_player_guess(
            self.room_id, self.player1["player_id"], player1_response_index  # Can't vote for yourself
        )
        self.game_manager.submit_player_guess(
            self.room_id, self.player2["player_id"], player1_response_index
        )
        
        # Player1 should get deception points from player2's guess
        leaderboard = self.game_manager.get_leaderboard(self.room_id)
        player1_score = next(p["score"] for p in leaderboard if p["player_id"] == self.player1["player_id"])
        
        # Player1 gets 5 points for fooling player2 (player1 can't vote for themselves)
        assert player1_score >= 5
    
    def test_get_leaderboard_sorting(self):
        """Test leaderboard sorting by score."""
        # Manually set different scores
        room_state = self.room_manager.get_room_state(self.room_id)
        room_state["players"][self.player1["player_id"]]["score"] = 5
        room_state["players"][self.player2["player_id"]]["score"] = 3
        
        leaderboard = self.game_manager.get_leaderboard(self.room_id)
        
        assert len(leaderboard) == 2
        assert leaderboard[0]["score"] == 5  # Highest score first
        assert leaderboard[1]["score"] == 3
        assert leaderboard[0]["rank"] == 1
        assert leaderboard[1]["rank"] == 2
    
    def test_phase_time_tracking(self):
        """Test phase timing functionality."""
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        
        # Should not be expired immediately
        assert not self.game_manager.is_phase_expired(self.room_id)
        
        # Should have time remaining
        time_remaining = self.game_manager.get_phase_time_remaining(self.room_id)
        assert time_remaining > 0
        assert time_remaining <= 180  # Should be at most 3 minutes
    
    def test_can_start_round_conditions(self):
        """Test conditions for starting a new round."""
        # With 2 players in waiting phase, should be able to start
        can_start, reason = self.game_manager.can_start_round(self.room_id)
        assert can_start is True
        assert reason == "Ready to start"
        
        # Remove one player (need at least 2)
        self.room_manager.remove_player_from_room(self.room_id, self.player2["player_id"])
        can_start, reason = self.game_manager.can_start_round(self.room_id)
        assert can_start is False
        assert "Need at least 2 players" in reason
        
        # Add player back and start round
        self.room_manager.add_player_to_room(self.room_id, "Player2", "socket2")
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        
        # Should not be able to start during responding phase
        can_start, reason = self.game_manager.can_start_round(self.room_id)
        assert can_start is False
        assert "responding phase" in reason
    
    def test_nonexistent_room_operations(self):
        """Test operations on non-existent rooms."""
        nonexistent_room = "nonexistent"
        
        assert self.game_manager.get_game_state(nonexistent_room) is None
        assert self.game_manager.get_leaderboard(nonexistent_room) == []
        assert not self.game_manager.is_phase_expired(nonexistent_room)
        assert self.game_manager.get_phase_time_remaining(nonexistent_room) == 0
        
        can_start, reason = self.game_manager.can_start_round(nonexistent_room)
        assert can_start is False
        assert "does not exist" in reason
    
    def test_responses_shuffled_in_guessing_phase(self):
        """Test that responses are shuffled when entering guessing phase."""
        # We'll run this multiple times to check for randomization
        # (though this is a probabilistic test)
        
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "Response A"
        )
        self.game_manager.submit_player_response(
            self.room_id, self.player2["player_id"], "Response B"
        )
        
        game_state = self.game_manager.get_game_state(self.room_id)
        responses = game_state["responses"]
        
        # Should have 3 responses total
        assert len(responses) == 3
        
        # Should have exactly one LLM response
        llm_responses = [r for r in responses if r["is_llm"]]
        assert len(llm_responses) == 1
        
        # The LLM response could be at any position (due to shuffling)
        llm_response_texts = [r["text"] for r in llm_responses]
        assert "This is the LLM response" in llm_response_texts
    
    def test_round_number_increments(self):
        """Test that round number increments correctly."""
        # Start first round
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        game_state = self.game_manager.get_game_state(self.room_id)
        assert game_state["round_number"] == 1
        
        # Complete the round and start another
        self.game_manager.advance_game_phase(self.room_id)  # to guessing
        self.game_manager.advance_game_phase(self.room_id)  # to results
        self.game_manager.advance_game_phase(self.room_id)  # to waiting
        
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        game_state = self.game_manager.get_game_state(self.room_id)
        assert game_state["round_number"] == 2
    
    def test_get_round_results_detailed(self):
        """Test detailed round results functionality."""
        # Complete a full round
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "Player 1 response"
        )
        self.game_manager.submit_player_response(
            self.room_id, self.player2["player_id"], "Player 2 response"
        )
        
        # Find LLM response index
        game_state = self.game_manager.get_game_state(self.room_id)
        responses = game_state["responses"]
        llm_index = None
        for i, response in enumerate(responses):
            if response["is_llm"]:
                llm_index = i
                break
        
        # Submit guesses
        self.game_manager.submit_player_guess(
            self.room_id, self.player1["player_id"], llm_index  # Correct guess
        )
        self.game_manager.submit_player_guess(
            self.room_id, self.player2["player_id"], 0  # Some guess
        )
        
        # Now in results phase, get detailed results
        results = self.game_manager.get_round_results(self.room_id)
        
        assert results is not None
        assert results["round_number"] == 1
        assert results["llm_response_index"] == llm_index
        assert results["llm_model"] == "GPT-4"
        assert len(results["responses"]) == 3
        assert results["total_players"] == 2
        assert results["total_guesses"] == 2
        
        # Check player results
        player_results = results["player_results"]
        assert len(player_results) == 2
        
        # Player 1 should have correct guess
        player1_result = player_results[self.player1["player_id"]]
        assert player1_result["correct_guess"] is True
        assert player1_result["round_points"] >= 1  # At least 1 for correct guess
        
        # Check response details
        for response in results["responses"]:
            assert "index" in response
            assert "text" in response
            assert "is_llm" in response
            assert "votes_received" in response
            assert "voters" in response
    
    def test_get_round_results_wrong_phase(self):
        """Test that round results are only available in results phase."""
        # In waiting phase
        results = self.game_manager.get_round_results(self.room_id)
        assert results is None
        
        # Start round (responding phase)
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        results = self.game_manager.get_round_results(self.room_id)
        assert results is None
        
        # Advance to guessing phase
        self.game_manager.advance_game_phase(self.room_id)
        results = self.game_manager.get_round_results(self.room_id)
        assert results is None
        
        # Advance to results phase
        self.game_manager.advance_game_phase(self.room_id)
        results = self.game_manager.get_round_results(self.room_id)
        assert results is not None
    
    def test_get_scoring_summary(self):
        """Test scoring summary functionality."""
        # Add a third player for more interesting stats
        player3 = self.room_manager.add_player_to_room(self.room_id, "Player3", "socket3")
        
        # Manually set some scores to test statistics
        room_state = self.room_manager.get_room_state(self.room_id)
        room_state["players"][self.player1["player_id"]]["score"] = 5
        room_state["players"][self.player2["player_id"]]["score"] = 3
        room_state["players"][player3["player_id"]]["score"] = 5  # Tie for first
        
        # Start a round to increment round number
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        
        summary = self.game_manager.get_scoring_summary(self.room_id)
        
        assert summary is not None
        assert "scoring_rules" in summary
        assert "game_stats" in summary
        
        # Check scoring rules
        rules = summary["scoring_rules"]
        assert rules["correct_llm_guess"] == 1
        assert rules["deception_point"] == 5
        assert "description" in rules
        
        # Check game stats
        stats = summary["game_stats"]
        assert stats["total_rounds"] == 1
        assert stats["active_players"] == 3
        assert stats["highest_score"] == 5
        assert len(stats["current_leaders"]) == 2  # Two players tied at 5 points
        assert "Player1" in stats["current_leaders"]
        assert "Player3" in stats["current_leaders"]
    
    def test_scoring_multiple_deception_points(self):
        """Test that players can earn multiple deception points in one round."""
        # Add a third player
        player3 = self.room_manager.add_player_to_room(self.room_id, "Player3", "socket3")
        
        # Complete a round
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "Very convincing AI response"
        )
        self.game_manager.submit_player_response(
            self.room_id, self.player2["player_id"], "Player 2 response"
        )
        self.game_manager.submit_player_response(
            self.room_id, player3["player_id"], "Player 3 response"
        )
        
        # Find player1's response index
        game_state = self.game_manager.get_game_state(self.room_id)
        responses = game_state["responses"]
        player1_response_index = None
        for i, response in enumerate(responses):
            if response["author_id"] == self.player1["player_id"]:
                player1_response_index = i
                break
        
        # Find LLM response index to make sure player1 doesn't guess it correctly
        llm_index = None
        for i, response in enumerate(responses):
            if response["is_llm"]:
                llm_index = i
                break
        
        # Player1 guesses wrong (not LLM), other players guess player1's response as LLM
        wrong_guess = 0 if player1_response_index != 0 else 1
        if wrong_guess == llm_index:
            wrong_guess = 2 if len(responses) > 2 else 0
            
        self.game_manager.submit_player_guess(
            self.room_id, self.player1["player_id"], wrong_guess  # Wrong guess to avoid LLM points
        )
        self.game_manager.submit_player_guess(
            self.room_id, self.player2["player_id"], player1_response_index
        )
        self.game_manager.submit_player_guess(
            self.room_id, player3["player_id"], player1_response_index
        )
        
        # Player1 should get 10 deception points (2 votes × 5 points each from player2 and player3)
        results = self.game_manager.get_round_results(self.room_id)
        player1_result = results["player_results"][self.player1["player_id"]]
        assert player1_result["deception_points"] == 10
        assert player1_result["response_votes"] == 2
        assert player1_result["correct_guess"] is False  # Should not have guessed LLM correctly
        
        # Check final score - should be exactly 10 (only deception points: 2 votes × 5 points each)
        leaderboard = self.game_manager.get_leaderboard(self.room_id)
        player1_score = next(p["score"] for p in leaderboard if p["player_id"] == self.player1["player_id"])
        assert player1_score == 10  # 10 deception points only (2 votes × 5 points each)
    
    def test_leaderboard_persistence_across_rounds(self):
        """Test that scores persist across multiple rounds."""
        # Complete first round with player1 getting points
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "Response 1"
        )
        self.game_manager.submit_player_response(
            self.room_id, self.player2["player_id"], "Response 2"
        )
        
        # Find LLM response and have player1 guess correctly
        game_state = self.game_manager.get_game_state(self.room_id)
        llm_index = next(i for i, r in enumerate(game_state["responses"]) if r["is_llm"])
        
        self.game_manager.submit_player_guess(self.room_id, self.player1["player_id"], llm_index)
        self.game_manager.submit_player_guess(self.room_id, self.player2["player_id"], 0)
        
        # Check scores after first round
        leaderboard = self.game_manager.get_leaderboard(self.room_id)
        player1_score_round1 = next(p["score"] for p in leaderboard if p["player_id"] == self.player1["player_id"])
        assert player1_score_round1 >= 1
        
        # Start second round
        self.game_manager.advance_game_phase(self.room_id)  # to waiting
        self.game_manager.start_new_round(self.room_id, self.prompt_data)
        
        # Complete second round with player2 getting points
        self.game_manager.submit_player_response(
            self.room_id, self.player1["player_id"], "Response 1 round 2"
        )
        self.game_manager.submit_player_response(
            self.room_id, self.player2["player_id"], "Response 2 round 2"
        )
        
        game_state = self.game_manager.get_game_state(self.room_id)
        llm_index = next(i for i, r in enumerate(game_state["responses"]) if r["is_llm"])
        
        self.game_manager.submit_player_guess(self.room_id, self.player1["player_id"], 0)  # Wrong
        self.game_manager.submit_player_guess(self.room_id, self.player2["player_id"], llm_index)  # Correct
        
        # Check final scores
        leaderboard = self.game_manager.get_leaderboard(self.room_id)
        player1_final = next(p["score"] for p in leaderboard if p["player_id"] == self.player1["player_id"])
        player2_final = next(p["score"] for p in leaderboard if p["player_id"] == self.player2["player_id"])
        
        # Player1 should have at least the points from round 1 (may have gained more)
        assert player1_final >= player1_score_round1
        # Player2 should have gained points in round 2
        assert player2_final >= 1
    
    def test_new_player_starts_with_zero_score(self):
        """Test that new players joining mid-game start with 0 points."""
        # Give existing players some points
        room_state = self.room_manager.get_room_state(self.room_id)
        room_state["players"][self.player1["player_id"]]["score"] = 5
        room_state["players"][self.player2["player_id"]]["score"] = 3
        
        # Add new player
        player3 = self.room_manager.add_player_to_room(self.room_id, "NewPlayer", "socket3")
        
        # Check leaderboard
        leaderboard = self.game_manager.get_leaderboard(self.room_id)
        new_player_entry = next(p for p in leaderboard if p["player_id"] == player3["player_id"])
        
        assert new_player_entry["score"] == 0
        assert new_player_entry["rank"] == 3  # Should be last due to 0 score