"""
Socket Event Router

This module provides declarative event-to-handler mapping with middleware support,
request/response logging, and centralized event management for Socket.IO events.
"""

import logging
from typing import Dict, List, Callable, Any, Optional
from functools import wraps
from flask import request
from flask_socketio import emit

from src.container import get_container

logger = logging.getLogger(__name__)


class EventRouteNotFoundError(Exception):
    """Raised when an event route is not found."""
    pass


class SocketEventRouter:
    """
    Router for Socket.IO events with middleware support and logging.

    Provides declarative event-to-handler mapping, middleware execution,
    and comprehensive request/response logging for debugging and monitoring.
    """

    def __init__(self):
        self._routes: Dict[str, Callable] = {}
        self._middleware: List[Callable] = []
        self._before_request_handlers: List[Callable] = []
        self._after_request_handlers: List[Callable] = []

    def register_route(self, event_name: str, handler: Callable) -> None:
        """Register an event handler for a specific event."""
        self._routes[event_name] = handler
        logger.debug(f"Registered route: {event_name} -> {handler.__name__}")

    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware that will be executed for all events."""
        self._middleware.append(middleware)
        logger.debug(f"Added middleware: {middleware.__name__}")

    def add_before_request(self, handler: Callable) -> None:
        """Add a handler that will be executed before every request."""
        self._before_request_handlers.append(handler)
        logger.debug(f"Added before_request handler: {handler.__name__}")

    def add_after_request(self, handler: Callable) -> None:
        """Add a handler that will be executed after every request."""
        self._after_request_handlers.append(handler)
        logger.debug(f"Added after_request handler: {handler.__name__}")

    def route(self, event_name: str):
        """Decorator for registering event handlers."""
        def decorator(handler: Callable):
            self.register_route(event_name, handler)
            return handler
        return decorator

    def middleware(self):
        """Decorator for registering middleware."""
        def decorator(middleware: Callable):
            self.add_middleware(middleware)
            return middleware
        return decorator

    def handle_event(self, event_name: str, data: Any = None) -> Any:
        """
        Handle an incoming Socket.IO event.

        Executes middleware, before_request handlers, the main handler,
        and after_request handlers in sequence.

        Args:
            event_name: The name of the event to handle
            data: The event data

        Returns:
            The result from the handler (if any)

        Raises:
            EventRouteNotFoundError: If no handler is registered for the event
        """
        if event_name not in self._routes:
            raise EventRouteNotFoundError(f"No handler registered for event: {event_name}")

        # Log incoming request
        logger.info(f"Handling event: {event_name} from client: {request.sid}")
        if data is not None:
            logger.debug(f"Event data: {data}")

        try:
            # Execute before_request handlers
            for handler in self._before_request_handlers:
                handler(event_name, data)

            # Execute middleware
            for middleware in self._middleware:
                data = middleware(event_name, data) or data

            # Execute main handler
            handler = self._routes[event_name]
            result = handler(data)

            # Execute after_request handlers
            for handler in self._after_request_handlers:
                handler(event_name, data, result)

            logger.debug(f"Successfully handled event: {event_name}")
            return result

        except Exception as e:
            logger.error(f"Error handling event {event_name}: {str(e)}")
            # Execute after_request handlers even on error
            for handler in self._after_request_handlers:
                try:
                    handler(event_name, data, None, error=e)
                except Exception as after_error:
                    logger.error(f"Error in after_request handler: {str(after_error)}")
            raise

    def get_registered_events(self) -> List[str]:
        """Get a list of all registered event names."""
        return list(self._routes.keys())

    def has_route(self, event_name: str) -> bool:
        """Check if a route is registered for the given event."""
        return event_name in self._routes


def create_router_with_socketio(socketio_instance) -> SocketEventRouter:
    """
    Create a SocketEventRouter and register all routes with the SocketIO instance.

    This function creates the router, registers all handlers, and then
    registers each route with the SocketIO instance so that events
    are properly routed through the router.

    Args:
        socketio_instance: The Flask-SocketIO instance

    Returns:
        The configured router instance
    """
    router = SocketEventRouter()

    def create_socketio_handler(event_name: str):
        """Create a handler function for SocketIO that routes through our router."""
        @wraps(router.handle_event)
        def socketio_handler(data=None):
            return router.handle_event(event_name, data)
        return socketio_handler

    # This will be called after all routes are registered
    def register_with_socketio():
        for event_name in router.get_registered_events():
            handler = create_socketio_handler(event_name)
            socketio_instance.on_event(event_name, handler)
            logger.debug(f"Registered SocketIO handler for: {event_name}")

    # Monkey patch the register method onto the router
    router.register_with_socketio = register_with_socketio

    return router


def request_logging_middleware(event_name: str, data: Any) -> Any:
    """Middleware for logging requests and responses."""
    start_time = logger.info(f"Processing {event_name}")
    # Return data unchanged - middleware can modify data if needed
    return data


def session_validation_middleware(event_name: str, data: Any) -> Any:
    """Middleware for basic session validation (can be extended)."""
    # This is a placeholder for session validation logic
    # Can be extended to check authentication, rate limiting, etc.
    return data


# Create the default router instance (will be configured during app startup)
_default_router: Optional[SocketEventRouter] = None


def get_router() -> SocketEventRouter:
    """Get the default router instance."""
    if _default_router is None:
        raise RuntimeError("Router not initialized. Call setup_router() first.")
    return _default_router


def setup_router(socketio_instance) -> SocketEventRouter:
    """Set up the default router with the SocketIO instance."""
    global _default_router
    _default_router = create_router_with_socketio(socketio_instance)

    # Add default middleware
    _default_router.add_middleware(request_logging_middleware)
    _default_router.add_middleware(session_validation_middleware)

    logger.info("Socket event router initialized")
    return _default_router