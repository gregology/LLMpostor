"""
Room Lifecycle Service Unit Tests

Tests room creation, deletion, cleanup operations, resource management, and lifecycle event handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import threading
import time

from src.services.room_lifecycle_service import RoomLifecycleService


class TestRoomLifecycleServiceBasicOperations:
    """Test basic room lifecycle operations"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        # Mock game settings
        self.mock_game_settings = Mock()

        with patch('src.services.room_lifecycle_service.get_game_settings', return_value=self.mock_game_settings):
            self.service = RoomLifecycleService()

    def test_initialization(self):
        """Test service initialization"""
        assert self.service._rooms == {}
        assert hasattr(self.service._rooms_lock, 'acquire')  # Check it's a lock-like object
        assert hasattr(self.service._rooms_lock, 'release')  # Check it's a lock-like object
        assert self.service.game_settings == self.mock_game_settings

    def test_create_room_success(self):
        """Test successful room creation"""
        room_id = "test-room-123"

        with patch('src.services.room_lifecycle_service.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = mock_now

            room_data = self.service.create_room(room_id)

            # Verify room was created with correct structure
            assert room_data["room_id"] == room_id
            assert room_data["players"] == {}
            assert room_data["game_state"]["phase"] == "waiting"
            assert room_data["game_state"]["current_prompt"] is None
            assert room_data["game_state"]["responses"] == []
            assert room_data["game_state"]["guesses"] == {}
            assert room_data["game_state"]["round_number"] == 0
            assert room_data["game_state"]["phase_start_time"] is None
            assert room_data["game_state"]["phase_duration"] == 0
            assert room_data["created_at"] == mock_now
            assert room_data["last_activity"] == mock_now

            # Verify room is stored internally
            assert room_id in self.service._rooms
            assert self.service._rooms[room_id]["room_id"] == room_id

    def test_create_room_already_exists(self):
        """Test creating room that already exists raises ValueError"""
        room_id = "existing-room"

        # Create room first
        self.service.create_room(room_id)

        # Attempt to create same room again should raise ValueError
        with pytest.raises(ValueError, match=f"Room {room_id} already exists"):
            self.service.create_room(room_id)

    def test_delete_room_success(self):
        """Test successful room deletion"""
        room_id = "room-to-delete"

        # Create room first
        self.service.create_room(room_id)
        assert self.service.room_exists(room_id)

        # Delete room
        result = self.service.delete_room(room_id)

        assert result is True
        assert not self.service.room_exists(room_id)
        assert room_id not in self.service._rooms

    def test_delete_room_not_exists(self):
        """Test deleting non-existent room returns False"""
        room_id = "non-existent-room"

        result = self.service.delete_room(room_id)

        assert result is False

    def test_room_exists_true(self):
        """Test room_exists returns True for existing room"""
        room_id = "existing-room"

        self.service.create_room(room_id)

        assert self.service.room_exists(room_id) is True

    def test_room_exists_false(self):
        """Test room_exists returns False for non-existent room"""
        room_id = "non-existent-room"

        assert self.service.room_exists(room_id) is False

    def test_get_room_data_existing(self):
        """Test getting room data for existing room"""
        room_id = "test-room"

        created_room = self.service.create_room(room_id)
        retrieved_room = self.service.get_room_data(room_id)

        assert retrieved_room is not None
        assert retrieved_room["room_id"] == room_id
        assert retrieved_room == self.service._rooms[room_id]

    def test_get_room_data_non_existent(self):
        """Test getting room data for non-existent room returns None"""
        room_id = "non-existent-room"

        result = self.service.get_room_data(room_id)

        assert result is None

    def test_get_all_room_ids_empty(self):
        """Test getting all room IDs when no rooms exist"""
        result = self.service.get_all_room_ids()

        assert result == []

    def test_get_all_room_ids_multiple_rooms(self):
        """Test getting all room IDs with multiple rooms"""
        room_ids = ["room1", "room2", "room3"]

        for room_id in room_ids:
            self.service.create_room(room_id)

        result = self.service.get_all_room_ids()

        assert len(result) == 3
        assert set(result) == set(room_ids)


class TestRoomLifecycleServiceConcurrency:
    """Test concurrent operations and thread safety"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.services.room_lifecycle_service.get_game_settings'):
            self.service = RoomLifecycleService()

    def test_ensure_room_exists_new_room(self):
        """Test ensure_room_exists creates room if it doesn't exist"""
        room_id = "auto-created-room"

        assert not self.service.room_exists(room_id)

        self.service.ensure_room_exists(room_id)

        assert self.service.room_exists(room_id)
        room_data = self.service.get_room_data(room_id)
        assert room_data["room_id"] == room_id

    def test_ensure_room_exists_existing_room(self):
        """Test ensure_room_exists doesn't modify existing room"""
        room_id = "existing-room"

        # Create room first
        original_room = self.service.create_room(room_id)
        original_created_at = original_room["created_at"]

        # Ensure room exists (should not recreate)
        self.service.ensure_room_exists(room_id)

        # Verify room wasn't recreated
        current_room = self.service.get_room_data(room_id)
        assert current_room["created_at"] == original_created_at

    def test_concurrent_room_creation(self):
        """Test concurrent room creation with same ID"""
        room_id = "concurrent-room"
        results = []
        exceptions = []

        def create_room_worker():
            try:
                room_data = self.service.create_room(room_id)
                results.append(room_data)
            except Exception as e:
                exceptions.append(e)

        # Start multiple threads trying to create same room
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=create_room_worker)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Only one should succeed, others should get ValueError
        assert len(results) == 1
        assert len(exceptions) == 4
        assert all(isinstance(e, ValueError) for e in exceptions)
        assert self.service.room_exists(room_id)

    def test_concurrent_ensure_room_exists(self):
        """Test concurrent ensure_room_exists calls"""
        room_id = "concurrent-ensure-room"
        creation_count = 0

        def ensure_room_worker():
            nonlocal creation_count
            original_count = len(self.service.get_all_room_ids())
            self.service.ensure_room_exists(room_id)
            new_count = len(self.service.get_all_room_ids())
            if new_count > original_count:
                creation_count += 1

        # Start multiple threads trying to ensure same room exists
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=ensure_room_worker)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Room should exist and be created only once
        assert self.service.room_exists(room_id)
        assert len(self.service.get_all_room_ids()) == 1


