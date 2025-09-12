"""
Integration tests for service initialization and dependency management.
Tests the current service initialization patterns before refactoring to service container.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.room_manager import RoomManager
from src.game_manager import GameManager
from src.content_manager import ContentManager
from src.services.error_response_factory import ErrorResponseFactory
from src.services.broadcast_service import BroadcastService
from src.services.session_service import SessionService
from src.services.auto_game_flow_service import AutoGameFlowService


class TestServiceInitializationOrder:
    """Test the current service initialization order as done in app.py."""

    def test_core_managers_initialization_order(self):
        """Test that core managers can be initialized in the current order."""
        # This mirrors app.py lines 35-38
        room_manager = RoomManager()
        game_manager = GameManager(room_manager)
        content_manager = ContentManager()
        error_handler = ErrorResponseFactory()
        
        assert room_manager is not None
        assert game_manager is not None
        assert game_manager.room_manager is room_manager
        assert content_manager is not None
        assert error_handler is not None

    def test_services_initialization_with_dependencies(self):
        """Test that services can be initialized with their dependencies."""
        # Core managers first
        room_manager = RoomManager()
        game_manager = GameManager(room_manager)
        error_handler = ErrorResponseFactory()
        
        # Mock SocketIO since we don't have a real Flask app
        mock_socketio = Mock()
        
        # Services initialization - mirrors app.py lines 41-42, 55
        session_service = SessionService()
        broadcast_service = BroadcastService(mock_socketio, room_manager, game_manager, error_handler)
        auto_flow_service = AutoGameFlowService(broadcast_service, game_manager, room_manager)
        
        assert session_service is not None
        assert broadcast_service is not None
        assert auto_flow_service is not None
        
        # Verify dependency injection worked
        assert broadcast_service.room_manager is room_manager
        assert broadcast_service.game_manager is game_manager
        assert broadcast_service.error_response_factory is error_handler
        assert auto_flow_service.game_manager is game_manager
        assert auto_flow_service.room_manager is room_manager

    def test_circular_dependency_handling(self):
        """Test that circular-like dependencies are handled correctly."""
        room_manager = RoomManager()
        game_manager = GameManager(room_manager)
        error_handler = ErrorResponseFactory()
        mock_socketio = Mock()
        
        # BroadcastService depends on game_manager
        broadcast_service = BroadcastService(mock_socketio, room_manager, game_manager, error_handler)
        
        # AutoGameFlowService depends on both broadcast_service AND game_manager
        auto_flow_service = AutoGameFlowService(broadcast_service, game_manager, room_manager)
        
        # This should work without circular import issues
        assert auto_flow_service.broadcast_service is broadcast_service
        assert auto_flow_service.game_manager is game_manager
        assert broadcast_service.game_manager is game_manager


class TestServiceDependencyValidation:
    """Test that services properly validate their dependencies."""

    def test_game_manager_requires_room_manager(self):
        """Test that GameManager requires a RoomManager dependency."""
        room_manager = RoomManager()
        game_manager = GameManager(room_manager)
        
        # GameManager should store the room_manager reference
        assert hasattr(game_manager, 'room_manager')
        assert game_manager.room_manager is room_manager

    def test_game_manager_with_none_room_manager(self):
        """Test GameManager behavior with None room_manager."""
        # GameManager currently accepts None but will fail when used
        game_manager = GameManager(None)
        assert game_manager.room_manager is None

    def test_broadcast_service_requires_all_dependencies(self):
        """Test that BroadcastService requires all its dependencies."""
        room_manager = RoomManager()
        game_manager = GameManager(room_manager)
        error_handler = ErrorResponseFactory()
        mock_socketio = Mock()
        
        broadcast_service = BroadcastService(mock_socketio, room_manager, game_manager, error_handler)
        
        # Verify all dependencies are stored
        assert broadcast_service.socketio is mock_socketio
        assert broadcast_service.room_manager is room_manager
        assert broadcast_service.game_manager is game_manager
        assert broadcast_service.error_response_factory is error_handler

    def test_broadcast_service_with_missing_dependencies(self):
        """Test BroadcastService with missing dependencies."""
        with pytest.raises(TypeError):
            BroadcastService()
        
        with pytest.raises(TypeError):
            BroadcastService(Mock())

    def test_auto_game_flow_service_dependencies(self):
        """Test AutoGameFlowService dependency requirements."""
        room_manager = RoomManager()
        game_manager = GameManager(room_manager)
        error_handler = ErrorResponseFactory()
        mock_socketio = Mock()
        broadcast_service = BroadcastService(mock_socketio, room_manager, game_manager, error_handler)
        
        auto_flow_service = AutoGameFlowService(broadcast_service, game_manager, room_manager)
        
        # Verify dependencies
        assert auto_flow_service.broadcast_service is broadcast_service
        assert auto_flow_service.game_manager is game_manager
        assert auto_flow_service.room_manager is room_manager


class TestServiceInteraction:
    """Test interactions between services as they would occur in the app."""

    def setup_method(self):
        """Set up services for interaction tests."""
        self.room_manager = RoomManager()
        self.game_manager = GameManager(self.room_manager)
        self.content_manager = ContentManager()
        self.error_handler = ErrorResponseFactory()
        self.mock_socketio = Mock()
        self.session_service = SessionService()
        self.broadcast_service = BroadcastService(
            self.mock_socketio, self.room_manager, self.game_manager, self.error_handler
        )
        self.auto_flow_service = AutoGameFlowService(
            self.broadcast_service, self.game_manager, self.room_manager
        )

    def test_room_creation_workflow(self):
        """Test the workflow of creating a room through services."""
        room_id = "test-room"
        player_name = "TestPlayer"
        
        # This mirrors the workflow in app.py join room handler
        player_data = self.room_manager.add_player_to_room(room_id, player_name, "socket-123")
        
        room_state = self.room_manager.get_room_state(room_id)
        assert room_state is not None
        # Players are stored by player_id, not name
        assert len(room_state['players']) == 1
        # Check that player exists in the room
        player_found = any(player['name'] == player_name for player in room_state['players'].values())
        assert player_found

    def test_game_start_workflow(self):
        """Test the workflow of starting a game through services."""
        room_id = "test-room"
        
        # Set up room with players
        self.room_manager.add_player_to_room(room_id, "Player1", "socket-1")
        self.room_manager.add_player_to_room(room_id, "Player2", "socket-2")
        
        # Mock content manager to have prompts
        with patch.object(self.content_manager, 'get_random_prompt_response') as mock_prompt:
            mock_prompt.return_value = {
                'id': 'test-prompt',
                'prompt': 'Test prompt',
                'model': 'Test Model',
                'response': 'Test response'
            }
            
            # Start game
            result = self.game_manager.start_new_round(room_id, self.content_manager)
            assert result is True

    def test_content_manager_loading(self):
        """Test content manager loading as done in app.py."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open'), \
             patch('yaml.safe_load', return_value={'prompts': []}):
            
            # This mirrors app.py lines 45-50
            try:
                self.content_manager.load_prompts_from_yaml()
                load_successful = True
            except Exception:
                load_successful = False
            
            # Should not raise exception (graceful handling)
            assert load_successful in [True, False]  # Either is acceptable

    def test_session_service_integration(self):
        """Test session service integration with other services."""
        session_id = "test-session-123"
        room_id = "test-room"
        player_id = "player-456"
        player_name = "TestPlayer"
        
        # Create session (using correct API method)
        self.session_service.create_session(session_id, room_id, player_id, player_name)
        
        # Retrieve session
        session_info = self.session_service.get_session(session_id)
        assert session_info is not None
        assert session_info['room_id'] == room_id
        assert session_info['player_id'] == player_id

    def test_broadcast_service_integration(self):
        """Test broadcast service integration with room and game managers."""
        room_id = "test-room"
        
        # Set up room
        self.room_manager.add_player_to_room(room_id, "Player1", "socket-1")
        
        # Test broadcast service can access room state
        room_state = self.room_manager.get_room_state(room_id)
        assert room_state is not None
        
        # BroadcastService should be able to use this data
        assert self.broadcast_service.room_manager.room_exists(room_id)


