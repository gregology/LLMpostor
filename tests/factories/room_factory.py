"""
Room Data Factory

Provides factory methods for creating room test data with consistent,
realistic values and customizable properties.
"""

import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class PlayerData:
    """Test data structure for player information"""
    name: str
    session_id: str
    has_responded: bool = False
    has_guessed: bool = False
    response_text: Optional[str] = None
    guess_index: Optional[int] = None
    total_score: int = 0
    round_score: int = 0
    join_time: datetime = field(default_factory=datetime.now)


@dataclass
class RoomData:
    """Test data structure for room information"""
    room_id: str
    phase: str = 'waiting'
    players: List[PlayerData] = field(default_factory=list)
    current_prompt: Optional[Dict[str, Any]] = None
    responses: List[str] = field(default_factory=list)
    guesses: List[Dict[str, Any]] = field(default_factory=list)
    round_number: int = 0
    phase_start_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    is_active: bool = True


class RoomFactory:
    """Factory for creating room test data"""

    @staticmethod
    def generate_room_id() -> str:
        """Generate a random room ID"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

    @staticmethod
    def generate_session_id() -> str:
        """Generate a random session ID"""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))

    @classmethod
    def create_room(
        self,
        room_id: Optional[str] = None,
        phase: str = 'waiting',
        player_count: int = 0,
        **kwargs
    ) -> RoomData:
        """Create a room with specified parameters"""
        if room_id is None:
            room_id = self.generate_room_id()

        room = RoomData(
            room_id=room_id,
            phase=phase,
            **kwargs
        )

        # Add players if requested
        for i in range(player_count):
            player = self.create_player(f"Player{i+1}")
            room.players.append(player)

        return room

    @classmethod
    def create_waiting_room(self, player_count: int = 2) -> RoomData:
        """Create a room in waiting phase"""
        return self.create_room(
            phase='waiting',
            player_count=player_count
        )

    @classmethod
    def create_responding_room(self, player_count: int = 3) -> RoomData:
        """Create a room in responding phase"""
        room = self.create_room(
            phase='responding',
            player_count=player_count,
            phase_start_time=datetime.now(),
            current_prompt=self.create_prompt()
        )
        room.round_number = 1
        return room

    @classmethod
    def create_guessing_room(self, player_count: int = 3) -> RoomData:
        """Create a room in guessing phase with responses"""
        room = self.create_responding_room(player_count)
        room.phase = 'guessing'
        room.phase_start_time = datetime.now()

        # Add responses for all players
        for i, player in enumerate(room.players):
            player.has_responded = True
            player.response_text = f"Response from {player.name}"
            room.responses.append(player.response_text)

        return room

    @classmethod
    def create_results_room(self, player_count: int = 3) -> RoomData:
        """Create a room in results phase with complete round data"""
        room = self.create_guessing_room(player_count)
        room.phase = 'results'
        room.phase_start_time = datetime.now()

        # Add guesses for all players
        for i, player in enumerate(room.players):
            player.has_guessed = True
            player.guess_index = random.randint(0, len(room.responses) - 1)

            # Calculate score based on correct guess
            correct_guess = player.guess_index == i
            player.round_score = 10 if correct_guess else 0
            player.total_score += player.round_score

            room.guesses.append({
                'player': player.name,
                'guess_index': player.guess_index,
                'correct': correct_guess
            })

        return room

    @staticmethod
    def create_player(
        name: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> PlayerData:
        """Create a player with specified parameters"""
        if name is None:
            name = f"Player{random.randint(1, 999)}"
        if session_id is None:
            session_id = RoomFactory.generate_session_id()

        return PlayerData(
            name=name,
            session_id=session_id,
            **kwargs
        )

    @staticmethod
    def create_prompt() -> Dict[str, Any]:
        """Create a test prompt"""
        prompts = [
            "What's your favorite way to spend a rainy day?",
            "If you could have any superpower, what would it be?",
            "What's the most unusual food you've ever tried?",
            "Describe your perfect vacation destination.",
            "What's a skill you'd like to learn?"
        ]

        return {
            'id': f"prompt_{random.randint(1, 1000)}",
            'prompt': random.choice(prompts),
            'category': 'general',
            'responses': [
                "AI Assistant Response 1",
                "AI Assistant Response 2"
            ]
        }

    @classmethod
    def create_rooms_batch(self, count: int, **kwargs) -> List[RoomData]:
        """Create multiple rooms for batch testing"""
        return [self.create_room(**kwargs) for _ in range(count)]

    @classmethod
    def create_concurrent_test_rooms(self, room_count: int = 5) -> List[RoomData]:
        """Create rooms for concurrent testing scenarios"""
        rooms = []
        phases = ['waiting', 'responding', 'guessing', 'results']

        for i in range(room_count):
            phase = phases[i % len(phases)]
            player_count = random.randint(2, 6)

            if phase == 'waiting':
                room = self.create_waiting_room(player_count)
            elif phase == 'responding':
                room = self.create_responding_room(player_count)
            elif phase == 'guessing':
                room = self.create_guessing_room(player_count)
            else:  # results
                room = self.create_results_room(player_count)

            rooms.append(room)

        return rooms


class RoomBuilder:
    """Builder pattern for creating customized room test data"""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset builder to initial state"""
        self._room_data = {
            'room_id': RoomFactory.generate_room_id(),
            'phase': 'waiting',
            'players': [],
            'round_number': 0
        }
        return self

    def with_id(self, room_id: str):
        """Set specific room ID"""
        self._room_data['room_id'] = room_id
        return self

    def in_phase(self, phase: str):
        """Set room phase"""
        self._room_data['phase'] = phase

        # Set appropriate phase start time
        if phase != 'waiting':
            self._room_data['phase_start_time'] = datetime.now()

        return self

    def with_players(self, *player_names: str):
        """Add players with specific names"""
        players = []
        for name in player_names:
            players.append(RoomFactory.create_player(name))
        self._room_data['players'] = players
        return self

    def with_random_players(self, count: int):
        """Add random players"""
        players = []
        for i in range(count):
            players.append(RoomFactory.create_player(f"TestPlayer{i+1}"))
        self._room_data['players'] = players
        return self

    def with_responses(self, *responses: str):
        """Add specific responses"""
        self._room_data['responses'] = list(responses)

        # Mark players as having responded
        for i, player in enumerate(self._room_data.get('players', [])):
            if i < len(responses):
                player.has_responded = True
                player.response_text = responses[i]

        return self

    def with_guesses(self, guesses: List[Dict[str, Any]]):
        """Add specific guesses"""
        self._room_data['guesses'] = guesses

        # Mark players as having guessed
        for guess in guesses:
            for player in self._room_data.get('players', []):
                if player.name == guess.get('player'):
                    player.has_guessed = True
                    player.guess_index = guess.get('guess_index')
                    break

        return self

    def with_prompt(self, prompt: Optional[Dict[str, Any]] = None):
        """Set current prompt"""
        if prompt is None:
            prompt = RoomFactory.create_prompt()
        self._room_data['current_prompt'] = prompt
        return self

    def in_round(self, round_number: int):
        """Set current round number"""
        self._room_data['round_number'] = round_number
        return self

    def created_ago(self, **kwargs):
        """Set creation time relative to now"""
        self._room_data['created_at'] = datetime.now() - timedelta(**kwargs)
        return self

    def last_active_ago(self, **kwargs):
        """Set last activity time relative to now"""
        self._room_data['last_activity'] = datetime.now() - timedelta(**kwargs)
        return self

    def inactive(self):
        """Mark room as inactive"""
        self._room_data['is_active'] = False
        return self

    def build(self) -> RoomData:
        """Build the room data object"""
        room = RoomData(**self._room_data)
        self.reset()  # Reset for next build
        return room


