"""
Game State Factory

Provides factory methods for creating game-related test data including
prompts, responses, guesses, scores, and leaderboards.
"""

import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


@dataclass
class PromptData:
    """Test data structure for prompt information"""
    id: str
    prompt: str
    category: str = 'general'
    responses: List[str] = field(default_factory=list)
    difficulty: str = 'medium'
    tags: List[str] = field(default_factory=list)


@dataclass
class GuessData:
    """Test data structure for guess information"""
    player_name: str
    session_id: str
    guess_index: int
    response_text: str
    is_correct: bool
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ScoreData:
    """Test data structure for score information"""
    player_name: str
    round_score: int
    total_score: int
    correct_guesses: int = 0
    total_guesses: int = 0
    bonus_points: int = 0


@dataclass
class LeaderboardEntry:
    """Test data structure for leaderboard entries"""
    rank: int
    player_name: str
    total_score: int
    rounds_played: int
    accuracy: float
    last_played: datetime = field(default_factory=datetime.now)


class GameContentFactory:
    """Factory for creating game content test data"""

    # Sample prompts for testing
    SAMPLE_PROMPTS = [
        {
            'prompt': "What's your favorite way to spend a weekend?",
            'category': 'lifestyle',
            'tags': ['weekend', 'leisure', 'personal']
        },
        {
            'prompt': "If you could travel anywhere in the world, where would you go?",
            'category': 'travel',
            'tags': ['travel', 'dreams', 'adventure']
        },
        {
            'prompt': "What's the most unusual food you've ever eaten?",
            'category': 'food',
            'tags': ['food', 'experience', 'culture']
        },
        {
            'prompt': "Describe your ideal job in three words.",
            'category': 'career',
            'tags': ['work', 'career', 'aspirations']
        },
        {
            'prompt': "What superpower would you choose and why?",
            'category': 'fantasy',
            'tags': ['fantasy', 'powers', 'imagination']
        }
    ]

    # Sample AI responses
    SAMPLE_RESPONSES = [
        "I'd love to explore new hiking trails and enjoy nature.",
        "Reading a good book by the fireplace sounds perfect.",
        "Visiting local farmers markets and trying new recipes.",
        "Learning a new hobby like photography or painting.",
        "Spending quality time with friends and family.",
        "Taking a relaxing spa day at home.",
        "Binge-watching documentaries about science.",
        "Working on creative writing projects."
    ]

    @classmethod
    def create_prompt(
        self,
        prompt_id: Optional[str] = None,
        prompt_text: Optional[str] = None,
        response_count: int = 2,
        **kwargs
    ) -> PromptData:
        """Create a test prompt with AI responses"""
        if prompt_id is None:
            prompt_id = f"prompt_{random.randint(1000, 9999)}"

        if prompt_text is None:
            sample = random.choice(self.SAMPLE_PROMPTS)
            prompt_text = sample['prompt']
            kwargs.setdefault('category', sample['category'])
            kwargs.setdefault('tags', sample['tags'])

        # Generate AI responses
        responses = random.sample(self.SAMPLE_RESPONSES, min(response_count, len(self.SAMPLE_RESPONSES)))

        return PromptData(
            id=prompt_id,
            prompt=prompt_text,
            responses=responses,
            **kwargs
        )

    @classmethod
    def create_prompts_batch(self, count: int) -> List[PromptData]:
        """Create multiple prompts for testing"""
        return [self.create_prompt() for _ in range(count)]

    @classmethod
    def create_category_prompts(self, categories: List[str]) -> List[PromptData]:
        """Create prompts for specific categories"""
        prompts = []
        for category in categories:
            matching_samples = [p for p in self.SAMPLE_PROMPTS if p['category'] == category]
            if matching_samples:
                sample = random.choice(matching_samples)
                prompt = self.create_prompt(
                    prompt_text=sample['prompt'],
                    category=sample['category'],
                    tags=sample['tags']
                )
                prompts.append(prompt)
        return prompts


