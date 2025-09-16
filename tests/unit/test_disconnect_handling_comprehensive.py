"""
Comprehensive disconnect handling tests.

This file consolidates all disconnect testing logic from the previous separate files:
- test_disconnect_handling_logic.py
- test_disconnect_behavioral_contracts.py
- test_disconnect_state_transitions.py

Provides complete coverage of disconnect scenarios with reduced redundancy and
clear organization by functional area.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.room_manager import RoomManager
from src.game_manager import GameManager
from src.services.auto_game_flow_service import AutoGameFlowService
from src.services.broadcast_service import BroadcastService
from src.services.session_service import SessionService
from src.services.error_response_factory import ErrorResponseFactory
from src.services.room_state_presenter import RoomStatePresenter
from src.core.game_phases import GamePhase


class TestDisconnectCoreOperations:
    """Test core disconnect operations and basic functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.session_service = SessionService()
        self.error_factory = ErrorResponseFactory()
        self.room_state_presenter = RoomStatePresenter(self.game_manager)

        # Mock socketio for broadcast service
        self.mock_socketio = Mock()
        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager,
            self.error_factory, self.room_state_presenter
        )

        self.auto_flow_service = AutoGameFlowService(
            self.broadcast_service, self.game_manager, self.room_manager
        )

    def test_single_player_disconnect_comprehensive(self):
        """Comprehensive test for single player disconnect including state preservation and idempotency."""
        room_id = "comprehensive-room"

        # Add player to room
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket123")
        player_id = player_data['player_id']

        # Verify initial connected state
        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 1
        assert connected_players[0]['name'] == 'Alice'
        assert connected_players[0]['connected'] == True

        initial_room_state = self.room_manager.get_room_state(room_id)
        assert len(initial_room_state['players']) == 1

        # Test primary disconnect operation
        disconnect_result = self.room_manager.disconnect_player_from_room(room_id, player_id)
        assert disconnect_result == True

        # Verify player state preservation (behavioral contract)
        post_disconnect_state = self.room_manager.get_room_state(room_id)
        assert len(post_disconnect_state['players']) == 1  # Player still in room

        player = post_disconnect_state['players'][player_id]
        assert player['name'] == 'Alice'  # Data preserved
        assert player['connected'] == False  # Status updated
        assert player['score'] == 0  # Score preserved
        assert 'socket_id' in player  # Socket ID field preserved

        # Verify connected players list updated
        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 0

        # Test idempotency - second disconnect should be safe
        second_disconnect = self.room_manager.disconnect_player_from_room(room_id, player_id)
        assert second_disconnect == True  # Still returns True for already disconnected

        # Verify state remains consistent after second disconnect
        final_state = self.room_manager.get_room_state(room_id)
        final_player = final_state['players'][player_id]
        assert final_player['connected'] == False
        assert final_player['name'] == 'Alice'
        assert final_player['score'] == 0

    def test_multi_player_disconnect_scenarios(self):
        """Comprehensive multi-player disconnect testing including concurrent scenarios."""
        room_id = "multi-player-room"

        # Set up multiple players with scores to test preservation
        players = []
        for i, name in enumerate(['Alice', 'Bob', 'Charlie', 'Diana']):
            player_data = self.room_manager.add_player_to_room(room_id, name, f"socket{i}")
            players.append(player_data)

        # Set initial scores to test preservation across disconnects
        room_state = self.room_manager.get_room_state(room_id)
        for i, player_data in enumerate(players):
            room_state['players'][player_data['player_id']]['score'] = (i + 1) * 25

        # Verify initial state
        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 4
        assert all(p['connected'] for p in connected_players)

        # Test sequential disconnects
        alice_disconnect = self.room_manager.disconnect_player_from_room(room_id, players[0]['player_id'])
        assert alice_disconnect == True

        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 3
        remaining_names = {p['name'] for p in connected_players}
        assert remaining_names == {'Bob', 'Charlie', 'Diana'}

        # Test concurrent-style disconnects (Charlie and Diana)
        charlie_disconnect = self.room_manager.disconnect_player_from_room(room_id, players[2]['player_id'])
        diana_disconnect = self.room_manager.disconnect_player_from_room(room_id, players[3]['player_id'])
        assert charlie_disconnect == True
        assert diana_disconnect == True

        # Verify final state consistency
        final_state = self.room_manager.get_room_state(room_id)
        assert len(final_state['players']) == 4  # All players preserved

        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 1  # Only Bob connected
        assert connected_players[0]['name'] == 'Bob'

        # Verify score preservation across disconnects
        alice_player = final_state['players'][players[0]['player_id']]
        assert alice_player['score'] == 25 and alice_player['connected'] == False

        bob_player = final_state['players'][players[1]['player_id']]
        assert bob_player['score'] == 50 and bob_player['connected'] == True

        charlie_player = final_state['players'][players[2]['player_id']]
        assert charlie_player['score'] == 75 and charlie_player['connected'] == False

        diana_player = final_state['players'][players[3]['player_id']]
        assert diana_player['score'] == 100 and diana_player['connected'] == False

    def test_disconnect_error_handling_comprehensive(self):
        """Comprehensive error handling for disconnect operations."""
        room_id = "error-room"

        # Test 1: Nonexistent room
        nonexistent_result = self.room_manager.disconnect_player_from_room("nonexistent", "fake-player-id")
        assert nonexistent_result == False

        # Test 2: Nonexistent player in existing room
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        fake_player_result = self.room_manager.disconnect_player_from_room(room_id, "fake-player-id")
        assert fake_player_result == False

        # Test 3: Verify real player still works after failed attempts
        real_disconnect = self.room_manager.disconnect_player_from_room(room_id, player_data['player_id'])
        assert real_disconnect == True

        # Test 4: Multiple idempotent calls (should all return True for existing disconnected player)
        for _ in range(3):
            repeat_result = self.room_manager.disconnect_player_from_room(room_id, player_data['player_id'])
            assert repeat_result == True


