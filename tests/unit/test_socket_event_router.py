"""
Socket Event Router Unit Tests

Tests for the SocketEventRouter class and its core routing functionality,
including event routing, middleware execution, error handling, and handler management.
"""

import pytest
import logging
from unittest.mock import Mock, patch, MagicMock, call
from flask import Flask

from src.handlers.socket_event_router import (
    SocketEventRouter,
    EventRouteNotFoundError,
    create_router_with_socketio,
    get_router,
    setup_router,
    request_logging_middleware,
    session_validation_middleware
)


class TestSocketEventRouter:
    """Test SocketEventRouter core functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.router = SocketEventRouter()

    def test_initialization(self):
        """Test SocketEventRouter initialization"""
        assert isinstance(self.router._routes, dict)
        assert isinstance(self.router._middleware, list)
        assert isinstance(self.router._before_request_handlers, list)
        assert isinstance(self.router._after_request_handlers, list)
        assert len(self.router._routes) == 0
        assert len(self.router._middleware) == 0
        assert len(self.router._before_request_handlers) == 0
        assert len(self.router._after_request_handlers) == 0

    def test_register_route(self):
        """Test route registration"""
        def test_handler(data):
            return "test_response"

        # Test registration
        self.router.register_route("test_event", test_handler)

        assert "test_event" in self.router._routes
        assert self.router._routes["test_event"] == test_handler
        assert self.router.has_route("test_event")
        assert not self.router.has_route("nonexistent_event")

    def test_route_decorator(self):
        """Test route decorator functionality"""
        @self.router.route("decorated_event")
        def decorated_handler(data):
            return "decorated_response"

        assert self.router.has_route("decorated_event")
        assert self.router._routes["decorated_event"] == decorated_handler

    def test_add_middleware(self):
        """Test middleware addition"""
        def test_middleware(event_name, data):
            return data

        self.router.add_middleware(test_middleware)

        assert test_middleware in self.router._middleware
        assert len(self.router._middleware) == 1

    def test_middleware_decorator(self):
        """Test middleware decorator"""
        @self.router.middleware()
        def decorated_middleware(event_name, data):
            return data

        assert decorated_middleware in self.router._middleware
        assert len(self.router._middleware) == 1

    def test_add_before_request_handler(self):
        """Test before request handler addition"""
        def before_handler(event_name, data):
            pass

        self.router.add_before_request(before_handler)

        assert before_handler in self.router._before_request_handlers
        assert len(self.router._before_request_handlers) == 1

    def test_add_after_request_handler(self):
        """Test after request handler addition"""
        def after_handler(event_name, data, result):
            pass

        self.router.add_after_request(after_handler)

        assert after_handler in self.router._after_request_handlers
        assert len(self.router._after_request_handlers) == 1

    def test_get_registered_events(self):
        """Test getting registered events list"""
        def handler1(data):
            pass
        def handler2(data):
            pass

        self.router.register_route("event1", handler1)
        self.router.register_route("event2", handler2)

        events = self.router.get_registered_events()
        assert set(events) == {"event1", "event2"}
        assert len(events) == 2


class TestSocketEventRouterHandling:
    """Test event handling functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.router = SocketEventRouter()
        self.app = Flask(__name__)

    def test_handle_event_not_found(self):
        """Test handling of unregistered event"""
        with pytest.raises(EventRouteNotFoundError) as exc_info:
            self.router.handle_event("nonexistent_event")

        assert "No handler registered for event: nonexistent_event" in str(exc_info.value)

    def test_handle_event_basic(self):
        """Test basic event handling"""
        def test_handler(data):
            return f"handled: {data}"

        self.router.register_route("test_event", test_handler)

        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request:
                mock_request.sid = "test_socket_123"
                result = self.router.handle_event("test_event", "test_data")

        assert result == "handled: test_data"

    def test_handle_event_no_data(self):
        """Test handling event with no data"""
        def test_handler(data):
            return f"no_data: {data}"

        self.router.register_route("no_data_event", test_handler)

        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request:
                mock_request.sid = "test_socket_456"
                result = self.router.handle_event("no_data_event")

        assert result == "no_data: None"

    def test_handle_event_with_middleware(self):
        """Test event handling with middleware execution"""
        call_order = []

        def middleware1(event_name, data):
            call_order.append("middleware1")
            return f"modified_by_1: {data}"

        def middleware2(event_name, data):
            call_order.append("middleware2")
            return f"modified_by_2: {data}"

        def test_handler(data):
            call_order.append("handler")
            return f"handled: {data}"

        self.router.add_middleware(middleware1)
        self.router.add_middleware(middleware2)
        self.router.register_route("middleware_event", test_handler)

        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request:
                mock_request.sid = "test_socket_789"
                result = self.router.handle_event("middleware_event", "original")

        # Check execution order
        assert call_order == ["middleware1", "middleware2", "handler"]
        # Check data transformation
        assert result == "handled: modified_by_2: modified_by_1: original"

    def test_middleware_no_return_value(self):
        """Test middleware that doesn't return data (data should be unchanged)"""
        def middleware_no_return(event_name, data):
            pass  # Returns None

        def test_handler(data):
            return f"handled: {data}"

        self.router.add_middleware(middleware_no_return)
        self.router.register_route("no_return_event", test_handler)

        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request:
                mock_request.sid = "test_socket_no_return"
                result = self.router.handle_event("no_return_event", "original_data")

        assert result == "handled: original_data"

    def test_handle_event_with_before_after_handlers(self):
        """Test before and after request handler execution"""
        call_order = []
        handler_data = []

        def before_handler1(event_name, data):
            call_order.append("before1")
            handler_data.append(("before1", event_name, data))

        def before_handler2(event_name, data):
            call_order.append("before2")
            handler_data.append(("before2", event_name, data))

        def after_handler1(event_name, data, result):
            call_order.append("after1")
            handler_data.append(("after1", event_name, data, result))

        def after_handler2(event_name, data, result):
            call_order.append("after2")
            handler_data.append(("after2", event_name, data, result))

        def main_handler(data):
            call_order.append("main")
            return f"processed: {data}"

        self.router.add_before_request(before_handler1)
        self.router.add_before_request(before_handler2)
        self.router.add_after_request(after_handler1)
        self.router.add_after_request(after_handler2)
        self.router.register_route("full_cycle_event", main_handler)

        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request:
                mock_request.sid = "test_socket_full"
                result = self.router.handle_event("full_cycle_event", "test_data")

        # Check execution order
        assert call_order == ["before1", "before2", "main", "after1", "after2"]

        # Check handler data
        assert handler_data[0] == ("before1", "full_cycle_event", "test_data")
        assert handler_data[1] == ("before2", "full_cycle_event", "test_data")
        assert handler_data[2] == ("after1", "full_cycle_event", "test_data", "processed: test_data")
        assert handler_data[3] == ("after2", "full_cycle_event", "test_data", "processed: test_data")

        assert result == "processed: test_data"


