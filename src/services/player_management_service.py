"""
Player Management Service for LLMpostor Game

Handles player addition, removal, disconnection, and reconnection logic.
Extracted from RoomManager to follow Single Responsibility Principle.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
import uuid
import threading
from src.config.game_settings import get_game_settings

logger = logging.getLogger(__name__)


class PlayerManagementService:
    """Manages player operations within rooms."""
    
    def __init__(self, room_lifecycle_service, concurrency_control_service):
        self.room_lifecycle_service = room_lifecycle_service
        self.concurrency_control_service = concurrency_control_service
        self.game_settings = get_game_settings()
    
    def _create_player_data(self, player_name: str, socket_id: str) -> Dict:
        """Create player data structure."""
        return {
            "player_id": str(uuid.uuid4()),
            "name": player_name,
            "score": 0,
            "socket_id": socket_id,
            "connected": True
        }
    
    def _validate_player_addition(self, room: Dict, player_name: str) -> None:
        """Validate that a player can be added to the room."""
        # Check if player name is already taken by a connected player
        for player in room["players"].values():
            if player["name"] == player_name and player.get("connected", True):
                raise ValueError(f"Player name '{player_name}' is already taken in room {room['room_id']}")
        
        # Check room capacity (prevent DoS)
        max_players = self.game_settings.max_players_per_room
        if len(room["players"]) >= max_players:
            raise ValueError(f"Room {room['room_id']} is full")
    
    def _find_disconnected_player(self, room: Dict, player_name: str) -> Optional[Dict]:
        """Find disconnected player with matching name in room."""
        for player in room["players"].values():
            if player["name"] == player_name and not player.get("connected", True):
                return player
        return None
    
    def _add_player_to_room_state(self, room: Dict, player_data: Dict) -> None:
        """Add player to room state."""
        room["players"][player_data["player_id"]] = player_data
        room["last_activity"] = datetime.now()
    
    def _remove_player_from_room_state(self, room: Dict, player_id: str) -> None:
        """Remove player from room state."""
        if player_id in room["players"]:
            del room["players"][player_id]
            room["last_activity"] = datetime.now()
    
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
        if self.concurrency_control_service.check_duplicate_request(request_key):
            # Find existing player and return their data (reconnection scenario)
            room = self.room_lifecycle_service.get_room_data(room_id)
            if room:
                for player in room["players"].values():
                    if player["name"] == player_name and player["socket_id"] == socket_id:
                        return player.copy()
        
        with self.concurrency_control_service.room_operation(room_id):
            # Ensure room exists
            self.room_lifecycle_service.ensure_room_exists(room_id)
            room = self.room_lifecycle_service.get_room_data(room_id)
            
            self._validate_player_addition(room, player_name)
            
            # Check for existing disconnected player with same name (reconnection)
            existing_player = self._find_disconnected_player(room, player_name)
            if existing_player:
                # Restore existing player with new socket_id
                existing_player["socket_id"] = socket_id
                existing_player["connected"] = True
                room["last_activity"] = datetime.now()
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
        with self.concurrency_control_service.room_operation(room_id):
            room = self.room_lifecycle_service.get_room_data(room_id)
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
        with self.concurrency_control_service.room_operation(room_id):
            room = self.room_lifecycle_service.get_room_data(room_id)
            if not room or player_id not in room["players"]:
                return False
            
            self._remove_player_from_room_state(room, player_id)
            
            # Check if room should be cleaned up
            if self.is_room_empty(room_id):
                self.room_lifecycle_service.delete_room(room_id)
            
            return True
    
    def get_room_players(self, room_id: str) -> List[Dict]:
        """
        Get all players in a room.
        
        Args:
            room_id: ID of the room
            
        Returns:
            List of player data dicts
        """
        room = self.room_lifecycle_service.get_room_data(room_id)
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
        room = self.room_lifecycle_service.get_room_data(room_id)
        if not room:
            return []
        
        return [player.copy() for player in room["players"].values() if player["connected"]]
    
    def is_room_empty(self, room_id: str) -> bool:
        """
        Check if a room has no connected players.
        
        Args:
            room_id: ID of the room to check
            
        Returns:
            True if room has no connected players or doesn't exist, False otherwise
        """
        room = self.room_lifecycle_service.get_room_data(room_id)
        if not room:
            return True
        # Count only connected players for determining if room is "empty"
        connected_count = sum(1 for player in room["players"].values() if player.get("connected", True))
        return connected_count == 0
    
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
        with self.concurrency_control_service.room_operation(room_id):
            room = self.room_lifecycle_service.get_room_data(room_id)
            if not room or player_id not in room["players"]:
                return False
            
            room["players"][player_id]["score"] = score
            room["last_activity"] = datetime.now()
            return True