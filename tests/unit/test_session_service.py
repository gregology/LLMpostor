"""
Session Service Unit Tests
Tests for the player session management service.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.services.session_service import SessionService


class TestSessionService:
    """Test SessionService basic functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.session_service = SessionService()

    def test_initialization(self):
        """Test session service initialization"""
        assert self.session_service._player_sessions == {}
        assert self.session_service.get_sessions_count() == 0

    def test_create_session_success(self):
        """Test successful session creation"""
        socket_id = "socket123"
        room_id = "room456"
        player_id = "player789"
        player_name = "TestPlayer"
        
        self.session_service.create_session(socket_id, room_id, player_id, player_name)
        
        # Verify session was created
        session = self.session_service.get_session(socket_id)
        assert session is not None
        assert session['room_id'] == room_id
        assert session['player_id'] == player_id
        assert session['player_name'] == player_name

    def test_create_session_update_existing(self):
        """Test updating an existing session"""
        socket_id = "socket123"
        
        # Create initial session
        self.session_service.create_session(socket_id, "room1", "player1", "Name1")
        assert self.session_service.get_sessions_count() == 1
        
        # Update session with new data
        self.session_service.create_session(socket_id, "room2", "player2", "Name2")
        assert self.session_service.get_sessions_count() == 1  # Should still be 1
        
        # Verify updated data
        session = self.session_service.get_session(socket_id)
        assert session['room_id'] == "room2"
        assert session['player_id'] == "player2"
        assert session['player_name'] == "Name2"

    def test_create_session_handles_exception(self):
        """Test create_session handles exceptions gracefully"""
        # Mock an internal error
        with patch.object(self.session_service, '_player_sessions') as mock_sessions:
            mock_sessions.__setitem__.side_effect = Exception("Storage error")
            
            # Should not raise exception (error is caught and logged)
            self.session_service.create_session("socket123", "room456", "player789", "TestPlayer")

    def test_get_session_existing(self):
        """Test getting existing session"""
        socket_id = "socket123"
        room_id = "room456"
        player_id = "player789"
        player_name = "TestPlayer"
        
        # Create session first
        self.session_service.create_session(socket_id, room_id, player_id, player_name)
        
        # Get session
        session = self.session_service.get_session(socket_id)
        assert session is not None
        assert session['room_id'] == room_id
        assert session['player_id'] == player_id
        assert session['player_name'] == player_name

    def test_get_session_nonexistent(self):
        """Test getting nonexistent session"""
        session = self.session_service.get_session("nonexistent")
        assert session is None

    def test_get_session_data_existing(self):
        """Test getting session data as tuple for existing session"""
        socket_id = "socket123"
        room_id = "room456"
        player_id = "player789"
        player_name = "TestPlayer"
        
        # Create session first
        self.session_service.create_session(socket_id, room_id, player_id, player_name)
        
        # Get session data
        room, player, name = self.session_service.get_session_data(socket_id)
        assert room == room_id
        assert player == player_id
        assert name == player_name

    def test_get_session_data_nonexistent(self):
        """Test getting session data for nonexistent session"""
        room, player, name = self.session_service.get_session_data("nonexistent")
        assert room is None
        assert player is None
        assert name is None

    def test_has_session_existing(self):
        """Test has_session for existing session"""
        socket_id = "socket123"
        
        # Initially should not exist
        assert self.session_service.has_session(socket_id) is False
        
        # Create session
        self.session_service.create_session(socket_id, "room456", "player789", "TestPlayer")
        
        # Should now exist
        assert self.session_service.has_session(socket_id) is True

    def test_has_session_nonexistent(self):
        """Test has_session for nonexistent session"""
        assert self.session_service.has_session("nonexistent") is False

    def test_remove_session_existing(self):
        """Test removing existing session"""
        socket_id = "socket123"
        room_id = "room456"
        player_id = "player789"
        player_name = "TestPlayer"
        
        # Create session first
        self.session_service.create_session(socket_id, room_id, player_id, player_name)
        assert self.session_service.has_session(socket_id) is True
        
        # Remove session
        removed_session = self.session_service.remove_session(socket_id)
        
        # Verify removed session data
        assert removed_session is not None
        assert removed_session['room_id'] == room_id
        assert removed_session['player_id'] == player_id
        assert removed_session['player_name'] == player_name
        
        # Verify session is gone
        assert self.session_service.has_session(socket_id) is False
        assert self.session_service.get_sessions_count() == 0

    def test_remove_session_nonexistent(self):
        """Test removing nonexistent session"""
        removed_session = self.session_service.remove_session("nonexistent")
        assert removed_session is None

    def test_remove_session_handles_exception(self):
        """Test remove_session handles exceptions gracefully"""
        # Create a session first
        self.session_service.create_session("socket123", "room456", "player789", "TestPlayer")
        
        # Create a mock dict that raises exception on pop
        mock_sessions = Mock()
        mock_sessions.pop.side_effect = Exception("Pop error")
        
        # Replace the _player_sessions dict
        original_sessions = self.session_service._player_sessions
        self.session_service._player_sessions = mock_sessions
        
        try:
            result = self.session_service.remove_session("socket123")
            assert result is None
        finally:
            # Restore original sessions
            self.session_service._player_sessions = original_sessions

    def test_get_all_sessions(self):
        """Test getting all active sessions"""
        # Initially should be empty
        all_sessions = self.session_service.get_all_sessions()
        assert all_sessions == {}
        
        # Create multiple sessions
        self.session_service.create_session("socket1", "room1", "player1", "Name1")
        self.session_service.create_session("socket2", "room1", "player2", "Name2")
        self.session_service.create_session("socket3", "room2", "player3", "Name3")
        
        # Get all sessions
        all_sessions = self.session_service.get_all_sessions()
        assert len(all_sessions) == 3
        
        # Verify structure is correct
        assert "socket1" in all_sessions
        assert all_sessions["socket1"]["room_id"] == "room1"
        assert all_sessions["socket1"]["player_id"] == "player1"
        assert all_sessions["socket1"]["player_name"] == "Name1"

    def test_get_sessions_count(self):
        """Test getting session count"""
        assert self.session_service.get_sessions_count() == 0
        
        # Add sessions
        self.session_service.create_session("socket1", "room1", "player1", "Name1")
        assert self.session_service.get_sessions_count() == 1
        
        self.session_service.create_session("socket2", "room1", "player2", "Name2")
        assert self.session_service.get_sessions_count() == 2
        
        # Remove session
        self.session_service.remove_session("socket1")
        assert self.session_service.get_sessions_count() == 1

    def test_get_sessions_by_room(self):
        """Test getting sessions filtered by room"""
        # Create sessions in different rooms
        self.session_service.create_session("socket1", "room1", "player1", "Name1")
        self.session_service.create_session("socket2", "room1", "player2", "Name2")
        self.session_service.create_session("socket3", "room2", "player3", "Name3")
        self.session_service.create_session("socket4", "room2", "player4", "Name4")
        self.session_service.create_session("socket5", "room3", "player5", "Name5")
        
        # Get sessions for room1
        room1_sessions = self.session_service.get_sessions_by_room("room1")
        assert len(room1_sessions) == 2
        assert "socket1" in room1_sessions
        assert "socket2" in room1_sessions
        assert room1_sessions["socket1"]["room_id"] == "room1"
        assert room1_sessions["socket2"]["room_id"] == "room1"
        
        # Get sessions for room2
        room2_sessions = self.session_service.get_sessions_by_room("room2")
        assert len(room2_sessions) == 2
        assert "socket3" in room2_sessions
        assert "socket4" in room2_sessions
        
        # Get sessions for nonexistent room
        empty_sessions = self.session_service.get_sessions_by_room("nonexistent")
        assert len(empty_sessions) == 0

    def test_cleanup_stale_sessions(self):
        """Test cleaning up stale sessions"""
        # Create multiple sessions
        self.session_service.create_session("socket1", "room1", "player1", "Name1")
        self.session_service.create_session("socket2", "room1", "player2", "Name2")
        self.session_service.create_session("socket3", "room2", "player3", "Name3")
        self.session_service.create_session("socket4", "room2", "player4", "Name4")
        
        assert self.session_service.get_sessions_count() == 4
        
        # Simulate some sockets being active, others stale
        active_sockets = {"socket1", "socket3", "socket5"}  # socket5 doesn't exist
        
        cleaned_count = self.session_service.cleanup_stale_sessions(active_sockets)
        
        # Should have cleaned up socket2 and socket4 (2 sessions)
        assert cleaned_count == 2
        assert self.session_service.get_sessions_count() == 2
        
        # Verify correct sessions remain
        assert self.session_service.has_session("socket1") is True
        assert self.session_service.has_session("socket2") is False
        assert self.session_service.has_session("socket3") is True
        assert self.session_service.has_session("socket4") is False

    def test_cleanup_stale_sessions_no_stale(self):
        """Test cleanup when no sessions are stale"""
        # Create sessions
        self.session_service.create_session("socket1", "room1", "player1", "Name1")
        self.session_service.create_session("socket2", "room1", "player2", "Name2")
        
        # All sockets are active
        active_sockets = {"socket1", "socket2"}
        
        cleaned_count = self.session_service.cleanup_stale_sessions(active_sockets)
        
        # Should not clean up any sessions
        assert cleaned_count == 0
        assert self.session_service.get_sessions_count() == 2

    def test_cleanup_stale_sessions_handles_exception(self):
        """Test cleanup handles exceptions gracefully"""
        self.session_service.create_session("socket1", "room1", "player1", "Name1")
        
        # Mock an error in the session iteration
        with patch.object(self.session_service, '_player_sessions') as mock_sessions:
            mock_sessions.__iter__.side_effect = Exception("Iteration error")
            
            result = self.session_service.cleanup_stale_sessions({"active"})
            assert result == 0

    def test_validate_session_for_room_action_valid(self):
        """Test session validation for room actions - valid case"""
        socket_id = "socket123"
        room_id = "room456"
        
        # Create session
        self.session_service.create_session(socket_id, room_id, "player789", "TestPlayer")
        
        # Validate without expected room
        is_valid, session_info = self.session_service.validate_session_for_room_action(socket_id)
        assert is_valid is True
        assert session_info is not None
        assert session_info['room_id'] == room_id
        
        # Validate with correct expected room
        is_valid, session_info = self.session_service.validate_session_for_room_action(socket_id, room_id)
        assert is_valid is True
        assert session_info is not None

    def test_validate_session_for_room_action_no_session(self):
        """Test session validation when no session exists"""
        is_valid, session_info = self.session_service.validate_session_for_room_action("nonexistent")
        assert is_valid is False
        assert session_info is None

    def test_validate_session_for_room_action_room_mismatch(self):
        """Test session validation when room doesn't match"""
        socket_id = "socket123"
        room_id = "room456"
        expected_room = "different_room"
        
        # Create session
        self.session_service.create_session(socket_id, room_id, "player789", "TestPlayer")
        
        # Validate with wrong expected room
        is_valid, session_info = self.session_service.validate_session_for_room_action(socket_id, expected_room)
        assert is_valid is False
        assert session_info is not None  # Session exists but room mismatches
        assert session_info['room_id'] == room_id

    def test_get_debug_info_empty(self):
        """Test debug info when no sessions exist"""
        debug_info = self.session_service.get_debug_info()
        assert debug_info['total_sessions'] == 0
        assert debug_info['sessions_by_room'] == {}

    def test_get_debug_info_with_sessions(self):
        """Test debug info with multiple sessions"""
        # Create sessions in different rooms
        self.session_service.create_session("socket1", "room1", "player1", "Name1")
        self.session_service.create_session("socket2", "room1", "player2", "Name2")
        self.session_service.create_session("socket3", "room1", "player3", "Name3")
        self.session_service.create_session("socket4", "room2", "player4", "Name4")
        self.session_service.create_session("socket5", "room2", "player5", "Name5")
        self.session_service.create_session("socket6", "room3", "player6", "Name6")
        
        debug_info = self.session_service.get_debug_info()
        
        assert debug_info['total_sessions'] == 6
        assert debug_info['sessions_by_room']['room1'] == 3
        assert debug_info['sessions_by_room']['room2'] == 2
        assert debug_info['sessions_by_room']['room3'] == 1