class TestRoomLifecycleServiceCleanup:
    """Test room cleanup operations"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.services.room_lifecycle_service.get_game_settings'):
            self.service = RoomLifecycleService()

    def test_cleanup_inactive_rooms_no_rooms(self):
        """Test cleanup when no rooms exist"""
        result = self.service.cleanup_inactive_rooms()

        assert result == 0

    def test_cleanup_inactive_rooms_all_active(self):
        """Test cleanup when all rooms are active"""
        # Create rooms with current timestamps
        room_ids = ["room1", "room2", "room3"]
        for room_id in room_ids:
            self.service.create_room(room_id)

        result = self.service.cleanup_inactive_rooms(max_inactive_minutes=60)

        assert result == 0
        assert len(self.service.get_all_room_ids()) == 3

    def test_cleanup_inactive_rooms_some_inactive(self):
        """Test cleanup with mix of active and inactive rooms"""
        # Create rooms
        room_ids = ["active_room1", "inactive_room1", "active_room2", "inactive_room2"]
        for room_id in room_ids:
            self.service.create_room(room_id)

        # Manually set some rooms as inactive by modifying last_activity
        old_time = datetime.now() - timedelta(minutes=90)
        self.service._rooms["inactive_room1"]["last_activity"] = old_time
        self.service._rooms["inactive_room2"]["last_activity"] = old_time

        result = self.service.cleanup_inactive_rooms(max_inactive_minutes=60)

        assert result == 2
        remaining_rooms = self.service.get_all_room_ids()
        assert len(remaining_rooms) == 2
        assert "active_room1" in remaining_rooms
        assert "active_room2" in remaining_rooms
        assert "inactive_room1" not in remaining_rooms
        assert "inactive_room2" not in remaining_rooms

    def test_cleanup_inactive_rooms_custom_timeout(self):
        """Test cleanup with custom timeout"""
        # Create room
        room_id = "test-room"
        self.service.create_room(room_id)

        # Set room as inactive for 30 minutes
        old_time = datetime.now() - timedelta(minutes=30)
        self.service._rooms[room_id]["last_activity"] = old_time

        # Cleanup with 60-minute timeout (should not clean)
        result1 = self.service.cleanup_inactive_rooms(max_inactive_minutes=60)
        assert result1 == 0
        assert self.service.room_exists(room_id)

        # Cleanup with 15-minute timeout (should clean)
        result2 = self.service.cleanup_inactive_rooms(max_inactive_minutes=15)
        assert result2 == 1
        assert not self.service.room_exists(room_id)

    def test_cleanup_inactive_rooms_boundary_condition(self):
        """Test cleanup at exact timeout boundary"""
        room_id = "boundary-room"
        self.service.create_room(room_id)

        # Set room as inactive for exactly 60 minutes
        boundary_time = datetime.now() - timedelta(minutes=60)
        self.service._rooms[room_id]["last_activity"] = boundary_time

        result = self.service.cleanup_inactive_rooms(max_inactive_minutes=60)

        # Should be cleaned (< cutoff time)
        assert result == 1
        assert not self.service.room_exists(room_id)


class TestRoomLifecycleServiceResourceManagement:
    """Test resource management and memory cleanup"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.services.room_lifecycle_service.get_game_settings'):
            self.service = RoomLifecycleService()

    def test_room_data_isolation(self):
        """Test that create_room returns a copy but get_room_data returns reference"""
        room_id = "isolation-test"

        created_room = self.service.create_room(room_id)
        retrieved_room = self.service.get_room_data(room_id)

        # Modify created room data (should not affect internal)
        created_room["room_id"] = "modified"

        # Verify internal data is unchanged by create_room modifications
        internal_room = self.service._rooms[room_id]
        assert internal_room["room_id"] == room_id

        # Note: get_room_data returns reference, so modifications affect internal data
        # This is the actual behavior of the service
        retrieved_room["players"]["test"] = "player"
        assert internal_room["players"]["test"] == "player"  # Reference behavior

    def test_large_number_of_rooms(self):
        """Test handling large number of rooms"""
        room_count = 1000
        room_ids = [f"room-{i:04d}" for i in range(room_count)]

        # Create many rooms
        for room_id in room_ids:
            self.service.create_room(room_id)

        # Verify all rooms exist
        assert len(self.service.get_all_room_ids()) == room_count

        # Verify specific rooms
        assert self.service.room_exists("room-0000")
        assert self.service.room_exists("room-0500")
        assert self.service.room_exists("room-0999")

        # Clean up all rooms
        for room_id in room_ids:
            assert self.service.delete_room(room_id)

        assert len(self.service.get_all_room_ids()) == 0