class GameplayFactory:
    """Factory for creating gameplay scenarios"""

    @staticmethod
    def create_guess(
        player_name: str,
        session_id: str,
        responses: List[str],
        correct_index: Optional[int] = None,
        **kwargs
    ) -> GuessData:
        """Create a guess data object"""
        if correct_index is None:
            guess_index = random.randint(0, len(responses) - 1)
            is_correct = random.choice([True, False])
        else:
            guess_index = random.randint(0, len(responses) - 1)
            is_correct = (guess_index == correct_index)

        return GuessData(
            player_name=player_name,
            session_id=session_id,
            guess_index=guess_index,
            response_text=responses[guess_index] if responses else "",
            is_correct=is_correct,
            **kwargs
        )

    @staticmethod
    def create_round_guesses(
        players: List[str],
        responses: List[str],
        correct_distribution: Optional[Dict[str, int]] = None
    ) -> List[GuessData]:
        """Create guesses for a complete round"""
        guesses = []

        for i, player_name in enumerate(players):
            session_id = f"session_{i+1}"
            correct_index = correct_distribution.get(player_name) if correct_distribution else None

            guess = GameplayFactory.create_guess(
                player_name=player_name,
                session_id=session_id,
                responses=responses,
                correct_index=correct_index
            )
            guesses.append(guess)

        return guesses

    @staticmethod
    def create_scoring_scenario(
        players: List[str],
        correct_guesses: Optional[Dict[str, bool]] = None
    ) -> List[ScoreData]:
        """Create scoring data for players"""
        scores = []

        for player_name in players:
            is_correct = correct_guesses.get(player_name, random.choice([True, False])) if correct_guesses else random.choice([True, False])

            round_score = 10 if is_correct else 0
            bonus_points = random.randint(0, 5) if is_correct else 0

            score = ScoreData(
                player_name=player_name,
                round_score=round_score + bonus_points,
                total_score=random.randint(0, 100) + round_score + bonus_points,
                correct_guesses=1 if is_correct else 0,
                total_guesses=1,
                bonus_points=bonus_points
            )
            scores.append(score)

        return scores

    @staticmethod
    def create_leaderboard(player_count: int = 10) -> List[LeaderboardEntry]:
        """Create a complete leaderboard for testing"""
        players = [f"Player{i+1}" for i in range(player_count)]
        entries = []

        for i, player_name in enumerate(players):
            total_score = random.randint(50, 500)
            rounds_played = random.randint(5, 50)
            correct_guesses = random.randint(1, rounds_played)
            accuracy = correct_guesses / rounds_played

            entry = LeaderboardEntry(
                rank=i+1,
                player_name=player_name,
                total_score=total_score,
                rounds_played=rounds_played,
                accuracy=accuracy,
                last_played=datetime.now() - timedelta(days=random.randint(0, 30))
            )
            entries.append(entry)

        # Sort by total score descending
        entries.sort(key=lambda x: x.total_score, reverse=True)
        for i, entry in enumerate(entries):
            entry.rank = i + 1

        return entries


class GameScenarioFactory:
    """Factory for creating complete game scenarios"""

    @staticmethod
    def create_perfect_round_scenario(players: List[str]) -> Tuple[PromptData, List[str], List[GuessData], List[ScoreData]]:
        """Create scenario where all players guess correctly"""
        prompt = GameContentFactory.create_prompt(response_count=len(players))

        # Create responses (one per player)
        responses = [f"Response from {player}" for player in players]

        # Create correct guesses (each player guesses their own response)
        correct_distribution = {player: i for i, player in enumerate(players)}
        guesses = GameplayFactory.create_round_guesses(players, responses, correct_distribution)

        # Create perfect scores
        correct_guesses = {player: True for player in players}
        scores = GameplayFactory.create_scoring_scenario(players, correct_guesses)

        return prompt, responses, guesses, scores

    @staticmethod
    def create_mixed_performance_scenario(players: List[str]) -> Tuple[PromptData, List[str], List[GuessData], List[ScoreData]]:
        """Create scenario with mixed player performance"""
        prompt = GameContentFactory.create_prompt(response_count=len(players))
        responses = [f"Response from {player}" for player in players]

        # Mixed correct/incorrect guesses
        correct_distribution = {}
        for i, player in enumerate(players):
            # 60% chance of guessing correctly
            if random.random() < 0.6:
                correct_distribution[player] = i
            else:
                # Random incorrect guess
                wrong_options = [j for j in range(len(players)) if j != i]
                correct_distribution[player] = random.choice(wrong_options) if wrong_options else i

        guesses = GameplayFactory.create_round_guesses(players, responses, correct_distribution)

        # Calculate scores based on correctness
        correct_guesses = {
            player: (correct_distribution[player] == i)
            for i, player in enumerate(players)
        }
        scores = GameplayFactory.create_scoring_scenario(players, correct_guesses)

        return prompt, responses, guesses, scores

    @staticmethod
    def create_no_correct_guesses_scenario(players: List[str]) -> Tuple[PromptData, List[str], List[GuessData], List[ScoreData]]:
        """Create scenario where no one guesses correctly"""
        prompt = GameContentFactory.create_prompt(response_count=len(players))
        responses = [f"Response from {player}" for player in players]

        # Ensure all guesses are wrong
        correct_distribution = {}
        for i, player in enumerate(players):
            wrong_options = [j for j in range(len(players)) if j != i]
            correct_distribution[player] = random.choice(wrong_options) if wrong_options else (i + 1) % len(players)

        guesses = GameplayFactory.create_round_guesses(players, responses, correct_distribution)

        # All incorrect scores
        correct_guesses = {player: False for player in players}
        scores = GameplayFactory.create_scoring_scenario(players, correct_guesses)

        return prompt, responses, guesses, scores

    @staticmethod
    def create_tournament_scenario(round_count: int = 5) -> List[Tuple[PromptData, List[str], List[GuessData], List[ScoreData]]]:
        """Create multiple rounds for tournament testing"""
        players = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
        rounds = []

        for round_num in range(round_count):
            # Vary performance across rounds
            if round_num == 0:
                scenario = GameScenarioFactory.create_perfect_round_scenario(players)
            elif round_num == round_count - 1:
                scenario = GameScenarioFactory.create_no_correct_guesses_scenario(players)
            else:
                scenario = GameScenarioFactory.create_mixed_performance_scenario(players)

            rounds.append(scenario)

        return rounds


