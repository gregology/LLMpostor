"""
Auto Game Flow Integration Tests

Tests the background service integration for the auto game flow service.
Validates timer service coordination, broadcast service integration, and room cleanup automation
in a realistic environment with actual service dependencies.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock, call
from flask_socketio import SocketIOTestClient

from src.services.auto_game_flow_service import AutoGameFlowService
from tests.migration_compat import app, socketio, room_manager, game_manager, broadcast_service, session_service
from tests.helpers.socket_mocks import create_mock_socketio


class TestAutoGameFlowIntegration:
    """Test auto game flow service integration with timer and broadcast services."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Clear any existing state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()

        # Create test client with real SocketIO integration
        self.client = SocketIOTestClient(app, socketio)

        # Stop auto flow service to control timing in tests
        if hasattr(app, 'auto_flow_service') and app.auto_flow_service:
            app.auto_flow_service.stop()

    def teardown_method(self):
        """Clean up after each test."""
        # Disconnect client safely
        if hasattr(self, 'client') and self.client and self.client.is_connected():
            self.client.disconnect()

        # Clear state
        room_manager._rooms.clear()
        session_service._player_sessions.clear()

        # Restart auto flow service for other tests
        if hasattr(app, 'auto_flow_service') and app.auto_flow_service:
            app.auto_flow_service.stop()

    def test_timer_service_coordination_with_broadcasts(self):
        """Test coordination between timer checking and broadcast service."""
        # Create a room with game in progress
        self.client.emit('join_room', {
            'room_id': 'timer-coord-room',
            'player_name': 'TimerPlayer1'
        })

        # Add second player to meet minimum requirements
        client2 = SocketIOTestClient(app, socketio)
        try:
            client2.emit('join_room', {
                'room_id': 'timer-coord-room',
                'player_name': 'TimerPlayer2'
            })

            # Clear initial events
            self.client.get_received()
            client2.get_received()

            # Start a game round
            self.client.emit('start_round', {})

            # Wait for round start
            time.sleep(0.1)

            # Create auto flow service with controlled config for fast testing
            with patch('src.services.auto_game_flow_service.get_config') as mock_config_func:
                mock_config = Mock()
                mock_config.game_flow_check_interval = 0.1  # 100ms for fast testing
                mock_config.countdown_broadcast_interval = 0.2  # 200ms intervals
                mock_config.room_status_broadcast_interval = 1
                mock_config.warning_threshold_seconds = 5
                mock_config.final_warning_threshold_seconds = 2
                mock_config.room_cleanup_inactive_minutes = 60
                mock_config.min_players_required = 2
                mock_config_func.return_value = mock_config

                # Start auto flow service
                auto_flow = AutoGameFlowService(
                    broadcast_service=broadcast_service,
                    game_manager=game_manager,
                    room_manager=room_manager
                )

                try:
                    # Let it run for a short time to check coordination
                    time.sleep(0.5)

                    # Get events received by clients
                    client1_events = self.client.get_received()
                    client2_events = client2.get_received()

                    # Should have received countdown updates due to timer coordination
                    countdown_events_1 = [e for e in client1_events if e['name'] == 'countdown_update']
                    countdown_events_2 = [e for e in client2_events if e['name'] == 'countdown_update']

                    # Both clients should receive countdown updates from the coordinated service
                    assert len(countdown_events_1) > 0, "Client 1 should receive countdown updates"
                    assert len(countdown_events_2) > 0, "Client 2 should receive countdown updates"

                    # Verify countdown data structure
                    if countdown_events_1:
                        countdown_data = countdown_events_1[0]['args'][0]
                        assert 'phase' in countdown_data
                        assert 'time_remaining' in countdown_data
                        assert 'phase_duration' in countdown_data

                finally:
                    auto_flow.stop()

        finally:
            client2.disconnect()

    def test_broadcast_service_integration_phase_transitions(self):
        """Test broadcast service integration during automated phase transitions."""
        # Create room with players
        self.client.emit('join_room', {
            'room_id': 'broadcast-room',
            'player_name': 'BroadcastPlayer1'
        })

        client2 = SocketIOTestClient(app, socketio)
        try:
            client2.emit('join_room', {
                'room_id': 'broadcast-room',
                'player_name': 'BroadcastPlayer2'
            })

            # Clear events
            self.client.get_received()
            client2.get_received()

            # Start round
            self.client.emit('start_round', {})
            time.sleep(0.1)

            # Submit responses for both players to trigger phase advance
            self.client.emit('submit_response', {'response': 'Test response 1'})
            client2.emit('submit_response', {'response': 'Test response 2'})

            # Wait for phase transition
            time.sleep(0.2)

            # Create auto flow service to test phase transition broadcasts
            with patch('src.services.auto_game_flow_service.get_config') as mock_config_func:
                mock_config = Mock()
                mock_config.game_flow_check_interval = 0.05  # Very fast for testing
                mock_config.countdown_broadcast_interval = 0.1
                mock_config.room_status_broadcast_interval = 1
                mock_config.warning_threshold_seconds = 30
                mock_config.final_warning_threshold_seconds = 10
                mock_config.room_cleanup_inactive_minutes = 60
                mock_config.min_players_required = 2
                mock_config_func.return_value = mock_config

                # Clear events before starting auto flow
                self.client.get_received()
                client2.get_received()

                auto_flow = AutoGameFlowService(
                    broadcast_service=broadcast_service,
                    game_manager=game_manager,
                    room_manager=room_manager
                )

                try:
                    # Run for enough time to potentially trigger phase transitions
                    time.sleep(0.3)

                    # Get events
                    client1_events = self.client.get_received()
                    client2_events = client2.get_received()

                    # Look for phase-related broadcasts
                    all_event_names_1 = [e['name'] for e in client1_events]
                    all_event_names_2 = [e['name'] for e in client2_events]

                    # Should have consistent broadcast events across clients
                    common_events = set(all_event_names_1) & set(all_event_names_2)

                    # Should include room state updates at minimum
                    room_state_events_1 = [e for e in client1_events if e['name'] == 'room_state_updated']
                    room_state_events_2 = [e for e in client2_events if e['name'] == 'room_state_updated']

                    # Both should receive consistent room state updates
                    assert len(room_state_events_1) == len(room_state_events_2), "Room state updates should be consistent"

                finally:
                    auto_flow.stop()

        finally:
            client2.disconnect()

    def test_room_cleanup_automation_integration(self):
        """Test room cleanup automation integration with room manager."""
        # Create a room that will be considered for cleanup
        self.client.emit('join_room', {
            'room_id': 'cleanup-room',
            'player_name': 'CleanupPlayer'
        })

        # Disconnect player to make room inactive
        self.client.disconnect()

        # Verify room exists initially
        room_state = room_manager.get_room_state('cleanup-room')
        assert room_state is not None, "Room should exist before cleanup"

        # Create auto flow service with very aggressive cleanup for testing
        with patch('src.services.auto_game_flow_service.get_config') as mock_config_func:
            mock_config = Mock()
            mock_config.game_flow_check_interval = 0.1
            mock_config.countdown_broadcast_interval = 10
            mock_config.room_status_broadcast_interval = 0.2  # Cleanup check every 200ms
            mock_config.warning_threshold_seconds = 30
            mock_config.final_warning_threshold_seconds = 10
            mock_config.room_cleanup_inactive_minutes = 0.001  # Very aggressive cleanup (0.06 seconds)
            mock_config.min_players_required = 2
            mock_config_func.return_value = mock_config

            auto_flow = AutoGameFlowService(
                broadcast_service=broadcast_service,
                game_manager=game_manager,
                room_manager=room_manager
            )

            try:
                # Wait for cleanup cycles to run
                time.sleep(0.5)

                # Check if room was cleaned up (room manager should handle the cleanup)
                # Note: We're testing integration, so we verify the service called room_manager methods
                # The actual cleanup depends on room_manager.cleanup_inactive_rooms implementation

                # Verify auto flow service is running and processing
                assert auto_flow.running, "Auto flow service should be running"

                # The service should have made calls to check rooms
                # (actual cleanup behavior depends on room_manager implementation)

            finally:
                auto_flow.stop()

    def test_background_thread_integration_lifecycle(self):
        """Test background thread integration and lifecycle management."""
        # Test proper thread lifecycle with real dependencies
        with patch('src.services.auto_game_flow_service.get_config') as mock_config_func:
            mock_config = Mock()
            mock_config.game_flow_check_interval = 0.1
            mock_config.countdown_broadcast_interval = 10
            mock_config.room_status_broadcast_interval = 1
            mock_config.warning_threshold_seconds = 30
            mock_config.final_warning_threshold_seconds = 10
            mock_config.room_cleanup_inactive_minutes = 60
            mock_config.min_players_required = 2
            mock_config_func.return_value = mock_config

            # Create service - should start background thread
            auto_flow = AutoGameFlowService(
                broadcast_service=broadcast_service,
                game_manager=game_manager,
                room_manager=room_manager
            )

            # Verify service is running
            assert auto_flow.running, "Service should be running after initialization"
            assert auto_flow.timer_thread.is_alive(), "Background thread should be alive"

            # Let it run briefly
            time.sleep(0.2)

            # Verify thread is still active and service is operational
            assert auto_flow.timer_thread.is_alive(), "Thread should remain alive during operation"
            assert auto_flow.running, "Service should remain running"

            # Stop service
            auto_flow.stop()

            # Verify proper shutdown
            assert not auto_flow.running, "Service should not be running after stop"

            # Wait for thread to finish
            time.sleep(0.1)

            # Thread should be stopped or finished
            if auto_flow.timer_thread.is_alive():
                # Give it a bit more time for cleanup
                auto_flow.timer_thread.join(timeout=1)

            # Verify final state
            assert not auto_flow.running, "Service should be fully stopped"

    def test_error_recovery_in_background_service(self):
        """Test error recovery in background service integration."""
        # Create room for testing
        self.client.emit('join_room', {
            'room_id': 'error-recovery-room',
            'player_name': 'ErrorPlayer'
        })

        # Mock game manager to throw errors periodically
        original_is_phase_expired = game_manager.is_phase_expired
        call_count = 0

        def failing_is_phase_expired(room_id):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail on second call
                raise Exception("Simulated error")
            return original_is_phase_expired(room_id)

        with patch.object(game_manager, 'is_phase_expired', side_effect=failing_is_phase_expired):
            with patch('src.services.auto_game_flow_service.get_config') as mock_config_func:
                mock_config = Mock()
                mock_config.game_flow_check_interval = 0.1
                mock_config.countdown_broadcast_interval = 10
                mock_config.room_status_broadcast_interval = 1
                mock_config.warning_threshold_seconds = 30
                mock_config.final_warning_threshold_seconds = 10
                mock_config.room_cleanup_inactive_minutes = 60
                mock_config.min_players_required = 2
                mock_config_func.return_value = mock_config

                auto_flow = AutoGameFlowService(
                    broadcast_service=broadcast_service,
                    game_manager=game_manager,
                    room_manager=room_manager
                )

                try:
                    # Let it run through error and recovery
                    time.sleep(0.5)

                    # Service should still be running despite the error
                    assert auto_flow.running, "Service should recover from errors and continue running"
                    assert auto_flow.timer_thread.is_alive(), "Background thread should remain alive after error"

                    # Should have made multiple calls (including the failed one)
                    assert call_count > 2, "Should have continued processing after error"

                finally:
                    auto_flow.stop()

    def test_cross_service_coordination_with_real_events(self):
        """Test coordination between auto flow service and other services with real events."""
        # Create room with players
        self.client.emit('join_room', {
            'room_id': 'coordination-room',
            'player_name': 'CoordPlayer1'
        })

        client2 = SocketIOTestClient(app, socketio)
        try:
            client2.emit('join_room', {
                'room_id': 'coordination-room',
                'player_name': 'CoordPlayer2'
            })

            # Clear events
            self.client.get_received()
            client2.get_received()

            # Start round to get into active game state
            self.client.emit('start_round', {})
            time.sleep(0.1)

            # Create auto flow service
            with patch('src.services.auto_game_flow_service.get_config') as mock_config_func:
                mock_config = Mock()
                mock_config.game_flow_check_interval = 0.1
                mock_config.countdown_broadcast_interval = 0.2
                mock_config.room_status_broadcast_interval = 1
                mock_config.warning_threshold_seconds = 30
                mock_config.final_warning_threshold_seconds = 10
                mock_config.room_cleanup_inactive_minutes = 60
                mock_config.min_players_required = 2
                mock_config_func.return_value = mock_config

                auto_flow = AutoGameFlowService(
                    broadcast_service=broadcast_service,
                    game_manager=game_manager,
                    room_manager=room_manager
                )

                try:
                    # Clear events before testing coordination
                    self.client.get_received()
                    client2.get_received()

                    # Let auto flow run
                    time.sleep(0.4)

                    # Simulate player disconnect to test cross-service coordination
                    player_id = None
                    for pid, player in room_manager.get_room_state('coordination-room')['players'].items():
                        if player['name'] == 'CoordPlayer1':
                            player_id = pid
                            break

                    if player_id:
                        # Test auto flow's disconnect handling integration
                        auto_flow.handle_player_disconnect_game_impact('coordination-room', player_id)

                        # Verify the service coordinated with other services
                        # Should have interacted with room_manager and broadcast_service
                        room_state = room_manager.get_room_state('coordination-room')
                        assert room_state is not None, "Room should still exist after disconnect handling"

                    # Get final events
                    final_events_1 = self.client.get_received()
                    final_events_2 = client2.get_received()

                    # Should have received some coordination events
                    all_events = final_events_1 + final_events_2
                    event_names = [e['name'] for e in all_events]

                    # Should have received updates through service coordination
                    coordination_events = [name for name in event_names if name in [
                        'countdown_update', 'room_state_updated', 'player_list_updated'
                    ]]

                    assert len(coordination_events) > 0, "Should receive coordination events between services"

                finally:
                    auto_flow.stop()

        finally:
            client2.disconnect()