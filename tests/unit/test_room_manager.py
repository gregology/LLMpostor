"""
Unit tests for RoomManager class.
"""

import pytest
from datetime import datetime, timedelta

from src.room_manager import RoomManager


class TestRoomManager:
    """Test cases for RoomManager functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
    
    def test_create_room_success(self):
        """Test successful room creation."""
        room_id = "test_room"
        room_data = self.room_manager.create_room(room_id)
        
        assert room_data["room_id"] == room_id
        assert room_data["players"] == {}
        assert room_data["game_state"]["phase"] == "waiting"
        assert room_data["game_state"]["round_number"] == 0
        assert isinstance(room_data["created_at"], datetime)
        assert isinstance(room_data["last_activity"], datetime)
    
    def test_create_room_duplicate_fails(self):
        """Test that creating duplicate room raises error."""
        room_id = "test_room"
        self.room_manager.create_room(room_id)
        
        with pytest.raises(ValueError, match="Room test_room already exists"):
            self.room_manager.create_room(room_id)
    
    def test_delete_room_success(self):
        """Test successful room deletion."""
        room_id = "test_room"
        self.room_manager.create_room(room_id)
        
        result = self.room_manager.delete_room(room_id)
        assert result is True
        assert not self.room_manager.room_exists(room_id)
    
    def test_delete_nonexistent_room(self):
        """Test deleting non-existent room returns False."""
        result = self.room_manager.delete_room("nonexistent")
        assert result is False
    
    def test_get_room_state_success(self):
        """Test getting room state for existing room."""
        room_id = "test_room"
        original_room = self.room_manager.create_room(room_id)
        
        room_state = self.room_manager.get_room_state(room_id)
        assert room_state is not None
        assert room_state["room_id"] == room_id
        # Ensure it's a copy, not the original
        assert room_state is not original_room
    
    def test_get_room_state_nonexistent(self):
        """Test getting room state for non-existent room returns None."""
        room_state = self.room_manager.get_room_state("nonexistent")
        assert room_state is None
    
    def test_room_exists(self):
        """Test room existence checking."""
        room_id = "test_room"
        
        assert not self.room_manager.room_exists(room_id)
        
        self.room_manager.create_room(room_id)
        assert self.room_manager.room_exists(room_id)
        
        self.room_manager.delete_room(room_id)
        assert not self.room_manager.room_exists(room_id)
    
    def test_is_room_empty_new_room(self):
        """Test that newly created room is empty."""
        room_id = "test_room"
        self.room_manager.create_room(room_id)
        
        assert self.room_manager.is_room_empty(room_id)
    
    def test_is_room_empty_nonexistent(self):
        """Test that non-existent room is considered empty."""
        assert self.room_manager.is_room_empty("nonexistent")
    
    def test_add_player_to_room_new_room(self):
        """Test adding player to non-existent room creates room."""
        room_id = "test_room"
        player_name = "TestPlayer"
        socket_id = "socket123"
        
        player_data = self.room_manager.add_player_to_room(room_id, player_name, socket_id)
        
        assert player_data["name"] == player_name
        assert player_data["socket_id"] == socket_id
        assert player_data["score"] == 0
        assert player_data["connected"] is True
        assert "player_id" in player_data
        
        # Verify room was created
        assert self.room_manager.room_exists(room_id)
        assert not self.room_manager.is_room_empty(room_id)
    
    def test_add_player_to_existing_room(self):
        """Test adding player to existing room."""
        room_id = "test_room"
        self.room_manager.create_room(room_id)
        
        player_data = self.room_manager.add_player_to_room(room_id, "Player1", "socket1")
        
        assert player_data["name"] == "Player1"
        assert not self.room_manager.is_room_empty(room_id)
    
    def test_add_duplicate_player_name_fails(self):
        """Test that adding player with duplicate name fails."""
        room_id = "test_room"
        player_name = "TestPlayer"
        
        self.room_manager.add_player_to_room(room_id, player_name, "socket1")
        
        with pytest.raises(ValueError, match="Player name 'TestPlayer' is already taken"):
            self.room_manager.add_player_to_room(room_id, player_name, "socket2")
    
    def test_remove_player_from_room_success(self):
        """Test successful player removal."""
        room_id = "test_room"
        player_data = self.room_manager.add_player_to_room(room_id, "Player1", "socket1")
        player_id = player_data["player_id"]
        
        result = self.room_manager.remove_player_from_room(room_id, player_id)
        assert result is True
        
        # Room should be deleted when empty (per implementation)
        assert not self.room_manager.room_exists(room_id)
    
    def test_remove_player_cleans_up_empty_room(self):
        """Test that removing last player cleans up room."""
        room_id = "test_room"
        player_data = self.room_manager.add_player_to_room(room_id, "Player1", "socket1")
        player_id = player_data["player_id"]
        
        self.room_manager.remove_player_from_room(room_id, player_id)
        
        # Room should be deleted when empty
        assert not self.room_manager.room_exists(room_id)
    
    def test_remove_nonexistent_player(self):
        """Test removing non-existent player returns False."""
        room_id = "test_room"
        self.room_manager.create_room(room_id)
        
        result = self.room_manager.remove_player_from_room(room_id, "nonexistent_player")
        assert result is False
    
    def test_remove_player_from_nonexistent_room(self):
        """Test removing player from non-existent room returns False."""
        result = self.room_manager.remove_player_from_room("nonexistent", "player_id")
        assert result is False
    
    
    def test_get_room_players(self):
        """Test getting all players in a room."""
        room_id = "test_room"
        
        # Empty room
        players = self.room_manager.get_room_players(room_id)
        assert players == []
        
        # Add players
        player1 = self.room_manager.add_player_to_room(room_id, "Player1", "socket1")
        player2 = self.room_manager.add_player_to_room(room_id, "Player2", "socket2")
        
        players = self.room_manager.get_room_players(room_id)
        assert len(players) == 2
        
        player_names = [p["name"] for p in players]
        assert "Player1" in player_names
        assert "Player2" in player_names
    
    def test_get_connected_players(self):
        """Test getting only connected players."""
        room_id = "test_room"
        
        # Add players
        player1 = self.room_manager.add_player_to_room(room_id, "Player1", "socket1")
        player2 = self.room_manager.add_player_to_room(room_id, "Player2", "socket2")
        
        # Disconnect one player
        self.room_manager.disconnect_player_from_room(room_id, player1["player_id"])
        
        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 1
        assert connected_players[0]["name"] == "Player2"
        assert connected_players[0]["connected"] is True
    
    def test_update_room_activity(self):
        """Test updating room activity timestamp."""
        room_id = "test_room"
        room_data = self.room_manager.create_room(room_id)
        original_activity = room_data["last_activity"]
        
        # Wait a bit to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        result = self.room_manager.update_room_activity(room_id)
        assert result is True
        
        updated_room = self.room_manager.get_room_state(room_id)
        assert updated_room["last_activity"] > original_activity
    
    def test_get_all_rooms(self):
        """Test getting list of all room IDs."""
        # No rooms initially
        rooms = self.room_manager.get_all_rooms()
        assert rooms == []
        
        # Create some rooms
        self.room_manager.create_room("room1")
        self.room_manager.create_room("room2")
        
        rooms = self.room_manager.get_all_rooms()
        assert len(rooms) == 2
        assert "room1" in rooms
        assert "room2" in rooms
    
    def test_cleanup_inactive_rooms(self):
        """Test cleanup of inactive rooms."""
        # Create room and modify its last_activity to be old
        room_id = "old_room"
        self.room_manager.create_room(room_id)
        
        # Manually set old timestamp (accessing internal state for testing)
        old_time = datetime.now() - timedelta(hours=2)
        self.room_manager._rooms[room_id]["last_activity"] = old_time
        
        # Create a recent room
        self.room_manager.create_room("new_room")
        
        # Cleanup rooms older than 1 hour
        cleaned_count = self.room_manager.cleanup_inactive_rooms(max_inactive_minutes=60)
        
        assert cleaned_count == 1
        assert not self.room_manager.room_exists("old_room")
        assert self.room_manager.room_exists("new_room")
    
    def test_multiple_players_different_rooms(self):
        """Test that players in different rooms don't interfere."""
        # Add players to different rooms
        player1 = self.room_manager.add_player_to_room("room1", "Player1", "socket1")
        player2 = self.room_manager.add_player_to_room("room2", "Player1", "socket2")  # Same name, different room
        
        # Both should succeed
        assert player1["name"] == "Player1"
        assert player2["name"] == "Player1"
        assert player1["player_id"] != player2["player_id"]
        
        # Rooms should be separate
        room1_players = self.room_manager.get_room_players("room1")
        room2_players = self.room_manager.get_room_players("room2")
        
        assert len(room1_players) == 1
        assert len(room2_players) == 1
        assert room1_players[0]["player_id"] != room2_players[0]["player_id"]
