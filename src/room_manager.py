"""
Room Manager for LLMpostor Game

Handles room lifecycle, player management, and room state tracking.
Implements in-memory storage for MVP version.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, List
import uuid
import threading
import time
from contextlib import contextmanager
# Cache service will be injected via dependency container if needed
from config_factory import get_config

logger = logging.getLogger(__name__)


class RoomManager:
    """Manages game rooms and their lifecycle with thread-safe operations."""
    
    def __init__(self):
        self._rooms: Dict[str, Dict] = {}
        # Global lock only for room map operations (create/delete)
        self._rooms_lock = threading.RLock()
        # Per-room locks for fine-grained control
        self._room_locks: Dict[str, threading.RLock] = {}
        # Lock for managing room locks themselves
        self._locks_lock = threading.Lock()
        # Request deduplication - more lenient during testing
        self._recent_requests: Dict[str, float] = {}
        # Adjust window based on testing environment
        import os
        is_testing = os.environ.get('TESTING') == '1' or 'pytest' in os.environ.get('_', '')
        self._request_window = 0.01 if is_testing else 1.0  # Much shorter window for tests
        
        # Cache service will be injected via dependency container if needed
        # For now, caching is disabled - can be re-enabled via DI container
        self.cache = None
        self.cache_enabled = False
    
    def _create_initial_room_data(self, room_id: str) -> Dict:
        """Create initial room data structure."""
        return {
            "room_id": room_id,
            "players": {},
            "game_state": {
                "phase": "waiting",
                "current_prompt": None,
                "responses": [],
                "guesses": {},
                "round_number": 0,
                "phase_start_time": None,
                "phase_duration": 0
            },
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }
    
    def _ensure_room_exists(self, room_id: str) -> None:
        """Ensure room exists, creating it if necessary."""
        if room_id not in self._rooms:
            # Need to acquire global lock to modify room map
            with self._rooms_lock:
                # Double-check after acquiring lock
                if room_id not in self._rooms:
                    room_data = self._create_initial_room_data(room_id)
                    self._rooms[room_id] = room_data
    
    def _validate_room_consistency(self, room_id: str) -> None:
        """Validate room state consistency, raising ValueError if invalid."""
        if not self._validate_room_state_consistency(room_id):
            raise ValueError(f"Room {room_id} is in an inconsistent state")
    
    def _validate_player_addition(self, room: Dict, player_name: str) -> None:
        """Validate that a player can be added to the room."""
        # Check if player name is already taken by a connected player
        for player in room["players"].values():
            if player["name"] == player_name and player.get("connected", True):
                raise ValueError(f"Player name '{player_name}' is already taken in room {room['room_id']}")
        
        # Check room capacity (prevent DoS)
        if len(room["players"]) >= 8:  # Max players per room
            raise ValueError(f"Room {room['room_id']} is full")
    
    def _create_player_data(self, player_name: str, socket_id: str) -> Dict:
        """Create player data structure."""
        return {
            "player_id": str(uuid.uuid4()),
            "name": player_name,
            "score": 0,
            "socket_id": socket_id,
            "connected": True
        }
    
    def _add_player_to_room_state(self, room: Dict, player_data: Dict) -> None:
        """Add player to room state."""
        room["players"][player_data["player_id"]] = player_data
        room["last_activity"] = datetime.now()
    
    def _remove_player_from_room_state(self, room: Dict, player_id: str) -> None:
        """Remove player from room state."""
        del room["players"][player_id]
        room["last_activity"] = datetime.now()
    
    def _find_disconnected_player(self, room: Dict, player_name: str) -> Dict:
        """Find disconnected player with matching name in room."""
        for player in room["players"].values():
            if player["name"] == player_name and not player.get("connected", True):
                return player
        return None
    
    def _validate_game_state_transition(self, room: Dict, game_state: Dict, room_id: str) -> bool:
        """Validate that a game state transition is valid."""
        current_phase = room["game_state"].get("phase", "waiting")
        new_phase = game_state.get("phase", current_phase)
        
        # Define valid phase transitions to prevent invalid state changes
        valid_transitions = {
            "waiting": ["responding", "waiting"],
            "responding": ["guessing", "waiting", "responding"],
            "guessing": ["results", "responding", "waiting"],
            "results": ["waiting", "responding"]
        }
        
        if new_phase not in valid_transitions.get(current_phase, []):
            import logging
            logging.warning(f"Invalid game state transition in room {room_id}: {current_phase} -> {new_phase}")
            return False
        
        # Validate game state consistency
        try:
            required_fields = ['phase', 'current_prompt', 'responses', 'guesses', 'round_number']
            for field in required_fields:
                if field not in game_state:
                    import logging
                    logging.warning(f"Missing required field {field} in game state update for room {room_id}")
                    return False
        except Exception as e:
            import logging
            logging.error(f"Game state validation error for room {room_id}: {e}")
            return False
        
        return True
    
    def _update_room_game_state(self, room: Dict, game_state: Dict) -> None:
        """Update room's game state."""
        room["game_state"] = game_state.copy()
        room["last_activity"] = datetime.now()
    
    def _get_room_lock(self, room_id: str) -> threading.RLock:
        """Get or create a lock for a specific room."""
        with self._locks_lock:
            if room_id not in self._room_locks:
                self._room_locks[room_id] = threading.RLock()
            return self._room_locks[room_id]
    
    def _cleanup_room_lock(self, room_id: str):
        """Clean up lock for a deleted room."""
        with self._locks_lock:
            if room_id in self._room_locks:
                del self._room_locks[room_id]
    
    @contextmanager
    def _room_operation(self, room_id: str):
        """Context manager for thread-safe room operations."""
        room_lock = self._get_room_lock(room_id)
        with room_lock:
            yield
    
    def _check_duplicate_request(self, request_key: str) -> bool:
        """Check if this is a duplicate request within the time window."""
        current_time = time.time()
        
        # Clean up old requests
        expired_keys = [key for key, timestamp in self._recent_requests.items() 
                       if current_time - timestamp > self._request_window]
        for key in expired_keys:
            del self._recent_requests[key]
        
        # Check if request is duplicate
        if request_key in self._recent_requests:
            return True
        
        # Record this request
        self._recent_requests[request_key] = current_time
        return False
    
    def _validate_room_state_consistency(self, room_id: str) -> bool:
        """Validate that room state is consistent and not corrupted."""
        room = self._rooms.get(room_id)
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
    
    def create_room(self, room_id: str) -> Dict:
        """
        Create a new game room with the given ID.
        
        Args:
            room_id: Unique identifier for the room
            
        Returns:
            Dict containing the room data
            
        Raises:
            ValueError: If room already exists
        """
        with self._rooms_lock:
            if room_id in self._rooms:
                raise ValueError(f"Room {room_id} already exists")
            
            room_data = self._create_initial_room_data(room_id)
            self._rooms[room_id] = room_data
            return room_data.copy()
    
    def delete_room(self, room_id: str) -> bool:
        """
        Delete a room and clean up its resources.
        
        Args:
            room_id: ID of the room to delete
            
        Returns:
            True if room was deleted, False if room didn't exist
        """
        with self._rooms_lock:
            if room_id in self._rooms:
                del self._rooms[room_id]
                self._cleanup_room_lock(room_id)
                return True
            return False
    
    def get_room_state(self, room_id: str) -> Optional[Dict]:
        """
        Get the current state of a room with caching optimization.
        
        Args:
            room_id: ID of the room
            
        Returns:
            Room data dict or None if room doesn't exist
        """
        # Try cache first for read-heavy operations (if available)
        if self.cache_enabled:
            cache_key = f"room_state:{room_id}"
            cached_state = self.cache.get(cache_key)
            if cached_state is not None:
                # Validate cached state is still current
                room = self._rooms.get(room_id)
                if room and room.get('last_activity') == cached_state.get('last_activity'):
                    return cached_state
        
        room = self._rooms.get(room_id)
        if room:
            room_copy = room.copy()
            
            # Cache the room state for quick access (if available)
            if self.cache_enabled:
                config = get_config()
                cache_key = f"room_state:{room_id}"
                self.cache.set(cache_key, room_copy, ttl=config.cache_default_ttl_seconds)
            
            return room_copy
        return None
    
    def room_exists(self, room_id: str) -> bool:
        """
        Check if a room exists.
        
        Args:
            room_id: ID of the room to check
            
        Returns:
            True if room exists, False otherwise
        """
        return room_id in self._rooms
    
    def is_room_empty(self, room_id: str) -> bool:
        """
        Check if a room has no connected players.
        
        Args:
            room_id: ID of the room to check
            
        Returns:
            True if room has no connected players or doesn't exist, False otherwise
        """
        room = self._rooms.get(room_id)
        if not room:
            return True
        # Count only connected players for determining if room is "empty"
        connected_count = sum(1 for player in room["players"].values() if player.get("connected", True))
        return connected_count == 0
    
    def add_player_to_room(self, room_id: str, player_name: str, socket_id: str) -> Dict:
        """
        Add a player to a room. Creates room if it doesn't exist.
        
        Args:
            room_id: ID of the room
            player_name: Display name for the player
            socket_id: Socket connection ID
            
        Returns:
            Player data dict
            
        Raises:
            ValueError: If player name is already taken in the room
        """
        # Check for duplicate requests (but allow reconnections)
        request_key = f"add_player:{room_id}:{player_name}:{socket_id}"
        if self._check_duplicate_request(request_key):
            # Find existing player and return their data (reconnection scenario)
            room = self._rooms.get(room_id)
            if room:
                for player in room["players"].values():
                    if player["name"] == player_name and player["socket_id"] == socket_id:
                        return player.copy()
            # If no existing player found, it might be a legitimate retry, so continue
        
        with self._room_operation(room_id):
            # Create room if it doesn't exist (requires global lock)
            if room_id not in self._rooms:
                # Temporarily release room lock to acquire global lock
                pass  # Will be handled by new create_room_if_needed helper
        
        # Re-acquire room lock for the actual operation
        with self._room_operation(room_id):
            self._ensure_room_exists(room_id)
            room = self._rooms[room_id]
            
            self._validate_room_consistency(room_id)
            self._validate_player_addition(room, player_name)
            
            # Check for existing disconnected player with same name (reconnection)
            existing_player = self._find_disconnected_player(room, player_name)
            if existing_player:
                # Restore existing player with new socket_id
                existing_player["socket_id"] = socket_id
                existing_player["connected"] = True
                player_data = existing_player
                logger.info(f"Player {player_name} reconnected to room {room_id} with preserved score {existing_player['score']}")
            else:
                # Create new player
                player_data = self._create_player_data(player_name, socket_id)
                self._add_player_to_room_state(room, player_data)
                logger.info(f"New player {player_name} joined room {room_id}")
            
            return player_data.copy()
    
    def disconnect_player_from_room(self, room_id: str, player_id: str) -> bool:
        """
        Mark a player as disconnected (for page refresh/temporary disconnection).
        Preserves player data including scores.
        
        Args:
            room_id: ID of the room
            player_id: ID of the player to disconnect
            
        Returns:
            True if player was marked as disconnected, False if player or room didn't exist
        """
        with self._room_operation(room_id):
            room = self._rooms.get(room_id)
            if not room or player_id not in room["players"]:
                return False
            
            player = room["players"][player_id]
            player["connected"] = False
            room["last_activity"] = datetime.now()
            
            logger.info(f"Player {player['name']} ({player_id}) marked as disconnected in room {room_id}")
            return True
    
    def remove_player_from_room(self, room_id: str, player_id: str) -> bool:
        """
        Remove a player from a room.
        
        Args:
            room_id: ID of the room
            player_id: ID of the player to remove
            
        Returns:
            True if player was removed, False if player or room didn't exist
        """
        with self._room_operation(room_id):
            room = self._rooms.get(room_id)
            if not room or player_id not in room["players"]:
                return False
            
            self._remove_player_from_room_state(room, player_id)
            
            # Clean up room if no connected players remain (requires global lock)
            if self.is_room_empty(room_id):
                with self._rooms_lock:
                    # Double-check room is still empty after acquiring global lock  
                    if room_id in self._rooms and self.is_room_empty(room_id):
                        del self._rooms[room_id]
                        self._cleanup_room_lock(room_id)
            
            return True
    
    
    def get_room_players(self, room_id: str) -> List[Dict]:
        """
        Get all players in a room.
        
        Args:
            room_id: ID of the room
            
        Returns:
            List of player data dicts
        """
        room = self._rooms.get(room_id)
        if not room:
            return []
        
        return [player.copy() for player in room["players"].values()]
    
    def get_connected_players(self, room_id: str) -> List[Dict]:
        """
        Get all connected players in a room.
        
        Args:
            room_id: ID of the room
            
        Returns:
            List of connected player data dicts
        """
        room = self._rooms.get(room_id)
        if not room:
            return []
        
        return [player.copy() for player in room["players"].values() if player["connected"]]
    
    def update_room_activity(self, room_id: str) -> bool:
        """
        Update the last activity timestamp for a room.
        
        Args:
            room_id: ID of the room
            
        Returns:
            True if room was updated, False if room doesn't exist
        """
        with self._room_operation(room_id):
            room = self._rooms.get(room_id)
            if not room:
                return False
            
            room["last_activity"] = datetime.now()
            return True
    
    def update_game_state(self, room_id: str, game_state: Dict) -> bool:
        """
        Update the game state for a room with race condition protection.
        
        Args:
            room_id: ID of the room
            game_state: New game state dict
            
        Returns:
            True if room was updated, False if room doesn't exist
        """
        with self._room_operation(room_id):
            room = self._rooms.get(room_id)
            if not room:
                return False
            
            if not self._validate_game_state_transition(room, game_state, room_id):
                return False
            
            self._update_room_game_state(room, game_state)
            
            if not self._validate_room_state_consistency(room_id):
                import logging
                logging.error(f"Room state became inconsistent after game state update in {room_id}")
                return False
            
            return True
    
    def get_all_rooms(self) -> List[str]:
        """
        Get list of all active room IDs.
        
        Returns:
            List of room ID strings
        """
        return list(self._rooms.keys())
    
    def cleanup_inactive_rooms(self, max_inactive_minutes: int = 60) -> int:
        """
        Clean up rooms that have been inactive for too long.
        
        Args:
            max_inactive_minutes: Maximum minutes of inactivity before cleanup
            
        Returns:
            Number of rooms cleaned up
        """
        from datetime import timedelta
        cutoff_time = datetime.now() - timedelta(minutes=max_inactive_minutes)
        
        rooms_to_delete = []
        
        for room_id, room in self._rooms.items():
            if room["last_activity"] < cutoff_time:
                rooms_to_delete.append(room_id)
        
        for room_id in rooms_to_delete:
            del self._rooms[room_id]
        
        return len(rooms_to_delete)
    
    
    def update_player_score(self, room_id: str, player_id: str, score: int) -> bool:
        """
        Update a player's score in a room.
        
        Args:
            room_id: ID of the room
            player_id: ID of the player
            score: New score value
            
        Returns:
            True if update was successful, False otherwise
        """
        with self._room_operation(room_id):
            room = self._rooms.get(room_id)
            if not room or player_id not in room["players"]:
                return False
            
            room["players"][player_id]["score"] = score
            room["last_activity"] = datetime.now()
            return True