class GameStateFactory:
    """Factory for creating various game state scenarios"""

    @staticmethod
    def create_new_game_scenario() -> RoomData:
        """Create scenario for a new game starting"""
        return (RoomBuilder()
                .with_random_players(3)
                .in_phase('waiting')
                .build())

    @staticmethod
    def create_mid_game_scenario() -> RoomData:
        """Create scenario for a game in progress"""
        return (RoomBuilder()
                .with_random_players(4)
                .in_phase('responding')
                .with_prompt()
                .in_round(2)
                .build())

    @staticmethod
    def create_completion_scenario() -> RoomData:
        """Create scenario for a completed game round"""
        return (RoomBuilder()
                .with_players("Alice", "Bob", "Charlie")
                .in_phase('results')
                .with_responses("Alice's response", "Bob's response", "Charlie's response")
                .with_guesses([
                    {'player': 'Alice', 'guess_index': 1, 'correct': False},
                    {'player': 'Bob', 'guess_index': 0, 'correct': False},
                    {'player': 'Charlie', 'guess_index': 2, 'correct': True}
                ])
                .in_round(1)
                .build())

    @staticmethod
    def create_error_scenarios() -> List[RoomData]:
        """Create various error scenarios for testing"""
        return [
            # Empty room
            RoomBuilder().build(),

            # Single player (insufficient)
            RoomBuilder().with_random_players(1).build(),

            # Stale room
            (RoomBuilder()
             .with_random_players(2)
             .last_active_ago(hours=2)
             .inactive()
             .build()),

            # Room with partial responses
            (RoomBuilder()
             .with_players("Alice", "Bob", "Charlie")
             .in_phase('responding')
             .with_responses("Alice's response")
             .build()),
        ]


if __name__ == "__main__":
    # Example usage
    room = RoomFactory.create_responding_room(3)
    print(f"Created room {room.room_id} with {len(room.players)} players")

    # Using builder pattern
    custom_room = (RoomBuilder()
                   .with_id("TEST")
                   .with_players("Alice", "Bob")
                   .in_phase('guessing')
                   .with_responses("Response 1", "Response 2")
                   .build())
    print(f"Built custom room {custom_room.room_id} in {custom_room.phase} phase")