class TestSocketEventRouterErrorHandling:
    """Test error handling in event routing"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.router = SocketEventRouter()
        self.app = Flask(__name__)

    def test_handler_exception_propagation(self):
        """Test that handler exceptions are propagated"""
        def failing_handler(data):
            raise ValueError("Handler failed")

        self.router.register_route("failing_event", failing_handler)

        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request:
                mock_request.sid = "test_socket_error"
                with pytest.raises(ValueError) as exc_info:
                    self.router.handle_event("failing_event", "test_data")

        assert "Handler failed" in str(exc_info.value)

    def test_middleware_exception_propagation(self):
        """Test that middleware exceptions are propagated"""
        def failing_middleware(event_name, data):
            raise RuntimeError("Middleware failed")

        def normal_handler(data):
            return "should not reach"

        self.router.add_middleware(failing_middleware)
        self.router.register_route("middleware_fail_event", normal_handler)

        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request:
                mock_request.sid = "test_socket_middleware_error"
                with pytest.raises(RuntimeError) as exc_info:
                    self.router.handle_event("middleware_fail_event", "test_data")

        assert "Middleware failed" in str(exc_info.value)

    def test_before_request_exception_propagation(self):
        """Test that before_request handler exceptions are propagated"""
        def failing_before_handler(event_name, data):
            raise ConnectionError("Before handler failed")

        def normal_handler(data):
            return "should not reach"

        self.router.add_before_request(failing_before_handler)
        self.router.register_route("before_fail_event", normal_handler)

        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request:
                mock_request.sid = "test_socket_before_error"
                with pytest.raises(ConnectionError) as exc_info:
                    self.router.handle_event("before_fail_event", "test_data")

        assert "Before handler failed" in str(exc_info.value)

    def test_after_request_handlers_called_on_error(self):
        """Test that after_request handlers are called even when main handler fails"""
        after_handler_calls = []

        def after_handler_success(event_name, data, result, error=None):
            after_handler_calls.append(("success", event_name, data, result, error))

        def after_handler_with_error_param(event_name, data, result=None, error=None):
            after_handler_calls.append(("with_error", event_name, data, result, error))

        def failing_handler(data):
            raise ValueError("Main handler failed")

        self.router.add_after_request(after_handler_success)
        self.router.add_after_request(after_handler_with_error_param)
        self.router.register_route("error_after_event", failing_handler)

        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request:
                mock_request.sid = "test_socket_after_error"
                with pytest.raises(ValueError):
                    self.router.handle_event("error_after_event", "test_data")

        # Both after handlers should have been called
        assert len(after_handler_calls) == 2

        # Check calls - error should be passed to handlers that support it
        success_call = after_handler_calls[0]
        error_call = after_handler_calls[1]

        assert success_call[0] == "success"
        assert success_call[1] == "error_after_event"
        assert success_call[2] == "test_data"
        assert success_call[3] is None  # result is None on error
        assert isinstance(success_call[4], ValueError)

        assert error_call[0] == "with_error"
        assert error_call[1] == "error_after_event"
        assert error_call[2] == "test_data"
        assert error_call[3] is None
        assert isinstance(error_call[4], ValueError)

    def test_after_request_handler_exception_handling(self):
        """Test that exceptions in after_request handlers are caught and logged"""
        def failing_after_handler(event_name, data, result, error=None):
            raise RuntimeError("After handler failed")

        def normal_handler(data):
            raise ValueError("Main handler failed")

        self.router.add_after_request(failing_after_handler)
        self.router.register_route("after_handler_fail_event", normal_handler)

        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request, \
                 patch('src.handlers.socket_event_router.logger') as mock_logger:
                mock_request.sid = "test_socket_after_fail"

                # Original exception should still be raised
                with pytest.raises(ValueError) as exc_info:
                    self.router.handle_event("after_handler_fail_event", "test_data")

                assert "Main handler failed" in str(exc_info.value)

                # After handler error should be logged
                mock_logger.error.assert_any_call("Error in after_request handler: After handler failed")


class TestSocketEventRouterLogging:
    """Test logging functionality in event router"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.router = SocketEventRouter()
        self.app = Flask(__name__)

    def test_event_logging(self):
        """Test that events are properly logged"""
        def test_handler(data):
            return "response"

        self.router.register_route("logged_event", test_handler)

        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request, \
                 patch('src.handlers.socket_event_router.logger') as mock_logger:
                mock_request.sid = "test_socket_logging"

                result = self.router.handle_event("logged_event", "test_data")

        # Check logging calls
        mock_logger.info.assert_any_call("Handling event: logged_event from client: test_socket_logging")
        mock_logger.debug.assert_any_call("Event data: test_data")
        mock_logger.debug.assert_any_call("Successfully handled event: logged_event")

    def test_error_logging(self):
        """Test that errors are properly logged"""
        def failing_handler(data):
            raise ValueError("Test error")

        self.router.register_route("error_logged_event", failing_handler)

        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request, \
                 patch('src.handlers.socket_event_router.logger') as mock_logger:
                mock_request.sid = "test_socket_error_logging"

                with pytest.raises(ValueError):
                    self.router.handle_event("error_logged_event", "test_data")

        # Check error logging
        mock_logger.error.assert_any_call("Error handling event error_logged_event: Test error")

    def test_registration_logging(self):
        """Test that route and middleware registration is logged"""
        def test_handler(data):
            pass

        def test_middleware(event_name, data):
            return data

        def test_before(event_name, data):
            pass

        def test_after(event_name, data, result):
            pass

        with patch('src.handlers.socket_event_router.logger') as mock_logger:
            self.router.register_route("test_event", test_handler)
            self.router.add_middleware(test_middleware)
            self.router.add_before_request(test_before)
            self.router.add_after_request(test_after)

        # Check logging calls
        mock_logger.debug.assert_any_call("Registered route: test_event -> test_handler")
        mock_logger.debug.assert_any_call("Added middleware: test_middleware")
        mock_logger.debug.assert_any_call("Added before_request handler: test_before")
        mock_logger.debug.assert_any_call("Added after_request handler: test_after")


