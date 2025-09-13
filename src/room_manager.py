"""
Room Manager for LLMpostor Game - Refactored

Coordinates specialized services to maintain existing API while improving separation of concerns.
Acts as a facade over the decomposed services.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, List

from src.services.room_lifecycle_service import RoomLifecycleService
from src.services.player_management_service import PlayerManagementService
from src.services.room_state_service import RoomStateService
from src.services.concurrency_control_service import ConcurrencyControlService

logger = logging.getLogger(__name__)


class RoomManager:
    """Manages game rooms and their lifecycle with thread-safe operations."""
    
    def __init__(self):
        # Initialize services
        self.concurrency_control = ConcurrencyControlService()
        self.lifecycle = RoomLifecycleService()
        self.state = RoomStateService(self.lifecycle, self.concurrency_control)
        self.players = PlayerManagementService(self.lifecycle, self.concurrency_control)
    
    # Room Lifecycle Operations
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
        return self.lifecycle.create_room(room_id)
    
    def delete_room(self, room_id: str) -> bool:
        """
        Delete a room and clean up its resources.
        
        Args:
            room_id: ID of the room to delete
            
        Returns:
            True if room was deleted, False if room didn't exist
        """
        result = self.lifecycle.delete_room(room_id)
        if result:
            self.concurrency_control.cleanup_room_lock(room_id)
        return result
    
    def room_exists(self, room_id: str) -> bool:
        """
        Check if a room exists.
        
        Args:
            room_id: ID of the room to check
            
        Returns:
            True if room exists, False otherwise
        """
        return self.lifecycle.room_exists(room_id)
    
    def get_all_rooms(self) -> List[str]:
        """
        Get list of all active room IDs.
        
        Returns:
            List of room ID strings
        """
        return self.lifecycle.get_all_room_ids()
    
    def cleanup_inactive_rooms(self, max_inactive_minutes: int = 60) -> int:
        """
        Clean up rooms that have been inactive for too long.
        
        Args:
            max_inactive_minutes: Maximum minutes of inactivity before cleanup
            
        Returns:
            Number of rooms cleaned up
        """
        return self.lifecycle.cleanup_inactive_rooms(max_inactive_minutes)
    
    # Room State Operations
    def get_room_state(self, room_id: str) -> Optional[Dict]:
        """
        Get the current state of a room with caching optimization.
        
        Args:
            room_id: ID of the room
            
        Returns:
            Room data dict or None if room doesn't exist
        """
        return self.state.get_room_state(room_id)
    
    def update_game_state(self, room_id: str, game_state: Dict) -> bool:
        """
        Update the game state for a room with race condition protection.
        
        Args:
            room_id: ID of the room
            game_state: New game state dict
            
        Returns:
            True if room was updated, False if room doesn't exist
        """
        return self.state.update_game_state(room_id, game_state)
    
    def update_room_activity(self, room_id: str) -> bool:
        """
        Update the last activity timestamp for a room.
        
        Args:
            room_id: ID of the room
            
        Returns:
            True if room was updated, False if room doesn't exist
        """
        return self.state.update_room_activity(room_id)
    
    # Player Management Operations
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
        return self.players.add_player_to_room(room_id, player_name, socket_id)
    
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
        return self.players.disconnect_player_from_room(room_id, player_id)
    
    def remove_player_from_room(self, room_id: str, player_id: str) -> bool:
        """
        Remove a player from a room.
        
        Args:
            room_id: ID of the room
            player_id: ID of the player to remove
            
        Returns:
            True if player was removed, False if player or room didn't exist
        """
        return self.players.remove_player_from_room(room_id, player_id)
    
    def get_room_players(self, room_id: str) -> List[Dict]:
        """
        Get all players in a room.
        
        Args:
            room_id: ID of the room
            
        Returns:
            List of player data dicts
        """
        return self.players.get_room_players(room_id)
    
    def get_connected_players(self, room_id: str) -> List[Dict]:
        """
        Get all connected players in a room.
        
        Args:
            room_id: ID of the room
            
        Returns:
            List of connected player data dicts
        """
        return self.players.get_connected_players(room_id)
    
    def is_room_empty(self, room_id: str) -> bool:
        """
        Check if a room has no connected players.
        
        Args:
            room_id: ID of the room to check
            
        Returns:
            True if room has no connected players or doesn't exist, False otherwise
        """
        return self.players.is_room_empty(room_id)
    
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
        return self.players.update_player_score(room_id, player_id, score)
    
    # Test compatibility properties and methods
    @property 
    def _rooms(self):
        """Access to internal rooms data for test compatibility."""
        return self.lifecycle._rooms
    
    def _get_room_lock(self, room_id: str):
        """Access to room locks for test compatibility."""
        return self.concurrency_control.get_room_lock(room_id)
    
    def _room_operation(self, room_id: str):
        """Access to room operation context manager for test compatibility."""
        return self.concurrency_control.room_operation(room_id)