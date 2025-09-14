"""
State-based tests for disconnect handling.

Tests the state transitions and invariants during disconnect scenarios,
focusing on game state consistency and player state management.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from src.room_manager import RoomManager
from src.game_manager import GameManager
from src.services.auto_game_flow_service import AutoGameFlowService
from src.services.broadcast_service import BroadcastService
from src.services.session_service import SessionService
from src.services.error_response_factory import ErrorResponseFactory
from src.services.room_state_presenter import RoomStatePresenter


class TestDisconnectStateTransitions:
    """Test state transitions during disconnect scenarios."""

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

    def test_player_state_invariants_on_disconnect(self):
        """Test that player state invariants are maintained during disconnect."""
        room_id = "invariant-room"

        # Initial state: Add players and verify invariants
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")

        initial_room_state = self.room_manager.get_room_state(room_id)

        # Verify initial invariants
        assert len(initial_room_state['players']) == 2
        assert sum(1 for p in initial_room_state['players'].values() if p['connected']) == 2
        assert all(p['score'] == 0 for p in initial_room_state['players'].values())
        assert all('socket_id' in p for p in initial_room_state['players'].values())

        # State transition: Disconnect Alice
        alice_id = alice_data['player_id']
        disconnect_success = self.room_manager.disconnect_player_from_room(room_id, alice_id)
        assert disconnect_success == True

        # Post-disconnect state verification
        post_disconnect_state = self.room_manager.get_room_state(room_id)

        # Verify invariants are maintained
        assert len(post_disconnect_state['players']) == 2  # Player count preserved
        assert sum(1 for p in post_disconnect_state['players'].values() if p['connected']) == 1  # Connection count correct

        # Verify Alice's state
        alice_player = post_disconnect_state['players'][alice_id]
        assert alice_player['name'] == "Alice"
        assert alice_player['connected'] == False
        assert alice_player['score'] == 0  # Score preserved
        assert 'socket_id' in alice_player  # Socket ID field preserved

        # Verify Bob's state unchanged
        bob_player = post_disconnect_state['players'][bob_data['player_id']]
        assert bob_player['name'] == "Bob"
        assert bob_player['connected'] == True
        assert bob_player['score'] == 0

    def test_score_state_preservation_across_disconnects(self):
        """Test that player scores are preserved across disconnect/reconnect cycles."""
        room_id = "score-preservation-room"

        # Add players with scores
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")

        alice_id = alice_data['player_id']
        bob_id = bob_data['player_id']

        # Set initial scores
        room_state = self.room_manager.get_room_state(room_id)
        room_state['players'][alice_id]['score'] = 150
        room_state['players'][bob_id]['score'] = 75

        # Verify initial scores
        assert room_state['players'][alice_id]['score'] == 150
        assert room_state['players'][bob_id]['score'] == 75

        # Disconnect Alice
        self.room_manager.disconnect_player_from_room(room_id, alice_id)

        # Verify Alice's score is preserved
        post_disconnect_state = self.room_manager.get_room_state(room_id)
        assert post_disconnect_state['players'][alice_id]['score'] == 150
        assert post_disconnect_state['players'][alice_id]['connected'] == False

        # Verify Bob's score is unchanged
        assert post_disconnect_state['players'][bob_id]['score'] == 75
        assert post_disconnect_state['players'][bob_id]['connected'] == True

        # Simulate reconnection by updating connection status
        post_disconnect_state['players'][alice_id]['connected'] = True
        post_disconnect_state['players'][alice_id]['socket_id'] = 'socket1-new'

        # Verify scores are still preserved after "reconnection"
        final_state = self.room_manager.get_room_state(room_id)
        assert final_state['players'][alice_id]['score'] == 150
        assert final_state['players'][bob_id]['score'] == 75

    def test_room_lifecycle_state_transitions(self):
        """Test room state transitions during complete disconnect scenarios."""
        room_id = "lifecycle-room"

        # State 1: Empty room (implicit - room doesn't exist)
        assert self.room_manager.get_room_state(room_id) is None

        # State 2: Single player room
        alice_data = self.room_manager.add_player_to_room(room_id, "Alice", "socket1")
        single_player_state = self.room_manager.get_room_state(room_id)
        assert len(single_player_state['players']) == 1
        assert single_player_state['game_state']['phase'] == 'waiting'

        # State 3: Multi-player room
        bob_data = self.room_manager.add_player_to_room(room_id, "Bob", "socket2")
        multi_player_state = self.room_manager.get_room_state(room_id)
        assert len(multi_player_state['players']) == 2

        # State 4: Partial disconnect (one player remains)
        self.room_manager.disconnect_player_from_room(room_id, alice_data['player_id'])
        partial_disconnect_state = self.room_manager.get_room_state(room_id)
        assert len(partial_disconnect_state['players']) == 2  # Players preserved
        connected_count = sum(1 for p in partial_disconnect_state['players'].values() if p['connected'])
        assert connected_count == 1

        # State 5: Complete disconnect (all players gone)
        self.room_manager.disconnect_player_from_room(room_id, bob_data['player_id'])
        complete_disconnect_state = self.room_manager.get_room_state(room_id)

        # Room should still exist but with no connected players
        assert complete_disconnect_state is not None
        assert len(complete_disconnect_state['players']) == 2  # Players preserved for reconnection
        connected_count = sum(1 for p in complete_disconnect_state['players'].values() if p['connected'])
        assert connected_count == 0

    def test_concurrent_disconnect_state_consistency(self):
        """Test state consistency when multiple players disconnect simultaneously."""
        room_id = "concurrent-room"

        # Add multiple players
        players = []
        for i in range(4):
            player_data = self.room_manager.add_player_to_room(room_id, f"Player{i+1}", f"socket{i+1}")
            players.append(player_data)

        # Verify initial state
        initial_state = self.room_manager.get_room_state(room_id)
        assert len(initial_state['players']) == 4
        assert sum(1 for p in initial_state['players'].values() if p['connected']) == 4

        # Simulate concurrent disconnects (Player1 and Player3)
        disconnect1 = self.room_manager.disconnect_player_from_room(room_id, players[0]['player_id'])
        disconnect3 = self.room_manager.disconnect_player_from_room(room_id, players[2]['player_id'])

        assert disconnect1 == True
        assert disconnect3 == True

        # Verify final state consistency
        final_state = self.room_manager.get_room_state(room_id)
        assert len(final_state['players']) == 4  # All players preserved

        connected_count = sum(1 for p in final_state['players'].values() if p['connected'])
        assert connected_count == 2  # Only Player2 and Player4 connected

        # Verify specific player states
        assert final_state['players'][players[0]['player_id']]['connected'] == False  # Player1
        assert final_state['players'][players[1]['player_id']]['connected'] == True   # Player2
        assert final_state['players'][players[2]['player_id']]['connected'] == False  # Player3
        assert final_state['players'][players[3]['player_id']]['connected'] == True   # Player4

        # Verify connected players list is consistent
        connected_players = self.room_manager.get_connected_players(room_id)
        connected_names = {p['name'] for p in connected_players}
        assert connected_names == {'Player2', 'Player4'}