class TestSocketIOIntegration:
    """Test SocketIO integration functionality"""

    def test_create_router_with_socketio(self):
        """Test router creation with SocketIO instance"""
        mock_socketio = Mock()

        router = create_router_with_socketio(mock_socketio)

        assert isinstance(router, SocketEventRouter)
        assert hasattr(router, 'register_with_socketio')

    def test_router_socketio_registration(self):
        """Test that routes are registered with SocketIO instance"""
        mock_socketio = Mock()

        router = create_router_with_socketio(mock_socketio)

        # Register some test routes
        @router.route("test_event1")
        def handler1(data):
            return "response1"

        @router.route("test_event2")
        def handler2(data):
            return "response2"

        # Register with SocketIO
        with patch('src.handlers.socket_event_router.logger') as mock_logger:
            router.register_with_socketio()

        # Check that on_event was called for each route
        assert mock_socketio.on_event.call_count == 2

        # Check the calls
        calls = mock_socketio.on_event.call_args_list
        events_registered = {call[0][0] for call in calls}
        assert events_registered == {"test_event1", "test_event2"}

        # Check logging
        mock_logger.debug.assert_any_call("Registered SocketIO handler for: test_event1")
        mock_logger.debug.assert_any_call("Registered SocketIO handler for: test_event2")

    def test_socketio_handler_creation(self):
        """Test that SocketIO handlers properly route through router"""
        mock_socketio = Mock()

        router = create_router_with_socketio(mock_socketio)

        @router.route("socketio_test")
        def test_handler(data):
            return f"processed: {data}"

        router.register_with_socketio()

        # Get the handler that was registered with SocketIO
        socketio_handler = mock_socketio.on_event.call_args_list[0][0][1]

        # Mock the router's handle_event method to verify it's called
        with patch.object(router, 'handle_event', return_value="mocked_result") as mock_handle:
            result = socketio_handler("test_data")

        # Verify the router's handle_event was called correctly
        mock_handle.assert_called_once_with("socketio_test", "test_data")
        assert result == "mocked_result"