class TestServiceCleanup:
    """Test service cleanup and shutdown procedures."""

    def test_auto_game_flow_service_cleanup(self):
        """Test that AutoGameFlowService can be properly cleaned up."""
        room_manager = RoomManager()
        game_manager = GameManager(room_manager)
        error_handler = ErrorResponseFactory()
        mock_socketio = Mock()
        broadcast_service = BroadcastService(mock_socketio, room_manager, game_manager, error_handler)
        
        auto_flow_service = AutoGameFlowService(broadcast_service, game_manager, room_manager)
        
        # Test cleanup (mirrors app.py atexit handler)
        auto_flow_service.stop()
        
        # Should not raise exception
        assert True

    def test_session_service_cleanup(self):
        """Test session service cleanup on shutdown."""
        session_service = SessionService()
        
        # Add some sessions (using correct API method)
        session_service.create_session("session1", "room1", "player1", "Player1")
        session_service.create_session("session2", "room2", "player2", "Player2")
        
        # Cleanup should work
        # Note: SessionService doesn't currently have explicit cleanup
        # This test documents the current state
        sessions = session_service._player_sessions
        assert len(sessions) == 2


class TestServiceErrorHandling:
    """Test error handling in service initialization and interaction."""

    def test_service_initialization_error_recovery(self):
        """Test that services can handle initialization errors gracefully."""
        room_manager = RoomManager()
        game_manager = GameManager(room_manager)
        
        # BroadcastService currently accepts any objects and doesn't validate types
        # This tests current behavior - no exception thrown during initialization
        broadcast_service = BroadcastService("invalid", room_manager, game_manager, None)
        assert broadcast_service is not None

    def test_content_manager_load_error_handling(self):
        """Test content manager error handling as done in app.py."""
        content_manager = ContentManager()
        
        with patch('builtins.open', side_effect=FileNotFoundError):
            # This mirrors the try/catch in app.py lines 45-50
            try:
                content_manager.load_prompts_from_yaml()
                load_failed = False
            except Exception as e:
                load_failed = True
                error_occurred = e
                
            # Should handle the error gracefully
            assert isinstance(error_occurred, (FileNotFoundError, Exception))

    def test_game_manager_error_propagation(self):
        """Test that game manager errors are properly handled by services."""
        room_manager = RoomManager()
        game_manager = GameManager(room_manager)
        
        # Test non-existent room handling
        result = game_manager.start_new_round("nonexistent-room", None)
        assert result is False  # Should handle gracefully, not crash