class TestDataBuilder:
    """Builder for creating complex test scenarios"""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset builder state"""
        self._players = []
        self._prompts = []
        self._responses = []
        self._guesses = []
        self._scores = []
        return self

    def with_players(self, *player_names: str):
        """Add specific players"""
        self._players = list(player_names)
        return self

    def with_random_players(self, count: int):
        """Add random players"""
        self._players = [f"TestPlayer{i+1}" for i in range(count)]
        return self

    def with_prompt(self, prompt: Optional[PromptData] = None):
        """Add a prompt"""
        if prompt is None:
            prompt = GameContentFactory.create_prompt()
        self._prompts = [prompt]
        return self

    def with_responses(self, *responses: str):
        """Add specific responses"""
        self._responses = list(responses)
        return self

    def with_player_responses(self):
        """Generate responses based on players"""
        if not self._players:
            raise ValueError("Players must be set before generating responses")
        self._responses = [f"Response from {player}" for player in self._players]
        return self

    def with_perfect_guesses(self):
        """Create perfect guesses (all correct)"""
        if not self._players or not self._responses:
            raise ValueError("Players and responses must be set")

        self._guesses = []
        for i, player in enumerate(self._players):
            guess = GuessData(
                player_name=player,
                session_id=f"session_{i}",
                guess_index=i,
                response_text=self._responses[i],
                is_correct=True
            )
            self._guesses.append(guess)
        return self

    def with_random_guesses(self):
        """Create random guesses"""
        if not self._players or not self._responses:
            raise ValueError("Players and responses must be set")

        self._guesses = GameplayFactory.create_round_guesses(self._players, self._responses)
        return self

    def with_scores_from_guesses(self):
        """Calculate scores based on guesses"""
        if not self._guesses:
            raise ValueError("Guesses must be set")

        correct_guesses = {guess.player_name: guess.is_correct for guess in self._guesses}
        self._scores = GameplayFactory.create_scoring_scenario(self._players, correct_guesses)
        return self

    def build_scenario(self) -> Dict[str, Any]:
        """Build complete game scenario"""
        return {
            'players': self._players,
            'prompts': self._prompts,
            'responses': self._responses,
            'guesses': self._guesses,
            'scores': self._scores
        }


if __name__ == "__main__":
    # Example usage
    prompt = GameContentFactory.create_prompt()
    print(f"Created prompt: {prompt.prompt}")

    players = ["Alice", "Bob", "Charlie"]
    scenario = GameScenarioFactory.create_mixed_performance_scenario(players)
    prompt, responses, guesses, scores = scenario

    print(f"Scenario: {len(guesses)} guesses, {sum(1 for g in guesses if g.is_correct)} correct")

    # Using builder
    builder_scenario = (TestDataBuilder()
                       .with_players("Alice", "Bob")
                       .with_player_responses()
                       .with_perfect_guesses()
                       .with_scores_from_guesses()
                       .build_scenario())

    print(f"Builder scenario: {len(builder_scenario['players'])} players")