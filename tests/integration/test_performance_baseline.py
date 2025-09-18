"""
Performance Baseline Tests

Tests to establish and validate basic performance characteristics:
- Memory usage under load
- Response time benchmarks
- Resource cleanup validation
"""

import time
import threading
import resource
import os
import gc
from unittest.mock import patch, MagicMock
import pytest
from flask_socketio import SocketIOTestClient

from tests.migration_compat import app, socketio, room_manager, auto_flow_service, session_service
from tests.helpers.room_helpers import join_room_helper, leave_room_helper


class TestPerformanceBaseline:
    """Performance baseline validation tests."""

    @pytest.fixture(autouse=True)
    def setup_and_cleanup(self):
        """Setup and cleanup for each test."""
        # Clear any existing state like other working tests
        room_manager._rooms.clear()
        session_service._player_sessions.clear()

        # Stop auto game flow to prevent interference
        auto_flow_service.stop()

        # Force garbage collection for consistent memory measurements
        gc.collect()

        yield

        # Cleanup
        room_manager._rooms.clear()
        session_service._player_sessions.clear()
        auto_flow_service.stop()
        gc.collect()

    @pytest.fixture
    def socketio_client(self):
        """Create SocketIO test client."""
        return SocketIOTestClient(app, socketio)

    def get_memory_usage_mb(self):
        """Get current memory usage in MB using resource module."""
        # Use resource.getrusage for memory measurement
        # Note: On some systems this may not be as accurate as psutil
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # maxrss is in kilobytes on Linux, bytes on macOS
        import sys
        if sys.platform == 'darwin':  # macOS
            return usage.ru_maxrss / 1024 / 1024  # Convert bytes to MB
        else:  # Linux
            return usage.ru_maxrss / 1024  # Convert KB to MB

    def test_memory_usage_single_room_operations(self, socketio_client):
        """Test memory usage with basic room operations."""
        # Measure initial memory
        initial_memory = self.get_memory_usage_mb()

        # Perform basic operations
        socketio_client.emit('join_room', {'code': 'TEST1', 'username': 'player1'})
        socketio_client.emit('leave_room', {'code': 'TEST1'})

        # Allow some processing time
        time.sleep(0.1)

        # Measure final memory
        final_memory = self.get_memory_usage_mb()

        # Memory should not increase significantly for basic operations
        memory_increase = final_memory - initial_memory
        assert memory_increase < 5.0, f"Memory increased by {memory_increase}MB for basic operations"

    def test_memory_usage_multiple_rooms(self, socketio_client):
        """Test memory usage when creating multiple rooms."""
        initial_memory = self.get_memory_usage_mb()

        # Create multiple rooms
        room_codes = []
        for i in range(10):
            code = f"ROOM{i:02d}"
            room_codes.append(code)
            socketio_client.emit('join_room', {'code': code, 'username': f'player{i}'})

        # Measure memory after room creation
        after_creation_memory = self.get_memory_usage_mb()

        # Clean up rooms
        for code in room_codes:
            socketio_client.emit('leave_room', {'code': code})

        # Allow cleanup time
        time.sleep(0.2)
        gc.collect()

        # Measure final memory
        final_memory = self.get_memory_usage_mb()

        # Memory should not grow excessively
        creation_increase = after_creation_memory - initial_memory
        assert creation_increase < 20.0, f"Memory increased by {creation_increase}MB for 10 rooms"

        # Memory should be cleaned up reasonably well (if there was any increase)
        if creation_increase > 0:
            cleanup_ratio = (after_creation_memory - final_memory) / creation_increase
            assert cleanup_ratio > 0.3, f"Only {cleanup_ratio*100:.1f}% of memory was cleaned up"

    def test_response_time_room_join(self, socketio_client):
        """Test response time for room join operations."""
        response_times = []

        # Test multiple room joins
        for i in range(5):
            start_time = time.time()

            response = socketio_client.emit('join_room', {
                'code': f'PERF{i}',
                'username': f'player{i}'
            })

            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # Convert to milliseconds
            response_times.append(response_time)

            # Clean up
            socketio_client.emit('leave_room', {'code': f'PERF{i}'})

        # Calculate statistics
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)

        # Assert reasonable response times (adjust thresholds as needed)
        assert avg_response_time < 100, f"Average response time {avg_response_time:.2f}ms too high"
        assert max_response_time < 200, f"Max response time {max_response_time:.2f}ms too high"

    def test_response_time_game_actions(self, socketio_client):
        """Test response time for game action operations."""
        # Setup a room and game
        socketio_client.emit('join_room', {'code': 'PERFGAME', 'username': 'player1'})
        socketio_client.emit('start_game', {'code': 'PERFGAME'})

        # Test response submission
        start_time = time.time()

        socketio_client.emit('submit_response', {
            'code': 'PERFGAME',
            'response': 'test response'
        })

        end_time = time.time()
        response_time = (end_time - start_time) * 1000

        # Clean up
        socketio_client.emit('leave_room', {'code': 'PERFGAME'})

        # Assert reasonable response time
        assert response_time < 150, f"Game action response time {response_time:.2f}ms too high"

    def test_concurrent_operations_performance(self):
        """Test performance under concurrent operations."""
        initial_memory = self.get_memory_usage_mb()

        # Create multiple clients
        clients = []
        for i in range(5):
            client = SocketIOTestClient(app, socketio)
            clients.append(client)

        # Perform concurrent operations
        def client_operations(client, client_id):
            room_code = f'CONC{client_id}'
            client.emit('join_room', {'code': room_code, 'username': f'player{client_id}'})
            time.sleep(0.1)
            client.emit('leave_room', {'code': room_code})

        # Start concurrent operations
        threads = []
        start_time = time.time()

        for i, client in enumerate(clients):
            thread = threading.Thread(target=client_operations, args=(client, i))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        end_time = time.time()
        total_time = end_time - start_time

        # Clean up clients
        for client in clients:
            client.disconnect()

        # Allow cleanup
        time.sleep(0.2)
        gc.collect()

        final_memory = self.get_memory_usage_mb()
        memory_increase = final_memory - initial_memory

        # Assert reasonable performance
        assert total_time < 2.0, f"Concurrent operations took {total_time:.2f}s"
        assert memory_increase < 15.0, f"Memory increased by {memory_increase}MB for concurrent ops"

    def test_resource_cleanup_after_disconnect(self, socketio_client):
        """Test that resources are properly cleaned up after disconnect."""
        initial_memory = self.get_memory_usage_mb()

        # Create room and join using helper
        response = join_room_helper(socketio_client, 'cleanup1', 'player1')

        # Verify room exists
        assert room_manager.room_exists('cleanup1'), "Room should exist after joining"

        # Simulate disconnect by leaving room
        leave_room_helper(socketio_client)

        # Allow cleanup time
        time.sleep(0.1)

        # Force garbage collection
        gc.collect()

        final_memory = self.get_memory_usage_mb()
        memory_increase = final_memory - initial_memory

        # Memory should not increase significantly after cleanup
        assert memory_increase < 2.0, f"Memory increased by {memory_increase}MB after cleanup"

    def test_room_cleanup_on_empty(self, socketio_client):
        """Test that empty rooms are cleaned up properly."""
        initial_room_count = len(room_manager.get_all_rooms())

        # Create and immediately leave rooms
        for i in range(3):
            room_code = f'EMPTY{i}'
            socketio_client.emit('join_room', {'code': room_code, 'username': f'player{i}'})
            socketio_client.emit('leave_room', {'code': room_code})

        # Allow cleanup time
        time.sleep(0.1)

        # Check that rooms were cleaned up
        final_room_count = len(room_manager.get_all_rooms())
        assert final_room_count == initial_room_count, "Empty rooms were not cleaned up properly"

    def test_background_service_resource_usage(self, socketio_client):
        """Test resource usage of background services."""
        initial_memory = self.get_memory_usage_mb()

        # Service should already be running (auto-started)
        # Create room with auto game flow
        socketio_client.emit('join_room', {'code': 'BGTEST', 'username': 'player1'})
        socketio_client.emit('start_game', {'code': 'BGTEST'})

        # Allow service to run briefly
        time.sleep(0.2)

        # Clean up room
        socketio_client.emit('leave_room', {'code': 'BGTEST'})

        # Allow cleanup
        time.sleep(0.1)
        gc.collect()

        final_memory = self.get_memory_usage_mb()
        memory_increase = final_memory - initial_memory

        # Background service should not consume excessive memory
        assert memory_increase < 5.0, f"Background service used {memory_increase}MB"

    def test_large_response_handling_performance(self, socketio_client):
        """Test performance with large response data."""
        # Create room
        socketio_client.emit('join_room', {'code': 'LARGETEST', 'username': 'player1'})
        socketio_client.emit('start_game', {'code': 'LARGETEST'})

        # Submit large response
        large_response = 'A' * 1000  # 1KB response

        start_time = time.time()
        socketio_client.emit('submit_response', {
            'code': 'LARGETEST',
            'response': large_response
        })
        end_time = time.time()

        response_time = (end_time - start_time) * 1000

        # Clean up
        socketio_client.emit('leave_room', {'code': 'LARGETEST'})

        # Should handle large responses efficiently
        assert response_time < 300, f"Large response took {response_time:.2f}ms"

    def test_memory_stability_over_time(self, socketio_client):
        """Test that memory usage remains stable over repeated operations."""
        memory_samples = []

        # Perform repeated operations and sample memory
        for i in range(10):
            # Sample memory before operation
            memory_before = self.get_memory_usage_mb()

            # Perform operation
            room_code = f'STABLE{i}'
            socketio_client.emit('join_room', {'code': room_code, 'username': f'player{i}'})
            socketio_client.emit('leave_room', {'code': room_code})

            # Allow cleanup
            time.sleep(0.05)

            # Sample memory after operation
            memory_after = self.get_memory_usage_mb()
            memory_samples.append(memory_after - memory_before)

        # Force final cleanup
        gc.collect()

        # Check for memory stability (no significant growth over time)
        avg_increase = sum(memory_samples) / len(memory_samples)
        max_increase = max(memory_samples)

        assert avg_increase < 1.0, f"Average memory increase per operation: {avg_increase:.2f}MB"
        assert max_increase < 3.0, f"Max memory increase per operation: {max_increase:.2f}MB"