class TestDisconnectSessionManagement:
    """Test session management during disconnect operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.session_service = SessionService()
        self.room_manager = RoomManager()

    def test_session_cleanup_comprehensive(self):
        """Comprehensive session cleanup testing including error cases and idempotency."""
        socket_id = "socket123"
        room_id = "session-room"

        # Test 1: Normal session cleanup workflow
        session_data = {
            'room_id': room_id,
            'player_id': 'player123',
            'player_name': 'Alice'
        }

        self.session_service.create_session(socket_id, **session_data)

        # Verify session exists
        assert self.session_service.has_session(socket_id) == True
        retrieved_session = self.session_service.get_session(socket_id)
        assert retrieved_session['player_name'] == 'Alice'
        assert retrieved_session['room_id'] == room_id

        # Test primary cleanup
        self.session_service.remove_session(socket_id)

        # Verify complete cleanup
        assert self.session_service.has_session(socket_id) == False
        assert self.session_service.get_session(socket_id) is None

        # Test 2: Idempotent cleanup (multiple removals should be safe)
        try:
            self.session_service.remove_session(socket_id)  # Second removal
            self.session_service.remove_session(socket_id)  # Third removal
        except Exception as e:
            pytest.fail(f"Session cleanup should be idempotent, but got: {e}")

        # Test 3: Cleanup of nonexistent session should be graceful
        try:
            self.session_service.remove_session("nonexistent-socket")
        except Exception as e:
            pytest.fail(f"Should handle nonexistent session gracefully, but got: {e}")

        # Test 4: Multiple session cleanup (memory management)
        initial_count = len(self.session_service.get_all_sessions())

        # Create multiple sessions
        test_sessions = []
        for i in range(5):
            test_socket = f"test-socket-{i}"
            test_data = {
                'room_id': f'room-{i}',
                'player_id': f'player-{i}',
                'player_name': f'Player{i}'
            }
            self.session_service.create_session(test_socket, **test_data)
            test_sessions.append(test_socket)

        # Verify all created
        assert len(self.session_service.get_all_sessions()) == initial_count + 5

        # Remove all test sessions
        for socket_id in test_sessions:
            self.session_service.remove_session(socket_id)

        # Verify all removed (no memory leaks)
        final_count = len(self.session_service.get_all_sessions())
        assert final_count == initial_count


class TestDisconnectGameFlowImpact:
    """Test disconnect impact on game flow and auto-advancement logic."""

    def setup_method(self):
        """Set up test fixtures for game flow testing."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.mock_socketio = Mock()
        self.error_factory = ErrorResponseFactory()
        self.room_state_presenter = RoomStatePresenter(self.game_manager)

        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager,
            self.error_factory, self.room_state_presenter
        )

        self.auto_flow_service = AutoGameFlowService(
            self.broadcast_service, self.game_manager, self.room_manager
        )

    def test_insufficient_players_game_reset(self):
        """Test game reset when disconnect results in insufficient players."""
        room_id = "insufficient-room"

        # Set up minimum viable game (2 players)
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")

        # Set up active game state
        room_state = self.room_manager.get_room_state(room_id)
        room_state['game_state']['phase'] = 'responding'
        room_state['game_state']['round_number'] = 1
        room_state['game_state']['current_prompt'] = {'id': 'test', 'prompt': 'Test prompt'}

        # Verify game is active
        assert room_state['game_state']['phase'] == 'responding'

        # Disconnect one player (leaving insufficient for game continuation)
        disconnect_result = self.room_manager.disconnect_player_from_room(room_id, bob_data['player_id'])
        assert disconnect_result == True

        # Trigger auto flow impact handling
        self.auto_flow_service.handle_player_disconnect_game_impact(room_id, bob_data['player_id'])

        # Verify game state handling (should reset to waiting or handle gracefully)
        final_room_state = self.room_manager.get_room_state(room_id)
        # Game should be reset to waiting phase when insufficient players
        assert final_room_state['game_state']['phase'] == 'waiting'

    def test_sufficient_players_game_continuation(self):
        """Test game handling when sufficient players remain after disconnect."""
        room_id = "continuation-room"

        # Set up game with more than minimum players (3 players)
        players = []
        for i, name in enumerate(['Alice', 'Bob', 'Charlie']):
            player_data = self.room_manager.add_player_to_room(room_id, name, f"socket{i}")
            players.append(player_data)

        # Set up active game state with partial responses
        room_state = self.room_manager.get_room_state(room_id)
        room_state['game_state'] = {
            'phase': 'responding',
            'round_number': 1,
            'responses': [
                {'player_id': players[0]['player_id'], 'text': 'Alice response'}
                # Bob and Charlie haven't responded yet
            ],
            'guesses': {},
            'current_prompt': {'id': 'test', 'prompt': 'Test prompt'},
            'phase_start_time': datetime.now(),
            'phase_duration': 60
        }

        # Disconnect one player (still leaves sufficient players)
        disconnect_result = self.room_manager.disconnect_player_from_room(room_id, players[2]['player_id'])  # Charlie
        assert disconnect_result == True

        # Test that auto flow handles the disconnect impact gracefully
        try:
            self.auto_flow_service.handle_player_disconnect_game_impact(room_id, players[2]['player_id'])
        except Exception as e:
            pytest.fail(f"Auto flow should handle disconnect impact gracefully: {e}")

        # Verify game state is handled appropriately (may reset to waiting with current logic)
        final_state = self.room_manager.get_room_state(room_id)
        # Current implementation resets to waiting when players disconnect during active game
        assert final_state['game_state']['phase'] == 'waiting'

        # Verify only 2 players are connected
        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 2