class TestGlobalRouterManagement:
    """Test global router management functions"""

    def setup_method(self):
        """Reset global router state"""
        # Reset the global router
        import src.handlers.socket_event_router
        src.handlers.socket_event_router._default_router = None

    def test_get_router_not_initialized(self):
        """Test getting router when not initialized"""
        with pytest.raises(RuntimeError) as exc_info:
            get_router()

        assert "Router not initialized. Call setup_router() first." in str(exc_info.value)

    def test_setup_router(self):
        """Test router setup with SocketIO instance"""
        mock_socketio = Mock()

        with patch('src.handlers.socket_event_router.logger') as mock_logger:
            router = setup_router(mock_socketio)

        assert isinstance(router, SocketEventRouter)

        # Check that default middleware was added
        assert len(router._middleware) == 2

        # Check logging
        mock_logger.info.assert_called_once_with("Socket event router initialized")

        # Verify we can get the router
        retrieved_router = get_router()
        assert retrieved_router is router


class TestDefaultMiddleware:
    """Test default middleware functions"""

    def test_request_logging_middleware(self):
        """Test request logging middleware"""
        test_data = {"test": "data"}

        with patch('src.handlers.socket_event_router.logger') as mock_logger:
            result = request_logging_middleware("test_event", test_data)

        # Should return data unchanged
        assert result == test_data

        # Should log the event
        mock_logger.info.assert_called_once_with("Processing test_event")

    def test_session_validation_middleware(self):
        """Test session validation middleware"""
        test_data = {"session": "data"}

        result = session_validation_middleware("test_event", test_data)

        # Should return data unchanged (placeholder implementation)
        assert result == test_data