class TestSessionServiceEdgeCases:
    """Test edge cases and error scenarios"""

    def setup_method(self):
        """Setup session service for edge case tests"""
        self.session_service = SessionService()

    def test_create_session_with_empty_strings(self):
        """Test creating session with empty string values"""
        socket_id = "socket123"
        
        # Create session with empty values
        self.session_service.create_session(socket_id, "", "", "")
        
        session = self.session_service.get_session(socket_id)
        assert session is not None
        assert session['room_id'] == ""
        assert session['player_id'] == ""
        assert session['player_name'] == ""

    def test_create_session_with_none_values(self):
        """Test creating session with None values (should convert to strings)"""
        socket_id = "socket123"
        
        # This should handle None gracefully or raise appropriate error
        self.session_service.create_session(socket_id, None, None, None)
        
        session = self.session_service.get_session(socket_id)
        assert session is not None
        # Values should be stored as provided (None)
        assert session['room_id'] is None
        assert session['player_id'] is None
        assert session['player_name'] is None

    def test_create_session_with_special_characters(self):
        """Test creating session with special characters"""
        socket_id = "socket!@#$%"
        room_id = "room_with_special_chars_123!@#"
        player_id = "player-id.with.dots"
        player_name = "Player Name With Spaces & Symbols!"
        
        self.session_service.create_session(socket_id, room_id, player_id, player_name)
        
        session = self.session_service.get_session(socket_id)
        assert session is not None
        assert session['room_id'] == room_id
        assert session['player_id'] == player_id
        assert session['player_name'] == player_name

    def test_cleanup_stale_sessions_with_empty_active_set(self):
        """Test cleanup when active sockets set is empty"""
        # Create sessions
        self.session_service.create_session("socket1", "room1", "player1", "Name1")
        self.session_service.create_session("socket2", "room1", "player2", "Name2")
        
        # Empty active set - all should be cleaned
        cleaned_count = self.session_service.cleanup_stale_sessions(set())
        
        assert cleaned_count == 2
        assert self.session_service.get_sessions_count() == 0

    def test_concurrent_operations_simulation(self):
        """Test simulating concurrent operations (basic thread safety check)"""
        # This is a basic test since we don't have explicit thread safety mechanisms
        # but we can test that operations don't interfere with each other
        
        socket_ids = [f"socket{i}" for i in range(100)]
        
        # Create many sessions
        for i, socket_id in enumerate(socket_ids):
            self.session_service.create_session(socket_id, f"room{i % 5}", f"player{i}", f"Name{i}")
        
        assert self.session_service.get_sessions_count() == 100
        
        # Remove some sessions
        for i in range(0, 50, 2):  # Remove even-indexed sessions
            self.session_service.remove_session(socket_ids[i])
        
        assert self.session_service.get_sessions_count() == 75
        
        # Verify remaining sessions are intact
        for i in range(1, 50, 2):  # Check odd-indexed sessions
            session = self.session_service.get_session(socket_ids[i])
            assert session is not None
            assert session['player_id'] == f"player{i}"

    def test_session_data_isolation(self):
        """Test that session data is properly isolated between different sockets"""
        # Create multiple sessions
        sessions_data = [
            ("socket1", "room1", "player1", "Name1"),
            ("socket2", "room2", "player2", "Name2"),
            ("socket3", "room1", "player3", "Name3"),
        ]
        
        for socket_id, room_id, player_id, player_name in sessions_data:
            self.session_service.create_session(socket_id, room_id, player_id, player_name)
        
        # Verify each session has correct, isolated data
        for socket_id, expected_room, expected_player, expected_name in sessions_data:
            session = self.session_service.get_session(socket_id)
            assert session['room_id'] == expected_room
            assert session['player_id'] == expected_player
            assert session['player_name'] == expected_name
        
        # Modify one session and verify others are unaffected
        modified_session = self.session_service.get_session("socket1")
        modified_session['room_id'] = "modified_room"  # Direct modification
        
        # Other sessions should be unaffected
        session2 = self.session_service.get_session("socket2")
        session3 = self.session_service.get_session("socket3")
        
        assert session2['room_id'] == "room2"
        assert session3['room_id'] == "room1"