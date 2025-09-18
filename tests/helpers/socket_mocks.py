"""
Common SocketIO mock patterns for testing.
Provides standardized mock objects and utilities for testing Socket.IO functionality.
"""

from unittest.mock import Mock, MagicMock


def create_mock_socketio():
    """Create a standardized mock SocketIO object for testing.

    Returns:
        Mock: A configured mock SocketIO object with common methods
    """
    mock_socketio = Mock()

    # Configure common methods
    mock_socketio.emit = Mock()
    mock_socketio.join_room = Mock()
    mock_socketio.leave_room = Mock()
    mock_socketio.close_room = Mock()

    # Reset call counts for clean testing
    mock_socketio.reset_mock()

    return mock_socketio


def create_broadcast_service_mocks():
    """Create a set of mocks commonly used with BroadcastService.

    Returns:
        dict: Dictionary containing mock objects for broadcast service testing
    """
    return {
        'socketio': create_mock_socketio(),
        'room_manager': Mock(),
        'game_manager': Mock(),
        'error_response_factory': Mock(),
        'room_state_presenter': Mock()
    }


class MockSocketIOTestHelper:
    """Helper class for testing SocketIO interactions with standardized assertions."""

    def __init__(self, mock_socketio=None):
        """Initialize with a mock SocketIO object.

        Args:
            mock_socketio: Optional mock SocketIO object. If None, creates one.
        """
        self.mock_socketio = mock_socketio or create_mock_socketio()

    def assert_emit_called_with(self, event, data=None, room=None):
        """Assert that emit was called with specific parameters.

        Args:
            event (str): The event name
            data: Expected data (optional)
            room (str): Expected room (optional)
        """
        if data is not None and room is not None:
            self.mock_socketio.emit.assert_called_with(event, data, room=room)
        elif data is not None:
            self.mock_socketio.emit.assert_called_with(event, data)
        elif room is not None:
            # Check if emit was called with event and room parameter
            calls = self.mock_socketio.emit.call_args_list
            matching_calls = [call for call in calls
                             if call[0][0] == event and
                             (len(call[1]) > 0 and call[1].get('room') == room)]
            assert len(matching_calls) > 0, f"Expected emit call with event '{event}' and room '{room}' not found"
        else:
            self.mock_socketio.emit.assert_called_with(event)

    def assert_emit_called_once(self):
        """Assert that emit was called exactly once."""
        self.mock_socketio.emit.assert_called_once()

    def assert_emit_not_called(self):
        """Assert that emit was never called."""
        self.mock_socketio.emit.assert_not_called()

    def get_emit_calls(self):
        """Get all emit call arguments for inspection.

        Returns:
            list: List of call arguments
        """
        return self.mock_socketio.emit.call_args_list

    def reset_mock(self):
        """Reset the mock call history."""
        self.mock_socketio.reset_mock()