class TestComplexEventHandlingScenarios:
    """Test complex event handling scenarios with multiple components"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.router = SocketEventRouter()
        self.app = Flask(__name__)

    def test_full_pipeline_execution_order(self):
        """Test complete execution pipeline with all components"""
        execution_log = []

        def before1(event_name, data):
            execution_log.append(("before1", event_name, data))

        def before2(event_name, data):
            execution_log.append(("before2", event_name, data))

        def middleware1(event_name, data):
            execution_log.append(("middleware1", event_name, data))
            return f"m1:{data}"

        def middleware2(event_name, data):
            execution_log.append(("middleware2", event_name, data))
            return f"m2:{data}"

        def main_handler(data):
            execution_log.append(("main_handler", data))
            return f"handled:{data}"

        def after1(event_name, data, result):
            execution_log.append(("after1", event_name, data, result))

        def after2(event_name, data, result):
            execution_log.append(("after2", event_name, data, result))

        # Setup pipeline
        self.router.add_before_request(before1)
        self.router.add_before_request(before2)
        self.router.add_middleware(middleware1)
        self.router.add_middleware(middleware2)
        self.router.add_after_request(after1)
        self.router.add_after_request(after2)
        self.router.register_route("complex_event", main_handler)

        # Execute
        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request:
                mock_request.sid = "complex_test"
                result = self.router.handle_event("complex_event", "original")

        # Verify execution order and data flow
        expected_log = [
            ("before1", "complex_event", "original"),
            ("before2", "complex_event", "original"),
            ("middleware1", "complex_event", "original"),
            ("middleware2", "complex_event", "m1:original"),
            ("main_handler", "m2:m1:original"),
            ("after1", "complex_event", "m2:m1:original", "handled:m2:m1:original"),
            ("after2", "complex_event", "m2:m1:original", "handled:m2:m1:original")
        ]

        assert execution_log == expected_log
        assert result == "handled:m2:m1:original"

    def test_multiple_events_with_shared_middleware(self):
        """Test multiple events sharing the same middleware"""
        middleware_calls = []
        handler_calls = []

        def shared_middleware(event_name, data):
            middleware_calls.append((event_name, data))
            return f"processed:{data}"

        def handler1(data):
            handler_calls.append(("handler1", data))
            return f"h1:{data}"

        def handler2(data):
            handler_calls.append(("handler2", data))
            return f"h2:{data}"

        # Setup
        self.router.add_middleware(shared_middleware)
        self.router.register_route("event1", handler1)
        self.router.register_route("event2", handler2)

        # Execute both events
        with self.app.test_request_context():
            with patch('src.handlers.socket_event_router.request') as mock_request:
                mock_request.sid = "shared_test"

                result1 = self.router.handle_event("event1", "data1")
                result2 = self.router.handle_event("event2", "data2")

        # Verify shared middleware was called for both events
        assert middleware_calls == [("event1", "data1"), ("event2", "data2")]
        assert handler_calls == [("handler1", "processed:data1"), ("handler2", "processed:data2")]
        assert result1 == "h1:processed:data1"
        assert result2 == "h2:processed:data2"