class TestRoomLifecycleServiceEdgeCases:
    """Test edge cases and error conditions"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.services.room_lifecycle_service.get_game_settings'):
            self.service = RoomLifecycleService()

    def test_empty_room_id(self):
        """Test behavior with empty room ID"""
        room_id = ""

        # Should be able to create room with empty ID
        room_data = self.service.create_room(room_id)
        assert room_data["room_id"] == ""
        assert self.service.room_exists("")

    def test_none_room_id_operations(self):
        """Test operations with None room ID"""
        # These should handle None gracefully
        assert not self.service.room_exists(None)
        assert self.service.get_room_data(None) is None
        assert not self.service.delete_room(None)

    def test_special_character_room_ids(self):
        """Test room IDs with special characters"""
        special_room_ids = [
            "room-with-dashes",
            "room_with_underscores",
            "room.with.dots",
            "room@with#symbols",
            "room with spaces",
            "UPPERCASE_ROOM",
            "123456789"
        ]

        for room_id in special_room_ids:
            room_data = self.service.create_room(room_id)
            assert room_data["room_id"] == room_id
            assert self.service.room_exists(room_id)

        # Verify all rooms exist
        all_rooms = self.service.get_all_room_ids()
        assert len(all_rooms) == len(special_room_ids)
        assert set(all_rooms) == set(special_room_ids)

    def test_unicode_room_ids(self):
        """Test room IDs with Unicode characters"""
        unicode_room_ids = [
            "café-room",
            "房间-123",
            "комната-test",
            "🎮-gaming-room"
        ]

        for room_id in unicode_room_ids:
            room_data = self.service.create_room(room_id)
            assert room_data["room_id"] == room_id
            assert self.service.room_exists(room_id)

    def test_extremely_long_room_id(self):
        """Test very long room ID"""
        long_room_id = "a" * 1000

        room_data = self.service.create_room(long_room_id)
        assert room_data["room_id"] == long_room_id
        assert self.service.room_exists(long_room_id)


class TestRoomLifecycleServiceLogging:
    """Test logging behavior"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.services.room_lifecycle_service.get_game_settings'):
            self.service = RoomLifecycleService()

    @patch('src.services.room_lifecycle_service.logger')
    def test_create_room_logging(self, mock_logger):
        """Test that room creation is logged"""
        room_id = "logged-room"

        self.service.create_room(room_id)

        mock_logger.info.assert_called_with(f"Created room {room_id}")

    @patch('src.services.room_lifecycle_service.logger')
    def test_delete_room_logging(self, mock_logger):
        """Test that room deletion is logged"""
        room_id = "room-to-delete"

        self.service.create_room(room_id)
        mock_logger.reset_mock()  # Clear creation log

        self.service.delete_room(room_id)

        mock_logger.info.assert_called_with(f"Deleted room {room_id}")

    @patch('src.services.room_lifecycle_service.logger')
    def test_ensure_room_exists_logging(self, mock_logger):
        """Test that auto-creation is logged"""
        room_id = "auto-created-room"

        self.service.ensure_room_exists(room_id)

        mock_logger.info.assert_called_with(f"Auto-created room {room_id}")

    @patch('src.services.room_lifecycle_service.logger')
    def test_cleanup_rooms_logging(self, mock_logger):
        """Test that cleanup operations are logged"""
        room_id = "cleanup-room"
        self.service.create_room(room_id)

        # Make room inactive
        old_time = datetime.now() - timedelta(minutes=90)
        self.service._rooms[room_id]["last_activity"] = old_time

        mock_logger.reset_mock()  # Clear creation log

        self.service.cleanup_inactive_rooms(max_inactive_minutes=60)

        mock_logger.info.assert_called_with(f"Cleaned up inactive room {room_id}")