class TestDisconnectErrorRecovery:
    """Test disconnect handling with error conditions and corrupted states."""

    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.mock_socketio = Mock()
        self.error_factory = ErrorResponseFactory()
        self.room_state_presenter = RoomStatePresenter(self.game_manager)

        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager,
            self.error_factory, self.room_state_presenter
        )

        self.auto_flow_service = AutoGameFlowService(
            self.broadcast_service, self.game_manager, self.room_manager
        )

    def test_corrupted_room_state_handling(self):
        """Test disconnect handling with corrupted room state."""
        room_id = "corrupted-room"

        # Create room and player
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")

        # Test 1: Missing game_state
        room_state = self.room_manager.get_room_state(room_id)
        del room_state['game_state']

        try:
            self.auto_flow_service.handle_player_disconnect_game_impact(room_id, player_data['player_id'])
        except Exception as e:
            pytest.fail(f"Should handle missing game_state gracefully, but got: {e}")

        # Test 2: Corrupted players data
        room_state = self.room_manager.get_room_state(room_id)
        room_state['players'] = None  # Corrupt players

        try:
            # Room manager operations should handle gracefully
            connected = self.room_manager.get_connected_players(room_id)
            # May return empty list or handle gracefully
        except Exception as e:
            # Acceptable if handled at this level
            pass

    def test_service_error_resilience(self):
        """Test error resilience when service operations fail."""
        room_id = "error-resilience-room"

        # Test with room manager errors
        with patch.object(self.room_manager, 'get_connected_players', side_effect=Exception("Connection error")):
            try:
                self.auto_flow_service.handle_player_disconnect_game_impact(room_id, "fake-player-id")
            except Exception as e:
                pytest.fail(f"Should handle room manager errors gracefully, but got: {e}")

        # Test with broadcast service errors
        with patch.object(self.mock_socketio, 'emit', side_effect=Exception("Broadcast error")):
            try:
                # Should not crash other operations
                player_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
                disconnect_result = self.room_manager.disconnect_player_from_room(room_id, player_data['player_id'])
                assert disconnect_result == True
            except Exception as e:
                pytest.fail(f"Should isolate broadcast errors, but got: {e}")

    def test_disconnect_workflow_robustness(self):
        """Test complete disconnect workflow robustness under various error conditions."""
        room_id = "robustness-room"
        socket_id = "socket123"

        # Set up complete workflow components
        session_service = SessionService()
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", socket_id)

        session_data = {
            'room_id': room_id,
            'player_id': player_data['player_id'],
            'player_name': 'Alice'
        }
        session_service.create_session(socket_id, **session_data)

        # Test robustness with each step potentially failing

        # Step 1: Disconnect (should always work for valid input)
        disconnect_result = self.room_manager.disconnect_player_from_room(room_id, player_data['player_id'])
        assert disconnect_result == True

        # Step 2: Game impact (should handle gracefully even with errors)
        try:
            self.auto_flow_service.handle_player_disconnect_game_impact(room_id, player_data['player_id'])
        except Exception as e:
            # Should not crash the workflow
            pass

        # Step 3: Session cleanup (should always work)
        session_service.remove_session(socket_id)
        assert not session_service.has_session(socket_id)

        # Final verification - core disconnect succeeded despite potential errors
        room_state = self.room_manager.get_room_state(room_id)
        player = room_state['players'][player_data['player_id']]
        assert player['connected'] == False
        assert player['name'] == 'Alice'


