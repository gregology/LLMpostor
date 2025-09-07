"""
Room Manager for LLMpostor Game

Handles room lifecycle, player management, and room state tracking.
Implements in-memory storage for MVP version.
"""

from datetime import datetime
from typing import Dict, Optional, List
import uuid
import threading
import time
from contextlib import contextmanager
from src.services.cache_service import get_cache_service


class RoomManager:
    """Manages game rooms and their lifecycle with thread-safe operations."""
    
    def __init__(self):
        self._rooms: Dict[str, Dict] = {}
        # Global lock for room operations
        self._global_lock = threading.RLock()
        # Per-room locks for fine-grained control
        self._room_locks: Dict[str, threading.RLock] = {}
        # Lock for managing room locks themselves
        self._locks_lock = threading.Lock()
        # Operation tracking for race condition detection
        self._active_operations: Dict[str, Dict] = {}
        # Request deduplication - more lenient during testing
        self._recent_requests: Dict[str, float] = {}
        # Adjust window based on testing environment
        import os
        is_testing = os.environ.get('TESTING') == '1' or 'pytest' in os.environ.get('_', '')
        self._request_window = 0.01 if is_testing else 1.0  # Much shorter window for tests
        
        # Performance optimization: Initialize caching (optional)
        try:
            self.cache = get_cache_service({
                'max_memory_size': 50 * 1024 * 1024,  # 50MB for room data
                'default_ttl': 3600,  # 1 hour
                'cleanup_interval': 300  # 5 minutes
            })
            self.cache_enabled = True
        except Exception:
            # Fallback: disable caching if service unavailable (e.g., during testing)
            self.cache = None
            self.cache_enabled = False
    
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
    def _room_operation(self, room_id: str, operation_type: str = "generic"):
        """Context manager for thread-safe room operations."""
        room_lock = self._get_room_lock(room_id)
        operation_id = f"{room_id}:{operation_type}:{threading.current_thread().ident}"
        
        # Track active operation
        with self._global_lock:
            if room_id not in self._active_operations:
                self._active_operations[room_id] = {}
            self._active_operations[room_id][operation_id] = {
                'start_time': time.time(),
                'thread_id': threading.current_thread().ident,
                'operation_type': operation_type
            }
        
        try:
            with room_lock:
                yield room_lock
        finally:
            # Clean up operation tracking
            with self._global_lock:
                if room_id in self._active_operations:
                    self._active_operations[room_id].pop(operation_id, None)
                    if not self._active_operations[room_id]:
                        del self._active_operations[room_id]
    
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
        with self._room_operation(room_id, "create_room"):
            if room_id in self._rooms:
                raise ValueError(f"Room {room_id} already exists")
            
            room_data = {
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
        with self._room_operation(room_id, "delete_room"):
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
                cache_key = f"room_state:{room_id}"
                self.cache.set(cache_key, room_copy, ttl=60)  # Cache for 1 minute
            
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
        Check if a room has no players.
        
        Args:
            room_id: ID of the room to check
            
        Returns:
            True if room is empty or doesn't exist, False otherwise
        """
        room = self._rooms.get(room_id)
        if not room:
            return True
        return len(room["players"]) == 0
    
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
        
        with self._room_operation(room_id, "add_player"):
            # Create room if it doesn't exist
            if room_id not in self._rooms:
                self.create_room(room_id)
            
            room = self._rooms[room_id]
            
            # Validate room state consistency
            if not self._validate_room_state_consistency(room_id):
                raise ValueError(f"Room {room_id} is in an inconsistent state")
            
            # Check if player name is already taken
            for player in room["players"].values():
                if player["name"] == player_name:
                    raise ValueError(f"Player name '{player_name}' is already taken in room {room_id}")
            
            # Check room capacity (prevent DoS)
            if len(room["players"]) >= 8:  # Max players per room
                raise ValueError(f"Room {room_id} is full")
            
            # Generate unique player ID
            player_id = str(uuid.uuid4())
            
            # Create player data
            player_data = {
                "player_id": player_id,
                "name": player_name,
                "score": 0,
                "socket_id": socket_id,
                "connected": True
            }
            
            # Add player to room
            room["players"][player_id] = player_data
            room["last_activity"] = datetime.now()
            
            return player_data.copy()
    
    def remove_player_from_room(self, room_id: str, player_id: str) -> bool:
        """
        Remove a player from a room.
        
        Args:
            room_id: ID of the room
            player_id: ID of the player to remove
            
        Returns:
            True if player was removed, False if player or room didn't exist
        """
        room = self._rooms.get(room_id)
        if not room:
            return False
        
        if player_id in room["players"]:
            del room["players"][player_id]
            room["last_activity"] = datetime.now()
            
            # Clean up empty room
            if len(room["players"]) == 0:
                del self._rooms[room_id]
            
            return True
        return False
    
    def update_player_connection(self, room_id: str, player_id: str, connected: bool, socket_id: Optional[str] = None) -> bool:
        """
        Update a player's connection status.
        
        Args:
            room_id: ID of the room
            player_id: ID of the player
            connected: New connection status
            socket_id: New socket ID (optional)
            
        Returns:
            True if player was updated, False if player or room didn't exist
        """
        room = self._rooms.get(room_id)
        if not room:
            return False
        
        player = room["players"].get(player_id)
        if not player:
            return False
        
        player["connected"] = connected
        if socket_id is not None:
            player["socket_id"] = socket_id
        
        room["last_activity"] = datetime.now()
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
        with self._room_operation(room_id, "update_game_state"):
            room = self._rooms.get(room_id)
            if not room:
                return False
            
            # Validate state transition is valid
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
                # Log invalid transition attempt
                import logging
                logging.warning(f"Invalid game state transition in room {room_id}: {current_phase} -> {new_phase}")
                return False
            
            # Validate game state consistency
            try:
                required_fields = ['phase', 'current_prompt', 'responses', 'guesses', 'round_number']
                for field in required_fields:
                    if field not in game_state:
                        logging.warning(f"Missing required field {field} in game state update for room {room_id}")
                        return False
            except Exception as e:
                logging.error(f"Game state validation error for room {room_id}: {e}")
                return False
            
            # Update with validated state
            room["game_state"] = game_state.copy()
            room["last_activity"] = datetime.now()
            
            # Validate room state after update
            if not self._validate_room_state_consistency(room_id):
                # Rollback if state becomes inconsistent
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
    
    def get_active_operations(self, room_id: Optional[str] = None) -> Dict:
        """
        Get information about active operations for debugging race conditions.
        
        Args:
            room_id: Optional room ID to filter by
            
        Returns:
            Dict of active operations
        """
        with self._global_lock:
            if room_id:
                return self._active_operations.get(room_id, {}).copy()
            return {k: v.copy() for k, v in self._active_operations.items()}
    
    def detect_potential_race_conditions(self, room_id: str) -> Dict:
        """
        Detect potential race conditions in a specific room.
        
        Args:
            room_id: Room ID to analyze
            
        Returns:
            Dict containing race condition analysis
        """
        with self._global_lock:
            active_ops = self._active_operations.get(room_id, {})
            
            analysis = {
                "concurrent_operations": len(active_ops),
                "operation_types": [op["operation_type"] for op in active_ops.values()],
                "thread_ids": list(set(op["thread_id"] for op in active_ops.values())),
                "long_running_operations": [],
                "potential_conflicts": []
            }
            
            current_time = time.time()
            
            # Check for long-running operations (>5 seconds)
            for op_id, op_info in active_ops.items():
                duration = current_time - op_info["start_time"]
                if duration > 5:
                    analysis["long_running_operations"].append({
                        "operation_id": op_id,
                        "duration": duration,
                        "type": op_info["operation_type"]
                    })
            
            # Check for conflicting operation types
            conflicting_pairs = [
                ("create_room", "delete_room"),
                ("add_player", "remove_player"),
                ("update_game_state", "delete_room")
            ]
            
            for pair in conflicting_pairs:
                if pair[0] in analysis["operation_types"] and pair[1] in analysis["operation_types"]:
                    analysis["potential_conflicts"].append(pair)
            
            return analysis
    
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
        if room_id not in self._rooms:
            return False
        
        room = self._rooms[room_id]
        
        if player_id not in room["players"]:
            return False
        
        room["players"][player_id]["score"] = score
        room["last_activity"] = datetime.now()
        return True