"""
Room Lifecycle Service for LLMpostor Game

Handles room creation, deletion, and existence checking.
Extracted from RoomManager to follow Single Responsibility Principle.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
import threading
from src.config.game_settings import get_game_settings

logger = logging.getLogger(__name__)


class RoomLifecycleService:
    """Manages room creation, deletion, and lifecycle operations."""
    
    def __init__(self):
        self._rooms: Dict[str, Dict] = {}
        self._rooms_lock = threading.RLock()
        self.game_settings = get_game_settings()
    
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
            logger.info(f"Created room {room_id}")
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
                logger.info(f"Deleted room {room_id}")
                return True
            return False
    
    def room_exists(self, room_id: str) -> bool:
        """
        Check if a room exists.
        
        Args:
            room_id: ID of the room to check
            
        Returns:
            True if room exists, False otherwise
        """
        return room_id in self._rooms
    
    def ensure_room_exists(self, room_id: str) -> None:
        """Ensure room exists, creating it if necessary."""
        if room_id not in self._rooms:
            with self._rooms_lock:
                # Double-check after acquiring lock
                if room_id not in self._rooms:
                    room_data = self._create_initial_room_data(room_id)
                    self._rooms[room_id] = room_data
                    logger.info(f"Auto-created room {room_id}")
    
    def get_room_data(self, room_id: str) -> Optional[Dict]:
        """
        Get room data (internal access for other services).
        
        Args:
            room_id: ID of the room
            
        Returns:
            Room data dict or None if room doesn't exist
        """
        return self._rooms.get(room_id)
    
    def get_all_room_ids(self) -> List[str]:
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
        
        cleaned_count = 0
        with self._rooms_lock:
            for room_id in rooms_to_delete:
                if room_id in self._rooms:
                    del self._rooms[room_id]
                    cleaned_count += 1
                    logger.info(f"Cleaned up inactive room {room_id}")
        
        return cleaned_count