"""
Room operation helpers for integration tests.
Provides common patterns for room joining, leaving, and state management.
"""

import time
from typing import Dict, Any, Optional, List


def join_room_helper(client, room_id: str = 'test-room', player_name: str = 'TestPlayer') -> Dict[str, Any]:
    """
    Helper function to join a room and return the response data.

    Args:
        client: SocketIO test client
        room_id (str): Room ID to join
        player_name (str): Player name to use

    Returns:
        dict: Room joined response data

    Raises:
        AssertionError: If room joining fails
    """
    # Clear any existing received messages
    client.get_received()

    # Join room
    client.emit('join_room', {
        'room_id': room_id,
        'player_name': player_name
    })

    # Get response
    received = client.get_received()

    # Find room_joined event
    room_joined_event = find_event_in_received(received, 'room_joined')
    assert room_joined_event is not None, "Should receive room_joined event"

    response = room_joined_event['args'][0]
    assert response['success'] is True, f"Room join should succeed: {response.get('message', 'No message')}"

    return response['data']


def join_room_expect_error(client, room_id: str = '', player_name: str = '') -> Dict[str, Any]:
    """
    Helper function to join a room expecting an error response.

    Args:
        client: SocketIO test client
        room_id (str): Room ID to join (often invalid)
        player_name (str): Player name to use (often invalid)

    Returns:
        dict: Error response data

    Raises:
        AssertionError: If room joining succeeds when it should fail
    """
    # Clear any existing received messages
    client.get_received()

    # Try to join room
    client.emit('join_room', {
        'room_id': room_id,
        'player_name': player_name
    })

    # Get response
    received = client.get_received()

    # Look for error event first
    error_event = find_event_in_received(received, 'error')
    if error_event is not None:
        return error_event['args'][0] if error_event['args'] else error_event

    # If no error event, look for room_joined event with success=False
    room_joined_event = find_event_in_received(received, 'room_joined')
    assert room_joined_event is not None, "Should receive either error or room_joined event"

    response = room_joined_event['args'][0]
    assert response['success'] is False, f"Room join should fail but succeeded: {response}"

    return response


def leave_room_helper(client) -> Dict[str, Any]:
    """
    Helper function to leave a room and return the response data.

    Args:
        client: SocketIO test client

    Returns:
        dict: Leave room response data

    Raises:
        AssertionError: If room leaving fails
    """
    # Clear any existing received messages
    client.get_received()

    # Leave room
    client.emit('leave_room')

    # Get response
    received = client.get_received()

    # Find room_left event
    room_left_event = find_event_in_received(received, 'room_left')
    assert room_left_event is not None, "Should receive room_left event"

    response = room_left_event['args'][0]
    assert response['success'] is True, f"Room leave should succeed: {response.get('message', 'No message')}"

    return response['data']


def find_event_in_received(received: List[Dict], event_name: str) -> Optional[Dict]:
    """
    Helper function to find a specific event in received messages.

    Args:
        received (list): List of received events
        event_name (str): Name of the event to find

    Returns:
        dict or None: The event if found, None otherwise
    """
    for event in received:
        if event.get('name') == event_name:
            return event
    return None


def assert_room_joined_success(response_data: Dict[str, Any], expected_room_id: str, expected_player_name: str):
    """
    Helper function to assert that a room join response is successful and contains expected data.

    Args:
        response_data (dict): Response data from room join
        expected_room_id (str): Expected room ID
        expected_player_name (str): Expected player name
    """
    assert 'room_id' in response_data
    assert 'player_id' in response_data
    assert 'player_name' in response_data
    assert 'message' in response_data
    assert response_data['room_id'] == expected_room_id
    assert response_data['player_name'] == expected_player_name
    assert response_data['player_id'] is not None
    assert len(response_data['player_id']) > 0


def wait_for_room_state_event(client, timeout: float = 1.0) -> Optional[Dict]:
    """
    Wait for a room_state_updated event.

    Args:
        client: SocketIO test client
        timeout (float): Maximum time to wait in seconds

    Returns:
        dict or None: Room state event if received, None if timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        received = client.get_received()
        for event in received:
            if event.get('name') == 'room_state_updated':
                return event
        time.sleep(0.01)  # Small delay to prevent busy waiting
    return None


def wait_for_player_list_event(client, timeout: float = 1.0) -> Optional[Dict]:
    """
    Wait for a player_list_updated event.

    Args:
        client: SocketIO test client
        timeout (float): Maximum time to wait in seconds

    Returns:
        dict or None: Player list event if received, None if timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        received = client.get_received()
        for event in received:
            if event.get('name') == 'player_list_updated':
                return event
        time.sleep(0.01)
    return None


def create_multiple_players(client_factory, room_id: str, player_count: int = 2) -> List[Dict[str, Any]]:
    """
    Create multiple players in a room.

    Args:
        client_factory: Function that creates new test clients
        room_id (str): Room ID to join
        player_count (int): Number of players to create

    Returns:
        list: List of player data dictionaries
    """
    players = []
    clients = []

    for i in range(player_count):
        client = client_factory()
        clients.append(client)

        player_data = join_room_helper(
            client,
            room_id=room_id,
            player_name=f'Player{i + 1}'
        )
        players.append(player_data)

    # Store clients for cleanup (caller should handle this)
    for i, client in enumerate(clients):
        players[i]['_test_client'] = client

    return players


def cleanup_players(players: List[Dict[str, Any]]):
    """
    Clean up test clients for multiple players.

    Args:
        players (list): List of player data with embedded test clients
    """
    for player in players:
        if '_test_client' in player:
            try:
                player['_test_client'].disconnect()
            except Exception:
                pass  # Ignore cleanup errors


class RoomTestHelper:
    """
    Helper class for managing room operations in tests.
    """

    def __init__(self, client):
        """
        Initialize with a test client.

        Args:
            client: SocketIO test client
        """
        self.client = client
        self.room_data = None

    def join_room(self, room_id: str = 'test-room', player_name: str = 'TestPlayer') -> Dict[str, Any]:
        """
        Join a room and store the room data.

        Args:
            room_id (str): Room ID to join
            player_name (str): Player name to use

        Returns:
            dict: Room joined response data
        """
        self.room_data = join_room_helper(self.client, room_id, player_name)
        return self.room_data

    def leave_room(self) -> Dict[str, Any]:
        """
        Leave the current room.

        Returns:
            dict: Leave room response data
        """
        response_data = leave_room_helper(self.client)
        self.room_data = None
        return response_data

    def get_room_state(self) -> Optional[Dict]:
        """
        Get the current room state.

        Returns:
            dict or None: Room state if available
        """
        self.client.get_received()  # Clear buffer
        self.client.emit('get_room_state')
        return wait_for_room_state_event(self.client)

    @property
    def room_id(self) -> Optional[str]:
        """Get the current room ID."""
        return self.room_data.get('room_id') if self.room_data else None

    @property
    def player_id(self) -> Optional[str]:
        """Get the current player ID."""
        return self.room_data.get('player_id') if self.room_data else None

    @property
    def player_name(self) -> Optional[str]:
        """Get the current player name."""
        return self.room_data.get('player_name') if self.room_data else None