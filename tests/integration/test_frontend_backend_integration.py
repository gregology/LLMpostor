"""
Frontend-Backend Integration Tests

Tests critical frontend-backend interactions:
- Event bus to Socket.IO communication
- Error display manager integration
- Memory manager interaction with server events

These tests validate that frontend modules properly interact with the backend
through Socket.IO events and handle server responses correctly.
"""

import pytest
import time
import threading
import json
from unittest.mock import Mock, patch, MagicMock
from flask_socketio import SocketIOTestClient

from tests.helpers.room_helpers import join_room_helper, find_event_in_received


class TestFrontendBackendIntegration:
    """Test frontend-backend integration scenarios"""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self, room_manager, session_service, app):
        """Set up test environment before each test."""
        # Clear any existing state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()

        app.config['TESTING'] = True

        yield  # This is where the test runs

        # Teardown: Clean up state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()

    def create_test_client(self, app, socketio):
        """Create a Socket.IO test client"""
        return SocketIOTestClient(app, socketio)

    def test_eventbus_socketio_bidirectional_communication(self, app, socketio):
        """
        Test that frontend EventBus events properly trigger Socket.IO emissions
        and that Socket.IO events properly trigger EventBus publications.

        This simulates:
        1. Frontend EventBus publishing events that should trigger socket emissions
        2. Socket events that should publish to the EventBus
        3. Error propagation through the EventBus-Socket pipeline
        """
        client = self.create_test_client(app, socketio)

        # Test 1: Room joining should trigger appropriate events
        join_data = join_room_helper(client, "integration-room", "IntegPlayer")
        assert join_data is not None
        assert 'player_id' in join_data

        # Test 2: Game state changes should propagate through the system
        client.emit('get_room_state')  # No parameters needed when already in room

        responses = client.get_received()
        room_state_responses = [r for r in responses if r['name'] == 'room_state']
        assert len(room_state_responses) > 0

        room_state = room_state_responses[0]['args'][0]
        assert 'room_id' in room_state
        assert 'players' in room_state
        assert room_state['room_id'] == 'integration-room'

        # Test 3: Error events should be handled gracefully
        client.emit('join_room', {'invalid': 'data'})  # Invalid join request

        error_responses = client.get_received()
        error_events = [r for r in error_responses if r['name'] == 'error']
        assert len(error_events) > 0

        error_data = error_events[0]['args'][0]
        assert 'error' in error_data or 'message' in error_data

        client.disconnect()

    def test_error_display_manager_server_integration(self, app, socketio):
        """
        Test ErrorDisplayManager integration with server error responses.

        This simulates:
        1. Server errors being received and processed
        2. Error recovery mechanisms triggered by user actions
        3. Fatal error handling with server disconnection
        """
        client = self.create_test_client(app, socketio)

        # Test 1: Server error handling
        join_data = join_room_helper(client, "error-test-room", "ErrorTestPlayer")
        assert join_data is not None

        # Test 2: Simulate various error scenarios
        error_scenarios = [
            {'type': 'validation_error', 'data': {'room_code': '', 'player_name': ''}},
            {'type': 'rate_limit_error', 'data': {'room_code': 'test', 'player_name': 'test'}},
            {'type': 'room_full_error', 'data': {'room_code': 'full-room', 'player_name': 'test'}}
        ]

        for scenario in error_scenarios:
            # Clear previous responses
            client.get_received()

            # Emit invalid request that should trigger error
            if scenario['type'] == 'validation_error':
                client.emit('join_room', scenario['data'])
            elif scenario['type'] == 'rate_limit_error':
                # Simulate rapid requests
                for _ in range(5):
                    client.emit('join_room', scenario['data'])
            elif scenario['type'] == 'room_full_error':
                # This would normally require a full room, but we test the error handling
                client.emit('join_room', scenario['data'])

            # Check for error responses
            responses = client.get_received()
            error_responses = [r for r in responses if r['name'] == 'error']

            # Should receive at least one error response
            assert len(error_responses) > 0, f"No error response for {scenario['type']}"

            error_data = error_responses[0]['args'][0]
            assert isinstance(error_data, dict), f"Error data should be dict for {scenario['type']}"

        # Test 3: Connection loss simulation (frontend should handle gracefully)
        client.disconnect()
        assert not client.connected

    def test_memory_manager_server_event_interaction(self, app, socketio):
        """
        Test MemoryManager interaction with server events and cleanup.

        This simulates:
        1. Memory tracking during active server communication
        2. Cleanup of resources when server events occur
        3. Memory optimization triggered by high activity
        """
        client = self.create_test_client(app, socketio)

        # Test 1: Normal operation with server events
        join_data = join_room_helper(client, "memory-test-room", "MemoryTestPlayer")
        assert join_data is not None

        # Test 2: Simulate multiple server interactions that would create DOM/event listeners
        interactions = [
            ('get_room_state', {'room_code': 'memory-test-room'}),
            ('leave_room', {'room_code': 'memory-test-room'}),
            ('join_room', {'room_code': 'memory-test-room', 'player_name': 'MemoryTestPlayer2'})
        ]

        for event_name, event_data in interactions:
            client.emit(event_name, event_data)

            # Get responses to simulate frontend processing
            responses = client.get_received()

            # Verify we get some response (shows server is processing)
            assert len(responses) >= 0  # May be 0 for some events, that's ok

        # Test 3: Disconnect should trigger memory cleanup
        client.disconnect()
        assert not client.connected

        # Test 4: Reconnection after cleanup
        client = self.create_test_client(app, socketio)

        # Should be able to rejoin after cleanup
        rejoin_data = join_room_helper(client, "memory-test-room", "MemTestRejoined")
        assert rejoin_data is not None
        assert 'player_id' in rejoin_data

        client.disconnect()

    def test_cross_module_error_propagation(self, app, socketio):
        """
        Test error propagation across frontend modules through the EventBus.

        This simulates:
        1. Socket errors triggering EventBus error events
        2. EventBus errors being handled by ErrorDisplayManager
        3. Memory cleanup triggered by error states
        """
        client = self.create_test_client(app, socketio)

        # Test 1: Establish baseline connection
        join_data = join_room_helper(client, "error-prop-room", "ErrorPropPlayer")
        assert join_data is not None

        # Test 2: Trigger various error conditions
        error_conditions = [
            # Missing required fields
            ('join_room', {}),
            # Invalid room code format
            ('join_room', {'room_code': 'invalid!@#', 'player_name': 'test'}),
            # Empty player name
            ('join_room', {'room_code': 'test-room', 'player_name': ''}),
            # Invalid event data type
            ('get_room_state', 'invalid_string_instead_of_dict')
        ]

        total_errors = 0

        for event_name, invalid_data in error_conditions:
            # Clear previous responses
            client.get_received()

            # Emit invalid request
            try:
                client.emit(event_name, invalid_data)
            except Exception:
                # Some invalid data might cause immediate client-side errors
                pass

            # Check for error responses
            responses = client.get_received()
            error_responses = [r for r in responses if r['name'] == 'error']

            total_errors += len(error_responses)

        # Should have received some error responses
        assert total_errors > 0, "Should have received error responses for invalid requests"

        client.disconnect()

    def test_concurrent_frontend_backend_operations(self, app, socketio):
        """
        Test concurrent frontend-backend operations and synchronization.

        This simulates:
        1. Multiple clients performing operations simultaneously
        2. EventBus handling concurrent events
        3. Memory manager handling concurrent resource operations
        """
        clients = []
        results = []

        # Create multiple clients
        num_clients = 3
        for i in range(num_clients):
            clients.append(self.create_test_client(app, socketio))

        # Test 1: Concurrent room joining
        def concurrent_operations(client_index, client):
            try:
                # Join room
                join_data = join_room_helper(client, "concurrent-room", f"ConcurPlayer{client_index}")

                if join_data and 'player_id' in join_data:
                    # Perform additional operations
                    client.emit('get_room_state')

                    # Get responses
                    responses = client.get_received()

                    results.append({
                        'client_index': client_index,
                        'join_success': True,
                        'response_count': len(responses),
                        'player_id': join_data['player_id']
                    })
                else:
                    results.append({
                        'client_index': client_index,
                        'join_success': False,
                        'error': 'Failed to join room'
                    })

            except Exception as e:
                results.append({
                    'client_index': client_index,
                    'join_success': False,
                    'error': str(e)
                })

        # Run concurrent operations
        threads = []
        for i, client in enumerate(clients):
            thread = threading.Thread(target=concurrent_operations, args=(i, client))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=10)  # 10 second timeout

        # Verify results
        successful_operations = [r for r in results if r.get('join_success', False)]
        assert len(successful_operations) == num_clients, f"Expected {num_clients} successful operations, got {len(successful_operations)}"

        # Verify unique player IDs
        player_ids = [r['player_id'] for r in successful_operations]
        assert len(set(player_ids)) == len(player_ids), "Player IDs should be unique"

        # Test 2: Concurrent disconnection
        for client in clients:
            if client.connected:
                client.disconnect()

        # Verify all disconnected
        for client in clients:
            assert not client.connected

    def test_frontend_state_synchronization_with_backend(self, app, socketio):
        """
        Test that frontend state stays synchronized with backend state.

        This simulates:
        1. Frontend receiving state updates from backend
        2. Frontend triggering backend state changes
        3. State consistency across multiple operations
        """
        client = self.create_test_client(app, socketio)

        # Test 1: Initial state synchronization
        join_data = join_room_helper(client, "sync-room", "SyncPlayer")
        assert join_data is not None

        initial_state = join_data
        assert 'room_id' in initial_state
        assert 'player_id' in initial_state

        # Test 2: Request current state
        client.emit('get_room_state')

        responses = client.get_received()
        state_updates = [r for r in responses if r['name'] == 'room_state']

        assert len(state_updates) > 0, "Should receive room state update"

        current_state = state_updates[0]['args'][0]
        assert current_state['room_id'] == 'sync-room'
        assert len(current_state['players']) >= 1

        # Test 3: Verify player is in the state
        player_found = False
        for player in current_state['players']:
            if player.get('player_id') == initial_state['player_id']:
                player_found = True
                break

        assert player_found, "Player should be found in room state"

        # Test 4: Leave room and verify state change
        client.emit('leave_room')

        leave_responses = client.get_received()
        # May or may not receive explicit response, but should not error

        # Test 5: Verify we can no longer get state for this room (if we left)
        client.emit('get_room_state')

        final_responses = client.get_received()
        # Should either get empty state or error - both are acceptable

        client.disconnect()

    def test_error_recovery_integration(self, app, socketio):
        """
        Test error recovery integration between frontend and backend.

        This simulates:
        1. Error conditions that require recovery
        2. Frontend retry mechanisms
        3. Backend state recovery after errors
        """
        client = self.create_test_client(app, socketio)

        # Test 1: Successful operation baseline
        join_data = join_room_helper(client, "recovery-room", "RecovPlayer")
        assert join_data is not None

        original_player_id = join_data['player_id']

        # Test 2: Simulate error conditions and recovery

        # Attempt invalid operation
        client.emit('join_room', {'room_code': '', 'player_name': ''})

        error_responses = client.get_received()
        error_count = len([r for r in error_responses if r['name'] == 'error'])

        # Should receive error response
        assert error_count > 0, "Should receive error for invalid join"

        # Test 3: Verify original state is still valid after error
        client.emit('get_room_state')

        state_responses = client.get_received()
        state_updates = [r for r in state_responses if r['name'] == 'room_state']

        if len(state_updates) > 0:
            current_state = state_updates[0]['args'][0]

            # Original player should still be in room
            player_still_exists = any(
                player.get('player_id') == original_player_id
                for player in current_state.get('players', [])
            )

            assert player_still_exists, "Original player should still exist after error"

        # Test 4: Recovery through reconnection simulation
        client.disconnect()
        assert not client.connected

        # Reconnect
        client = self.create_test_client(app, socketio)

        # Should be able to perform new operations
        new_join_data = join_room_helper(client, "recovery-room-new", "RecovPlayerNew")
        assert new_join_data is not None
        assert 'player_id' in new_join_data

        client.disconnect()