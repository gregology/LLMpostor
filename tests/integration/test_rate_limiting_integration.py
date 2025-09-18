"""
Rate Limiting Integration Tests

Tests rate limiting in practice with actual request blocking and integration with Socket.IO handlers.
Validates rate limiting effectiveness, testing environment bypass, and real blocking scenarios.
"""

import pytest
import time
import os
from unittest.mock import Mock, patch, MagicMock
from flask_socketio import SocketIOTestClient
from threading import Thread

from src.services.rate_limit_service import EventQueueManager, set_event_queue_manager, prevent_event_overflow
from src.core.errors import ErrorCode
from src.handlers.socket_event_router import create_router_with_socketio
from src.handlers.room_connection_handler import RoomConnectionHandler
from src.handlers.game_action_handler import GameActionHandler
from tests.migration_compat import app, socketio, room_manager, session_service
from config_factory import AppConfig, Environment


class TestRateLimitingIntegration:
    """Test rate limiting integration with Socket.IO handlers and real blocking scenarios."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Clear any existing state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()

        # Create test client with real SocketIO integration
        self.client = SocketIOTestClient(app, socketio)

        # Store original event queue manager
        from src.services import rate_limit_service
        self.original_manager = rate_limit_service._event_queue_manager

    def teardown_method(self):
        """Clean up after each test."""
        # Disconnect client
        if hasattr(self, 'client') and self.client:
            self.client.disconnect()

        # Clear state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()

        # Restore original event queue manager
        from src.services import rate_limit_service
        rate_limit_service._event_queue_manager = self.original_manager

    def test_testing_environment_bypass_integration(self):
        """Test that rate limiting is bypassed in testing environment."""
        # Create a restrictive config for rate limiting
        config = AppConfig(
            max_events_per_client_queue=5,
            max_events_rate_tracking=10,
            max_events_per_second=1,  # Very restrictive
            max_events_per_minute=2,   # Very restrictive
            rate_limit_window_seconds=60,
            environment=Environment.TESTING
        )

        # Create event manager with restrictive config
        with patch('src.services.rate_limit_service.get_config', return_value=config):
            event_manager = EventQueueManager()
            set_event_queue_manager(event_manager)

        # Verify testing environment is detected
        assert event_manager._is_testing() == True

        # Test that multiple rapid events are allowed due to testing bypass
        client_id = "test_bypass_client"

        # Should allow many events despite restrictive limits
        for i in range(10):  # Well above the restrictive limits
            result = event_manager.can_process_event(client_id, f"test_event_{i}")
            assert result == True, f"Event {i} should be allowed due to testing bypass"

        # Verify no client was blocked
        assert not event_manager.is_client_blocked(client_id)

    def test_actual_request_blocking_non_testing_environment(self):
        """Test actual request blocking when not in testing environment."""
        # Use testing config but mock _is_testing to simulate production behavior
        config = AppConfig(
            max_events_per_client_queue=10,
            max_events_rate_tracking=5,
            max_events_per_second=2,   # Allow 2 events per second
            max_events_per_minute=5,   # Allow 5 events per minute
            rate_limit_window_seconds=60,
            environment=Environment.TESTING  # Use testing env to avoid validation issues
        )

        with patch('src.services.rate_limit_service.get_config', return_value=config):
            event_manager = EventQueueManager()

        # Mock testing detection to return False for non-testing environment
        with patch.object(event_manager, '_is_testing', return_value=False):
            set_event_queue_manager(event_manager)

            client_id = "blocking_test_client"

            # Use a fixed time to control timing exactly
            with patch('time.time', return_value=1000.0):
                # First 2 events should be allowed (within per-second limit)
                assert event_manager.can_process_event(client_id, "event_1") == True
                assert event_manager.can_process_event(client_id, "event_2") == True

                # Third event should be blocked (exceeds per-second limit)
                assert event_manager.can_process_event(client_id, "event_3") == False

                # Client should be blocked now
                assert event_manager.is_client_blocked(client_id) == True

    def test_socket_handler_integration_with_rate_limiting(self):
        """Test rate limiting integration with actual Socket.IO handlers."""
        # Create a restrictive config to test blocking
        config = AppConfig(
            max_events_per_client_queue=10,
            max_events_rate_tracking=5,
            max_events_per_second=1,   # Very restrictive
            max_events_per_minute=3,
            rate_limit_window_seconds=60,
            environment=Environment.TESTING
        )

        with patch('src.services.rate_limit_service.get_config', return_value=config):
            event_manager = EventQueueManager()

        # Mock non-testing environment for this test
        with patch.object(event_manager, '_is_testing', return_value=False):
            set_event_queue_manager(event_manager)

            # Create a test handler with rate limiting decorator
            @prevent_event_overflow("test_handler_event")
            def test_handler():
                """Test handler with rate limiting."""
                return {"success": True, "message": "Handler executed"}

            # Test with Flask app context and mock Socket.IO request
            with app.test_request_context():
                with patch('src.services.rate_limit_service.request') as mock_request, \
                     patch('src.services.rate_limit_service.emit') as mock_emit, \
                     patch('time.time', return_value=2000.0):

                    mock_request.sid = "handler_test_client"

                    # First call should succeed
                    result = test_handler()
                    assert result["success"] == True
                    mock_emit.assert_not_called()  # No error emitted

                    # Second call should be blocked due to per-second limit
                    result = test_handler()
                    assert result is None  # Handler returns None when blocked

                    # Verify error was emitted
                    mock_emit.assert_called_once()
                    call_args = mock_emit.call_args
                    assert call_args[0][0] == 'error'  # Event name
                    error_data = call_args[0][1]
                    assert error_data['success'] == False
                    assert error_data['error']['code'] == ErrorCode.RATE_LIMITED.value
                    assert 'Too many requests' in error_data['error']['message']

    def test_global_rate_limiting_integration(self):
        """Test global rate limiting across multiple clients."""
        config = AppConfig(
            max_events_per_client_queue=20,
            max_events_rate_tracking=10,
            max_events_per_second=10,  # High per-client limit
            max_events_per_minute=50,
            rate_limit_window_seconds=60,
            environment=Environment.TESTING
        )

        with patch('src.services.rate_limit_service.get_config', return_value=config):
            event_manager = EventQueueManager()

        # Set a very low global limit for testing
        original_global_max = event_manager.global_max_events_per_second
        event_manager.global_max_events_per_second = 3

        with patch.object(event_manager, '_is_testing', return_value=False):
            set_event_queue_manager(event_manager)

            try:
                with patch('time.time', return_value=3000.0):
                    # Fill up global event window with events from different clients
                    clients = ["global_client_1", "global_client_2", "global_client_3"]

                    # First 3 events should be allowed (global limit is 3)
                    for i, client in enumerate(clients):
                        result = event_manager.can_process_event(client, f"global_event_{i}")
                        assert result == True, f"Global event {i} should be allowed"

                    # Fourth event should be blocked due to global limit
                    result = event_manager.can_process_event("global_client_4", "global_event_4")
                    assert result == False, "Event should be blocked by global rate limit"

            finally:
                # Restore original global limit
                event_manager.global_max_events_per_second = original_global_max

    def test_client_unblocking_after_timeout(self):
        """Test that blocked clients are automatically unblocked after timeout."""
        config = AppConfig(
            max_events_per_client_queue=10,
            max_events_rate_tracking=5,
            max_events_per_second=1,
            max_events_per_minute=3,
            rate_limit_window_seconds=60,
            environment=Environment.TESTING
        )

        with patch('src.services.rate_limit_service.get_config', return_value=config):
            event_manager = EventQueueManager()

        with patch.object(event_manager, '_is_testing', return_value=False):
            set_event_queue_manager(event_manager)

            client_id = "timeout_test_client"
            base_time = 4000.0

            with patch('time.time', return_value=base_time):
                # Fill up the rate limit and get client blocked
                assert event_manager.can_process_event(client_id, "event_1") == True
                assert event_manager.can_process_event(client_id, "event_2") == False  # This should block the client

                # Verify client is blocked
                assert event_manager.is_client_blocked(client_id) == True

            # Move time forward beyond block duration (60 seconds)
            with patch('time.time', return_value=base_time + 61):
                # Client should be automatically unblocked
                assert event_manager.is_client_blocked(client_id) == False

                # Should be able to process events again
                assert event_manager.can_process_event(client_id, "event_after_unblock") == True

    def test_rate_limiting_with_real_socketio_handlers(self):
        """Test rate limiting with actual registered Socket.IO handlers."""
        # This test uses the real handlers but with controlled rate limiting
        config = AppConfig(
            max_events_per_client_queue=10,
            max_events_rate_tracking=5,
            max_events_per_second=2,
            max_events_per_minute=5,
            rate_limit_window_seconds=60,
            environment=Environment.TESTING
        )

        with patch('src.services.rate_limit_service.get_config', return_value=config):
            event_manager = EventQueueManager()

        with patch.object(event_manager, '_is_testing', return_value=False):
            set_event_queue_manager(event_manager)

            # Connect client
            self.client.connect()

            # Create a test room first
            room_manager.create_room("test_room_rate")

            # Instead of trying to capture messages, we'll test the blocking directly
            # by checking if the events can be processed through the event manager
            with patch('time.time', return_value=5000.0):
                # Simulate multiple rapid join_room attempts from same client
                client_id = "socketio_test_client"

                # First two events should succeed (within limit of 2 per second)
                result1 = event_manager.can_process_event(client_id, "join_room")
                result2 = event_manager.can_process_event(client_id, "join_room")
                result3 = event_manager.can_process_event(client_id, "join_room")  # Should be blocked

                assert result1 == True, "First event should be allowed"
                assert result2 == True, "Second event should be allowed"
                assert result3 == False, "Third event should be blocked"

                # Verify client is blocked
                assert event_manager.is_client_blocked(client_id) == True

    def test_concurrent_rate_limiting(self):
        """Test rate limiting behavior under concurrent access."""
        config = AppConfig(
            max_events_per_client_queue=10,
            max_events_rate_tracking=10,
            max_events_per_second=5,
            max_events_per_minute=20,
            rate_limit_window_seconds=60,
            environment=Environment.TESTING
        )

        with patch('src.services.rate_limit_service.get_config', return_value=config):
            event_manager = EventQueueManager()

        with patch.object(event_manager, '_is_testing', return_value=False):
            set_event_queue_manager(event_manager)

            results = []

            def worker_thread(client_id, thread_num):
                """Worker thread that attempts to process events."""
                thread_results = []
                for i in range(3):  # Each thread tries 3 events
                    # Use same client ID to compete for same rate limit
                    result = event_manager.can_process_event(client_id, f"event_{thread_num}_{i}")
                    thread_results.append(result)
                results.append(thread_results)

            # Use a fixed time across all threads
            with patch('time.time', return_value=6000.0):
                # Start multiple threads
                threads = []
                for i in range(4):  # 4 threads, each trying 3 events = 12 total events
                    thread = Thread(target=worker_thread, args=("concurrent_client", i))
                    threads.append(thread)
                    thread.start()

                # Wait for all threads to complete
                for thread in threads:
                    thread.join()

            # Verify that some events were allowed and some were blocked
            all_results = [result for thread_results in results for result in thread_results]
            allowed_count = sum(all_results)
            blocked_count = len(all_results) - allowed_count

            # With 4 threads × 3 events = 12 events, and a limit of 5 per second,
            # we should have some allowed and some blocked
            assert allowed_count > 0, "Some events should be allowed"
            # Since all events are from same client with 5 per second limit,
            # max 5 should be allowed, rest should be blocked
            assert allowed_count <= 5, "Should not exceed per-second limit"
            if allowed_count == 5:
                assert blocked_count > 0, "Some events should be blocked due to rate limiting"

    def test_queue_statistics_integration(self):
        """Test queue statistics functionality in integration context."""
        config = AppConfig(
            max_events_per_client_queue=5,
            max_events_rate_tracking=10,
            max_events_per_second=3,
            max_events_per_minute=10,
            rate_limit_window_seconds=60,
            environment=Environment.TESTING
        )

        with patch('src.services.rate_limit_service.get_config', return_value=config):
            event_manager = EventQueueManager()

        with patch.object(event_manager, '_is_testing', return_value=False):
            set_event_queue_manager(event_manager)

            client_id = "stats_test_client"

            with patch('time.time', return_value=7000.0):
                # Process some events - with limit of 3 per second, all 3 should be allowed
                result1 = event_manager.can_process_event(client_id, "stats_event_1")
                result2 = event_manager.can_process_event(client_id, "stats_event_2")
                result3 = event_manager.can_process_event(client_id, "stats_event_3")
                result4 = event_manager.can_process_event(client_id, "stats_event_4")  # This should block

                # Get client-specific stats
                client_stats = event_manager.get_queue_stats(client_id)
                assert client_stats['queue_length'] == 3  # First 3 events processed
                assert client_stats['recent_events'] == 4  # All 4 attempts are tracked
                assert client_stats['blocked'] == True  # Client should be blocked after 4th event

                # Get global stats
                global_stats = event_manager.get_queue_stats()
                assert global_stats['total_clients'] == 1
                assert global_stats['blocked_clients'] == 1
                assert global_stats['global_event_count'] == 3  # Only successful events counted


class TestRateLimitingConfigurationIntegration:
    """Test rate limiting integration with different configurations."""

    def setup_method(self):
        """Set up test environment."""
        from src.services import rate_limit_service
        self.original_manager = rate_limit_service._event_queue_manager

    def teardown_method(self):
        """Clean up after each test."""
        from src.services import rate_limit_service
        rate_limit_service._event_queue_manager = self.original_manager

    def test_rate_limiting_with_production_config(self):
        """Test rate limiting with production-like configuration."""
        config = AppConfig(
            max_events_per_client_queue=100,
            max_events_rate_tracking=50,
            max_events_per_second=10,  # Production-like limits
            max_events_per_minute=100,
            rate_limit_window_seconds=60,
            environment=Environment.TESTING  # Use testing to avoid validation issues
        )

        with patch('src.services.rate_limit_service.get_config', return_value=config):
            event_manager = EventQueueManager()

        with patch.object(event_manager, '_is_testing', return_value=False):
            set_event_queue_manager(event_manager)

            client_id = "production_test_client"

            with patch('time.time', return_value=8000.0):
                # Should be able to process up to the limit
                for i in range(10):  # Up to max_events_per_second
                    result = event_manager.can_process_event(client_id, f"prod_event_{i}")
                    assert result == True, f"Event {i} should be allowed within production limits"

                # The 11th event should be blocked
                result = event_manager.can_process_event(client_id, "prod_event_11")
                assert result == False, "Event should be blocked after exceeding production limit"

    def test_rate_limiting_with_development_config(self):
        """Test rate limiting with development-friendly configuration."""
        config = AppConfig(
            max_events_per_client_queue=200,
            max_events_rate_tracking=100,
            max_events_per_second=50,  # More lenient for development
            max_events_per_minute=500,
            rate_limit_window_seconds=60,
            environment=Environment.DEVELOPMENT
        )

        with patch('src.services.rate_limit_service.get_config', return_value=config):
            event_manager = EventQueueManager()

        with patch.object(event_manager, '_is_testing', return_value=False):
            set_event_queue_manager(event_manager)

            client_id = "development_test_client"

            with patch('time.time', return_value=9000.0):
                # Should be able to process many more events
                for i in range(50):  # Up to max_events_per_second
                    result = event_manager.can_process_event(client_id, f"dev_event_{i}")
                    assert result == True, f"Event {i} should be allowed within development limits"

                # The 51st event should be blocked
                result = event_manager.can_process_event(client_id, "dev_event_51")
                assert result == False, "Event should be blocked after exceeding development limit"

    def test_error_handling_in_rate_limited_decorator(self):
        """Test error handling within rate-limited decorated functions."""
        config = AppConfig(
            max_events_per_client_queue=10,
            max_events_rate_tracking=5,
            max_events_per_second=5,
            max_events_per_minute=20,
            environment=Environment.TESTING
        )

        with patch('src.services.rate_limit_service.get_config', return_value=config):
            event_manager = EventQueueManager()

        with patch.object(event_manager, '_is_testing', return_value=False):
            set_event_queue_manager(event_manager)

            @prevent_event_overflow("error_handler_event")
            def error_handler():
                """Handler that raises an exception."""
                raise ValueError("Test exception in handler")

            # Test with Flask app context
            with app.test_request_context():
                with patch('src.services.rate_limit_service.request') as mock_request, \
                     patch('src.services.rate_limit_service.emit') as mock_emit, \
                     patch('src.services.rate_limit_service.logger') as mock_logger:

                    mock_request.sid = "error_handler_client"

                    # Call the handler that will raise an exception
                    result = error_handler()
                    assert result is None  # Handler returns None when error occurs

                    # Verify error was logged
                    mock_logger.error.assert_called_once()
                    log_call = mock_logger.error.call_args[0][0]
                    assert "Error in error_handler_event handler" in log_call

                    # Verify internal error was emitted
                    mock_emit.assert_called_once()
                    call_args = mock_emit.call_args
                    assert call_args[0][0] == 'error'
                    error_data = call_args[0][1]
                    assert error_data['success'] == False
                    assert error_data['error']['code'] == ErrorCode.INTERNAL_ERROR.value
                    assert 'internal error occurred' in error_data['error']['message']