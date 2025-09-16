"""
Concurrency Control Service Unit Tests

Tests for the ConcurrencyControlService class covering per-room locking mechanisms,
request deduplication, thread safety scenarios, and race condition prevention.
"""

import pytest
import threading
import time
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.services.concurrency_control_service import ConcurrencyControlService
from tests.helpers.socket_mocks import create_mock_socketio


class TestConcurrencyControlServiceInitialization:
    """Test ConcurrencyControlService initialization and basic properties"""

    def test_initialization(self):
        """Test ConcurrencyControlService initialization"""
        service = ConcurrencyControlService()

        assert isinstance(service._room_locks, dict)
        assert isinstance(service._locks_lock, threading.Lock)
        assert isinstance(service._recent_requests, dict)
        assert hasattr(service, 'game_settings')
        assert hasattr(service, '_request_window')
        assert len(service._room_locks) == 0
        assert len(service._recent_requests) == 0

    def test_initialization_with_game_settings(self):
        """Test initialization with game settings configuration"""
        with patch('src.services.concurrency_control_service.get_game_settings') as mock_get_settings:
            mock_settings = create_mock_socketio()  # Use shared mock utility
            mock_settings.request_dedup_window = 0.5
            mock_get_settings.return_value = mock_settings

            service = ConcurrencyControlService()

            assert service.game_settings == mock_settings
            assert service._request_window == 0.5
            mock_get_settings.assert_called_once()

    def test_initialization_with_testing_environment(self):
        """Test initialization in testing environment with shorter window"""
        with patch('src.services.concurrency_control_service.get_game_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.request_dedup_window = 0.01  # Testing mode
            mock_get_settings.return_value = mock_settings

            service = ConcurrencyControlService()

            assert service._request_window == 0.01


class TestRoomLockingMechanisms:
    """Test per-room locking functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.service = ConcurrencyControlService()

    def test_get_room_lock_creation(self):
        """Test room lock creation"""
        room_id = "test_room_123"

        # First call should create the lock
        lock = self.service.get_room_lock(room_id)

        assert isinstance(lock, type(threading.RLock()))
        assert room_id in self.service._room_locks
        assert self.service._room_locks[room_id] is lock

    def test_get_room_lock_reuse(self):
        """Test that same lock is returned for same room"""
        room_id = "test_room_456"

        # Get lock twice
        lock1 = self.service.get_room_lock(room_id)
        lock2 = self.service.get_room_lock(room_id)

        assert lock1 is lock2
        assert len(self.service._room_locks) == 1

    def test_get_room_lock_different_rooms(self):
        """Test that different rooms get different locks"""
        room_id1 = "room_1"
        room_id2 = "room_2"

        lock1 = self.service.get_room_lock(room_id1)
        lock2 = self.service.get_room_lock(room_id2)

        assert lock1 is not lock2
        assert len(self.service._room_locks) == 2
        assert self.service._room_locks[room_id1] is lock1
        assert self.service._room_locks[room_id2] is lock2

    def test_cleanup_room_lock(self):
        """Test room lock cleanup"""
        room_id = "cleanup_room"

        # Create lock
        lock = self.service.get_room_lock(room_id)
        assert room_id in self.service._room_locks

        # Cleanup
        self.service.cleanup_room_lock(room_id)
        assert room_id not in self.service._room_locks

    def test_cleanup_nonexistent_room_lock(self):
        """Test cleanup of nonexistent room lock (should not error)"""
        # Should not raise exception
        self.service.cleanup_room_lock("nonexistent_room")
        assert len(self.service._room_locks) == 0

    def test_room_operation_context_manager(self):
        """Test room operation context manager"""
        room_id = "context_room"
        operation_executed = []

        with self.service.room_operation(room_id):
            operation_executed.append(True)
            # Verify lock was created
            assert room_id in self.service._room_locks

        assert operation_executed == [True]

    def test_room_operation_context_manager_exception_handling(self):
        """Test room operation context manager with exception"""
        room_id = "exception_room"

        with pytest.raises(ValueError):
            with self.service.room_operation(room_id):
                # Verify lock was created
                assert room_id in self.service._room_locks
                raise ValueError("Test exception")

        # Lock should still exist after exception
        assert room_id in self.service._room_locks

    def test_room_operation_lock_acquisition(self):
        """Test that room operation actually acquires the lock"""
        room_id = "lock_test_room"
        execution_order = []

        def operation_with_delay(op_id):
            with self.service.room_operation(room_id):
                execution_order.append(f"start_{op_id}")
                time.sleep(0.01)  # Small delay to test lock behavior
                execution_order.append(f"end_{op_id}")

        # Run two operations concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(operation_with_delay, "op1")
            future2 = executor.submit(operation_with_delay, "op2")

            # Wait for both to complete
            future1.result()
            future2.result()

        # Operations should not interleave due to locking
        assert len(execution_order) == 4
        # Should be either [start_op1, end_op1, start_op2, end_op2]
        # or [start_op2, end_op2, start_op1, end_op1]
        op1_start_idx = execution_order.index("start_op1")
        op1_end_idx = execution_order.index("end_op1")
        op2_start_idx = execution_order.index("start_op2")
        op2_end_idx = execution_order.index("end_op2")

        # Verify operations don't interleave
        assert abs(op1_start_idx - op1_end_idx) == 1
        assert abs(op2_start_idx - op2_end_idx) == 1


class TestRequestDeduplication:
    """Test request deduplication functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.service = ConcurrencyControlService()

    def test_check_duplicate_request_first_request(self):
        """Test first request is not considered duplicate"""
        request_key = "user_123_action_join"

        is_duplicate = self.service.check_duplicate_request(request_key)

        assert not is_duplicate
        assert request_key in self.service._recent_requests

    def test_check_duplicate_request_immediate_duplicate(self):
        """Test immediate duplicate request detection"""
        request_key = "user_456_action_submit"

        # First request
        is_duplicate1 = self.service.check_duplicate_request(request_key)
        # Immediate second request
        is_duplicate2 = self.service.check_duplicate_request(request_key)

        assert not is_duplicate1
        assert is_duplicate2

    def test_check_duplicate_request_after_window_expires(self):
        """Test request after time window expires is not duplicate"""
        request_key = "user_789_action_guess"

        # Mock shorter window for testing
        original_window = self.service._request_window
        self.service._request_window = 0.01  # 10ms window

        try:
            # First request
            is_duplicate1 = self.service.check_duplicate_request(request_key)

            # Wait for window to expire
            time.sleep(0.02)

            # Second request after window
            is_duplicate2 = self.service.check_duplicate_request(request_key)

            assert not is_duplicate1
            assert not is_duplicate2
        finally:
            self.service._request_window = original_window

    def test_check_duplicate_request_cleanup_expired(self):
        """Test cleanup of expired requests"""
        request_key1 = "expired_request"
        request_key2 = "recent_request"

        # Mock shorter window
        original_window = self.service._request_window
        self.service._request_window = 0.01

        try:
            # Add first request
            self.service.check_duplicate_request(request_key1)

            # Wait for first to expire
            time.sleep(0.02)

            # Add second request (should trigger cleanup)
            self.service.check_duplicate_request(request_key2)

            # First request should be cleaned up
            assert request_key1 not in self.service._recent_requests
            assert request_key2 in self.service._recent_requests
        finally:
            self.service._request_window = original_window

    def test_check_duplicate_request_multiple_users(self):
        """Test deduplication works independently for different users"""
        request_key1 = "user_1_action_submit"
        request_key2 = "user_2_action_submit"

        # Both users make same action
        is_duplicate1_1 = self.service.check_duplicate_request(request_key1)
        is_duplicate2_1 = self.service.check_duplicate_request(request_key2)

        # Same users repeat actions
        is_duplicate1_2 = self.service.check_duplicate_request(request_key1)
        is_duplicate2_2 = self.service.check_duplicate_request(request_key2)

        # First requests should not be duplicates
        assert not is_duplicate1_1
        assert not is_duplicate2_1

        # Second requests should be duplicates for each user
        assert is_duplicate1_2
        assert is_duplicate2_2

    def test_check_duplicate_request_different_actions_same_user(self):
        """Test different actions by same user are not duplicates"""
        user_id = "user_123"
        request_key1 = f"{user_id}_action_join"
        request_key2 = f"{user_id}_action_submit"

        is_duplicate1 = self.service.check_duplicate_request(request_key1)
        is_duplicate2 = self.service.check_duplicate_request(request_key2)

        assert not is_duplicate1
        assert not is_duplicate2
        assert len(self.service._recent_requests) == 2

    def test_request_deduplication_timing_precision(self):
        """Test timing precision in request deduplication"""
        request_key = "timing_test"

        # Make request
        start_time = time.time()
        self.service.check_duplicate_request(request_key)

        # Verify timestamp is recorded accurately
        recorded_time = self.service._recent_requests[request_key]
        assert abs(recorded_time - start_time) < 0.001  # Within 1ms


class TestThreadSafetyScenarios:
    """Test thread safety of the concurrency control service"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.service = ConcurrencyControlService()

    def test_concurrent_room_lock_creation(self):
        """Test concurrent creation of room locks is thread-safe"""
        room_id = "concurrent_room"
        locks_obtained = []

        def get_lock():
            lock = self.service.get_room_lock(room_id)
            locks_obtained.append(lock)

        # Create multiple threads trying to get same room lock
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_lock) for _ in range(10)]

            # Wait for all to complete
            for future in as_completed(futures):
                future.result()

        # All threads should get the same lock instance
        assert len(locks_obtained) == 10
        assert all(lock is locks_obtained[0] for lock in locks_obtained)
        assert len(self.service._room_locks) == 1

    def test_concurrent_room_lock_creation_different_rooms(self):
        """Test concurrent creation of locks for different rooms"""
        room_count = 20
        room_locks = {}

        def create_room_lock(room_index):
            room_id = f"room_{room_index}"
            lock = self.service.get_room_lock(room_id)
            room_locks[room_id] = lock

        # Create locks for different rooms concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_room_lock, i) for i in range(room_count)]

            for future in as_completed(futures):
                future.result()

        # Should have unique locks for each room
        assert len(room_locks) == room_count
        assert len(self.service._room_locks) == room_count

        # All locks should be different
        lock_objects = list(room_locks.values())
        assert len(set(id(lock) for lock in lock_objects)) == room_count

    def test_concurrent_room_cleanup(self):
        """Test concurrent room cleanup is thread-safe"""
        room_count = 10

        # Create locks for multiple rooms
        for i in range(room_count):
            self.service.get_room_lock(f"cleanup_room_{i}")

        assert len(self.service._room_locks) == room_count

        def cleanup_room(room_index):
            self.service.cleanup_room_lock(f"cleanup_room_{room_index}")

        # Cleanup all rooms concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(cleanup_room, i) for i in range(room_count)]

            for future in as_completed(futures):
                future.result()

        # All rooms should be cleaned up
        assert len(self.service._room_locks) == 0

    def test_concurrent_request_deduplication(self):
        """Test concurrent request deduplication is thread-safe"""
        request_key = "concurrent_request"
        duplicate_results = []

        def check_duplicate():
            result = self.service.check_duplicate_request(request_key)
            duplicate_results.append(result)

        # Multiple threads checking same request concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_duplicate) for _ in range(10)]

            for future in as_completed(futures):
                future.result()

        # Exactly one should be non-duplicate, others should be duplicates
        non_duplicate_count = duplicate_results.count(False)
        duplicate_count = duplicate_results.count(True)

        assert non_duplicate_count == 1
        assert duplicate_count == 9
        assert len(duplicate_results) == 10

    def test_concurrent_mixed_operations(self):
        """Test concurrent mixed operations (locks + deduplication)"""
        results = {}

        def mixed_operation(thread_id):
            room_id = f"room_{thread_id % 3}"  # Use 3 different rooms
            request_key = f"thread_{thread_id}_request"

            # Get room lock
            lock = self.service.get_room_lock(room_id)

            # Check for duplicate request
            is_duplicate = self.service.check_duplicate_request(request_key)

            # Perform operation with room lock
            with self.service.room_operation(room_id):
                time.sleep(0.001)  # Simulate work

            results[thread_id] = {
                'lock': lock,
                'is_duplicate': is_duplicate,
                'room_id': room_id
            }

        # Run multiple threads with mixed operations
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(mixed_operation, i) for i in range(15)]

            for future in as_completed(futures):
                future.result()

        # Verify results
        assert len(results) == 15

        # Group by room to verify lock consistency
        rooms = {}
        for thread_id, result in results.items():
            room_id = result['room_id']
            if room_id not in rooms:
                rooms[room_id] = []
            rooms[room_id].append(result)

        # Verify same room uses same lock
        for room_id, room_results in rooms.items():
            locks = [r['lock'] for r in room_results]
            assert all(lock is locks[0] for lock in locks)

        # Verify no duplicate requests (each thread has unique request key)
        duplicate_statuses = [r['is_duplicate'] for r in results.values()]
        assert all(not is_dup for is_dup in duplicate_statuses)


class TestRaceConditionPrevention:
    """Test race condition prevention scenarios"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.service = ConcurrencyControlService()

    def test_room_lock_creation_race_condition(self):
        """Test race condition in room lock creation"""
        room_id = "race_room"
        creation_count = 0
        lock_instances = []

        def create_and_track_lock():
            nonlocal creation_count

            # Simulate race condition by adding small delays
            time.sleep(0.001)

            # This should be atomic
            lock = self.service.get_room_lock(room_id)
            lock_instances.append(lock)

            # Check if lock was just created
            if room_id in self.service._room_locks:
                creation_count += 1

        # Multiple threads attempting to create same lock
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(create_and_track_lock) for _ in range(20)]

            for future in as_completed(futures):
                future.result()

        # Should have exactly one lock instance
        assert len(set(id(lock) for lock in lock_instances)) == 1
        assert len(self.service._room_locks) == 1

    def test_request_deduplication_race_condition(self):
        """Test race condition in request deduplication"""
        request_key = "race_request"
        first_request_indicators = []

        def check_request_atomically():
            # Small delay to increase chance of race condition
            time.sleep(0.001)

            # This should be atomic
            is_duplicate = self.service.check_duplicate_request(request_key)

            if not is_duplicate:
                first_request_indicators.append(True)
            else:
                first_request_indicators.append(False)

        # Multiple threads checking same request
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(check_request_atomically) for _ in range(15)]

            for future in as_completed(futures):
                future.result()

        # Exactly one thread should see non-duplicate
        first_request_count = first_request_indicators.count(True)
        assert first_request_count == 1
        assert len(first_request_indicators) == 15

    def test_cleanup_during_access_race_condition(self):
        """Test race condition between cleanup and access"""
        room_id = "cleanup_race_room"
        access_results = []
        cleanup_results = []

        # Create initial lock
        initial_lock = self.service.get_room_lock(room_id)

        def access_lock():
            try:
                lock = self.service.get_room_lock(room_id)
                access_results.append(lock)
            except Exception as e:
                access_results.append(e)

        def cleanup_lock():
            try:
                self.service.cleanup_room_lock(room_id)
                cleanup_results.append("success")
            except Exception as e:
                cleanup_results.append(e)

        # Concurrent access and cleanup
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Mix of access and cleanup operations
            futures = []
            for i in range(10):
                if i % 3 == 0:
                    futures.append(executor.submit(cleanup_lock))
                else:
                    futures.append(executor.submit(access_lock))

            for future in as_completed(futures):
                future.result()

        # No exceptions should occur
        for result in access_results:
            assert isinstance(result, type(threading.RLock()))

        for result in cleanup_results:
            assert result == "success"

    def test_room_operation_context_race_condition(self):
        """Test race condition in room operation context manager"""
        room_id = "context_race_room"
        operation_results = []

        def protected_operation(op_id):
            try:
                with self.service.room_operation(room_id):
                    # Simulate work that could race
                    current_time = time.time()
                    time.sleep(0.002)  # Small delay
                    operation_results.append((op_id, current_time))
            except Exception as e:
                operation_results.append((op_id, e))

        # Multiple concurrent operations on same room
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(protected_operation, i) for i in range(8)]

            for future in as_completed(futures):
                future.result()

        # All operations should succeed
        assert len(operation_results) == 8
        for op_id, result in operation_results:
            assert not isinstance(result, Exception)
            assert isinstance(result, float)  # timestamp

    def test_request_window_expiry_race_condition(self):
        """Test race condition in request window expiry cleanup"""
        base_key = "expiry_race"

        # Set short window for testing
        original_window = self.service._request_window
        self.service._request_window = 0.01

        try:
            def make_request_with_delay(request_id):
                request_key = f"{base_key}_{request_id}"

                # Make initial request
                self.service.check_duplicate_request(request_key)

                # Wait for potential expiry
                time.sleep(0.015)

                # Make another request (should trigger cleanup)
                return self.service.check_duplicate_request(f"{base_key}_new_{request_id}")

            # Multiple threads making requests with expiry
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_request_with_delay, i) for i in range(10)]

                results = []
                for future in as_completed(futures):
                    results.append(future.result())

            # All new requests should be non-duplicates
            assert all(not is_duplicate for is_duplicate in results)

        finally:
            self.service._request_window = original_window


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling scenarios"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.service = ConcurrencyControlService()

    def test_empty_room_id_handling(self):
        """Test handling of empty room ID"""
        empty_room_id = ""

        # Should not raise exception
        lock = self.service.get_room_lock(empty_room_id)
        assert isinstance(lock, type(threading.RLock()))
        assert empty_room_id in self.service._room_locks

    def test_none_room_id_handling(self):
        """Test handling of None room ID"""
        # Should handle None gracefully
        lock = self.service.get_room_lock(None)
        assert isinstance(lock, type(threading.RLock()))
        assert None in self.service._room_locks

    def test_special_characters_in_room_id(self):
        """Test room IDs with special characters"""
        special_room_ids = [
            "room-with-dashes",
            "room_with_underscores",
            "room.with.dots",
            "room with spaces",
            "room@with#symbols!",
            "room123with456numbers"
        ]

        locks = {}
        for room_id in special_room_ids:
            locks[room_id] = self.service.get_room_lock(room_id)

        # All should have unique locks
        assert len(locks) == len(special_room_ids)
        assert len(set(id(lock) for lock in locks.values())) == len(special_room_ids)

    def test_empty_request_key_deduplication(self):
        """Test deduplication with empty request key"""
        empty_key = ""

        is_duplicate1 = self.service.check_duplicate_request(empty_key)
        is_duplicate2 = self.service.check_duplicate_request(empty_key)

        assert not is_duplicate1
        assert is_duplicate2

    def test_none_request_key_deduplication(self):
        """Test deduplication with None request key"""
        # Should handle None gracefully
        is_duplicate1 = self.service.check_duplicate_request(None)
        is_duplicate2 = self.service.check_duplicate_request(None)

        assert not is_duplicate1
        assert is_duplicate2

    def test_very_long_request_key(self):
        """Test deduplication with very long request key"""
        long_key = "x" * 10000  # 10KB string

        is_duplicate1 = self.service.check_duplicate_request(long_key)
        is_duplicate2 = self.service.check_duplicate_request(long_key)

        assert not is_duplicate1
        assert is_duplicate2

    def test_memory_cleanup_with_many_expired_requests(self):
        """Test memory cleanup with large number of expired requests"""
        # Set very short window
        original_window = self.service._request_window
        self.service._request_window = 0.001

        try:
            # Add requests quickly (some may expire during this loop due to short window)
            for i in range(100):  # Reduced number to avoid automatic cleanup during loop
                self.service.check_duplicate_request(f"request_{i}")

            # At least some requests should be stored
            initial_count = len(self.service._recent_requests)
            assert initial_count > 0

            # Wait for all to expire
            time.sleep(0.01)

            # Trigger cleanup by making new request
            self.service.check_duplicate_request("cleanup_trigger")

            # Should have cleaned up expired requests, only cleanup_trigger should remain
            assert len(self.service._recent_requests) == 1
            assert "cleanup_trigger" in self.service._recent_requests

        finally:
            self.service._request_window = original_window

    def test_service_resilience_to_time_changes(self):
        """Test service resilience to system time changes"""
        request_key = "time_change_test"

        # Make initial request
        self.service.check_duplicate_request(request_key)

        # Mock time.time to return earlier time (simulate time going backwards)
        with patch('time.time', return_value=time.time() - 3600):  # 1 hour ago
            # Should handle gracefully without crashes
            is_duplicate = self.service.check_duplicate_request("new_request")
            assert not is_duplicate  # Should treat as new request