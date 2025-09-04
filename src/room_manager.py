"""
Room Manager for LLMposter Game

Handles room lifecycle, player management, and room state tracking.
Implements in-memory storage for MVP version.
"""

from datetime import datetime
from typing import Dict, Optional, List
import uuid


class RoomManager:
    """Manages game rooms and their lifecycle."""
    
    def __init__(self):
        self._rooms: Dict[str, Dict] = {}
    
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
        if room_id in self._rooms:
            del self._rooms[room_id]
            return True
        return False
    
    def get_room_state(self, room_id: str) -> Optional[Dict]:
        """
        Get the current state of a room.
        
        Args:
            room_id: ID of the room
            
        Returns:
            Room data dict or None if room doesn't exist
        """
        room = self._rooms.get(room_id)
        return room.copy() if room else None
    
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
        # Create room if it doesn't exist
        if room_id not in self._rooms:
            self.create_room(room_id)
        
        room = self._rooms[room_id]
        
        # Check if player name is already taken
        for player in room["players"].values():
            if player["name"] == player_name:
                raise ValueError(f"Player name '{player_name}' is already taken in room {room_id}")
        
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
        Update the game state for a room.
        
        Args:
            room_id: ID of the room
            game_state: New game state dict
            
        Returns:
            True if room was updated, False if room doesn't exist
        """
        room = self._rooms.get(room_id)
        if not room:
            return False
        
        room["game_state"] = game_state.copy()
        room["last_activity"] = datetime.now()
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
        if room_id not in self._rooms:
            return False
        
        room = self._rooms[room_id]
        
        if player_id not in room["players"]:
            return False
        
        room["players"][player_id]["score"] = score
        room["last_activity"] = datetime.now()
        return True