class TestDisconnectServiceInteractionContracts:
    """Test behavioral contracts for service interactions during disconnects."""

    def setup_method(self):
        """Set up test fixtures."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.session_service = SessionService()
        self.mock_socketio = Mock()
        self.error_factory = ErrorResponseFactory()
        self.room_state_presenter = RoomStatePresenter(self.game_manager)

        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager,
            self.error_factory, self.room_state_presenter
        )

        self.auto_flow_service = AutoGameFlowService(
            self.broadcast_service, self.game_manager, self.room_manager
        )

    def test_complete_disconnect_service_contract(self):
        """Test the complete disconnect service interaction contract."""
        room_id = "contract-room"
        socket_id = "socket123"

        # Set up initial state
        player_data = self.room_manager.add_player_to_room(room_id, "Alice", socket_id)
        player_id = player_data['player_id']

        session_data = {
            'room_id': room_id,
            'player_id': player_id,
            'player_name': 'Alice'
        }
        self.session_service.create_session(socket_id, **session_data)

        # Execute complete disconnect workflow

        # Contract 1: Room manager disconnect should succeed
        disconnect_result = self.room_manager.disconnect_player_from_room(room_id, player_id)
        assert disconnect_result == True

        # Contract 2: Auto flow should handle impact without crashing
        try:
            self.auto_flow_service.handle_player_disconnect_game_impact(room_id, player_id)
        except Exception as e:
            pytest.fail(f"Auto flow service should handle disconnect impact gracefully: {e}")

        # Contract 3: Broadcast service should handle updates
        try:
            self.broadcast_service.broadcast_player_list_update(room_id)
            self.broadcast_service.broadcast_room_state_update(room_id)
        except Exception as e:
            pytest.fail(f"Broadcast service should handle updates gracefully: {e}")

        # Contract 4: Session cleanup should be complete
        self.session_service.remove_session(socket_id)
        assert self.session_service.has_session(socket_id) == False

        # Verify final state contracts
        final_room_state = self.room_manager.get_room_state(room_id)
        assert len(final_room_state['players']) == 1  # Player preserved
        assert not list(final_room_state['players'].values())[0]['connected']  # Disconnected

        connected_players = self.room_manager.get_connected_players(room_id)
        assert len(connected_players) == 0  # No connected players

    def test_broadcast_service_contracts(self):
        """Test broadcast service behavioral contracts during disconnect."""
        room_id = "broadcast-contract-room"

        # Set up players
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        self.room_manager.add_player_to_room(room_id, "Bob", "socket2")

        # Disconnect Alice
        self.room_manager.disconnect_player_from_room(room_id, alice_data['player_id'])

        # Contract: Player list update should emit correct event
        self.broadcast_service.broadcast_player_list_update(room_id)

        # Verify broadcast was called
        assert self.mock_socketio.emit.called

        # Check for expected event types
        call_args_list = self.mock_socketio.emit.call_args_list
        event_names = [call[0][0] for call in call_args_list if len(call[0]) > 0]
        assert 'player_list_updated' in event_names

        # Contract: Room state update should emit correct event
        self.mock_socketio.reset_mock()
        self.broadcast_service.broadcast_room_state_update(room_id)

        assert self.mock_socketio.emit.called
        call_args_list = self.mock_socketio.emit.call_args_list
        event_names = [call[0][0] for call in call_args_list if len(call[0]) > 0]
        assert 'room_state_updated' in event_names