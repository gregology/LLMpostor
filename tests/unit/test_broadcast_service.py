"""
Broadcast Service Unit Tests
Tests for the centralized Socket.IO broadcasting service.
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.services.broadcast_service import BroadcastService


class TestBroadcastService:
    """Test BroadcastService functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.mock_socketio = Mock()
        self.mock_room_manager = Mock()
        self.mock_game_manager = Mock()
        self.mock_error_response_factory = Mock()
        
        # Create broadcast service (payload optimizer is now disabled by default)
        self.broadcast_service = BroadcastService(
            socketio=self.mock_socketio,
            room_manager=self.mock_room_manager,
            game_manager=self.mock_game_manager,
            error_response_factory=self.mock_error_response_factory
        )

    def test_initialization_with_optimization(self):
        """Test service initialization (optimization now disabled by default)"""
        service = BroadcastService(
            socketio=self.mock_socketio,
            room_manager=self.mock_room_manager,
            game_manager=self.mock_game_manager,
            error_response_factory=self.mock_error_response_factory
        )
        # Payload optimization feature has been removed from the codebase
        assert not hasattr(service, 'optimization_enabled')
        assert not hasattr(service, 'payload_optimizer')

    def test_initialization_without_optimization(self):
        """Test service initialization without optimization (default behavior now)"""
        service = BroadcastService(
            socketio=self.mock_socketio,
            room_manager=self.mock_room_manager,
            game_manager=self.mock_game_manager,
            error_response_factory=self.mock_error_response_factory
        )
        # Payload optimization feature has been removed from the codebase
        assert not hasattr(service, 'optimization_enabled')
        assert not hasattr(service, 'payload_optimizer')

    def test_emit_to_room_success(self):
        """Test successful emission to room"""
        event = "test_event"
        data = {"message": "test"}
        room_id = "room123"
        
        self.broadcast_service.emit_to_room(event, data, room_id)
        
        self.mock_socketio.emit.assert_called_once_with(event, data, room=room_id)

    def test_emit_to_room_handles_exception(self):
        """Test emit_to_room handles socketio exceptions gracefully"""
        self.mock_socketio.emit.side_effect = Exception("Socket error")
        
        # Should not raise exception
        self.broadcast_service.emit_to_room("test", {}, "room123")
        
        self.mock_socketio.emit.assert_called_once()

    def test_emit_to_player_success(self):
        """Test successful emission to specific player"""
        event = "player_event"
        data = {"action": "kick"}
        socket_id = "socket456"
        
        self.broadcast_service.emit_to_player(event, data, socket_id)
        
        self.mock_socketio.emit.assert_called_once_with(event, data, room=socket_id)

    def test_emit_to_player_handles_exception(self):
        """Test emit_to_player handles socketio exceptions gracefully"""
        self.mock_socketio.emit.side_effect = Exception("Socket error")
        
        # Should not raise exception
        self.broadcast_service.emit_to_player("test", {}, "socket123")
        
        self.mock_socketio.emit.assert_called_once()

    def test_emit_error_to_player_success(self):
        """Test successful error emission to player"""
        error_response = {"error_code": "INVALID_ACTION", "message": "Invalid action"}
        socket_id = "socket789"
        
        self.broadcast_service.emit_error_to_player(error_response, socket_id)
        
        self.mock_socketio.emit.assert_called_once_with('error', error_response, room=socket_id)

    def test_emit_error_to_player_handles_exception(self):
        """Test emit_error_to_player handles socketio exceptions gracefully"""
        self.mock_socketio.emit.side_effect = Exception("Socket error")
        
        # Should not raise exception
        self.broadcast_service.emit_error_to_player({"error_code": "TEST"}, "socket123")
        
        self.mock_socketio.emit.assert_called_once()

    def test_broadcast_player_list_update_success(self):
        """Test successful player list broadcast"""
        room_id = "room123"
        
        # Mock room state
        room_state = {
            'players': {
                'player1': {
                    'player_id': 'player1',
                    'name': 'Alice',
                    'score': 100,
                    'connected': True
                },
                'player2': {
                    'player_id': 'player2',
                    'name': 'Bob',
                    'score': 50,
                    'connected': False
                }
            }
        }
        
        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_room_manager.get_connected_players.return_value = ['player1']
        
        self.broadcast_service.broadcast_player_list_update(room_id)
        
        # Verify emit was called with correct data structure
        self.mock_socketio.emit.assert_called_once()
        call_args = self.mock_socketio.emit.call_args
        
        assert call_args[0][0] == 'player_list_updated'  # event name
        assert call_args[1]['room'] == room_id
        
        # Check payload structure
        payload = call_args[0][1]
        assert 'players' in payload
        assert 'connected_count' in payload
        assert 'total_count' in payload
        assert len(payload['players']) == 2
        assert payload['connected_count'] == 1
        assert payload['total_count'] == 2

    def test_broadcast_player_list_update_no_room(self):
        """Test player list broadcast when room doesn't exist"""
        self.mock_room_manager.get_room_state.return_value = None
        
        self.broadcast_service.broadcast_player_list_update("nonexistent")
        
        # Should not emit anything
        self.mock_socketio.emit.assert_not_called()

    def test_broadcast_player_list_update_handles_exception(self):
        """Test player list broadcast handles exceptions gracefully"""
        self.mock_room_manager.get_room_state.side_effect = Exception("Room error")
        
        # Should not raise exception
        self.broadcast_service.broadcast_player_list_update("room123")

    def test_broadcast_room_state_update_waiting_phase(self):
        """Test room state broadcast in waiting phase"""
        room_id = "room123"
        mock_datetime = datetime(2023, 1, 1, 12, 0, 0)
        
        room_state = {
            'players': {},
            'game_state': {
                'phase': 'waiting',
                'round_number': 0,
                'phase_start_time': mock_datetime,
                'phase_duration': 30,
                'current_prompt': None,
                'responses': [],
                'guesses': {}
            }
        }
        
        self.mock_room_manager.get_room_state.return_value = room_state
        
        self.broadcast_service.broadcast_room_state_update(room_id)
        
        # Verify emit was called
        self.mock_socketio.emit.assert_called_once()
        call_args = self.mock_socketio.emit.call_args
        
        assert call_args[0][0] == 'room_state_updated'
        payload = call_args[0][1]
        
        # Check basic state structure
        assert payload['phase'] == 'waiting'
        assert payload['round_number'] == 0
        assert payload['phase_start_time'] == mock_datetime.isoformat()
        assert payload['phase_duration'] == 30

    def test_broadcast_room_state_update_responding_phase(self):
        """Test room state broadcast in responding phase"""
        room_id = "room123"
        mock_datetime = datetime(2023, 1, 1, 12, 0, 0)
        
        room_state = {
            'players': {},
            'game_state': {
                'phase': 'responding',
                'round_number': 1,
                'phase_start_time': mock_datetime,
                'phase_duration': 120,
                'current_prompt': {
                    'id': 'prompt1',
                    'prompt': 'Test prompt',
                    'model': 'gpt-4',
                    'ai_response': 'Secret AI response'  # Should be filtered out
                },
                'responses': [{'text': 'Response 1'}, {'text': 'Response 2'}],
                'guesses': {}
            }
        }
        
        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_game_manager.get_phase_time_remaining.return_value = 90
        
        self.broadcast_service.broadcast_room_state_update(room_id)
        
        call_args = self.mock_socketio.emit.call_args
        payload = call_args[0][1]
        
        # Check responding phase specific data
        assert payload['phase'] == 'responding'
        assert 'current_prompt' in payload
        assert payload['current_prompt']['prompt'] == 'Test prompt'
        assert 'ai_response' not in payload['current_prompt']  # Should be filtered
        assert payload['response_count'] == 2
        assert payload['time_remaining'] == 90

    def test_broadcast_room_state_update_guessing_phase(self):
        """Test room state broadcast in guessing phase"""
        room_id = "room123"
        mock_datetime = datetime(2023, 1, 1, 12, 0, 0)
        
        room_state = {
            'players': {},
            'game_state': {
                'phase': 'guessing',
                'round_number': 1,
                'phase_start_time': mock_datetime,
                'phase_duration': 60,
                'current_prompt': {
                    'id': 'prompt1',
                    'prompt': 'Test prompt',
                    'model': 'gpt-4'
                },
                'responses': [
                    {'text': 'Response 1', 'player_id': 'player1'},
                    {'text': 'Response 2', 'player_id': 'player2'}
                ],
                'guesses': {'player1': 0}
            }
        }
        
        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_game_manager.get_phase_time_remaining.return_value = 45
        
        self.broadcast_service.broadcast_room_state_update(room_id)
        
        call_args = self.mock_socketio.emit.call_args
        payload = call_args[0][1]
        
        # Check guessing phase specific data
        assert payload['phase'] == 'guessing'
        assert 'responses' in payload
        assert len(payload['responses']) == 2
        assert payload['responses'][0]['index'] == 0
        assert payload['responses'][0]['text'] == 'Response 1'
        assert 'player_id' not in payload['responses'][0]  # Should be filtered
        assert payload['guess_count'] == 1
        assert payload['time_remaining'] == 45

    def test_broadcast_room_state_update_no_room(self):
        """Test room state broadcast when room doesn't exist"""
        self.mock_room_manager.get_room_state.return_value = None
        
        self.broadcast_service.broadcast_room_state_update("nonexistent")
        
        # Should not emit anything
        self.mock_socketio.emit.assert_not_called()

    def test_broadcast_room_state_update_handles_exception(self):
        """Test room state broadcast handles exceptions gracefully"""
        self.mock_room_manager.get_room_state.side_effect = Exception("Room error")
        
        # Should not raise exception
        self.broadcast_service.broadcast_room_state_update("room123")

    def test_broadcast_room_state_update_none_phase_start_time(self):
        """Test room state broadcast handles None phase_start_time"""
        room_id = "room123"
        
        room_state = {
            'players': {},
            'game_state': {
                'phase': 'waiting',
                'round_number': 0,
                'phase_start_time': None,  # None case
                'phase_duration': 30,
                'current_prompt': None,
                'responses': [],
                'guesses': {}
            }
        }
        
        self.mock_room_manager.get_room_state.return_value = room_state
        
        self.broadcast_service.broadcast_room_state_update(room_id)
        
        call_args = self.mock_socketio.emit.call_args
        payload = call_args[0][1]
        
        assert payload['phase_start_time'] is None


class TestBroadcastServiceEdgeCases:
    """Test edge cases and error scenarios"""

    def setup_method(self):
        """Setup test fixtures for edge case tests"""
        self.mock_socketio = Mock()
        self.mock_room_manager = Mock()
        self.mock_game_manager = Mock()
        self.mock_error_response_factory = Mock()
        
        # Create broadcast service (payload optimizer is now disabled by default)
        self.broadcast_service = BroadcastService(
            socketio=self.mock_socketio,
            room_manager=self.mock_room_manager,
            game_manager=self.mock_game_manager,
            error_response_factory=self.mock_error_response_factory
        )

    def test_broadcast_with_empty_players(self):
        """Test broadcast with empty player list"""
        room_state = {
            'players': {},  # Empty players dict
        }
        
        self.mock_room_manager.get_room_state.return_value = room_state
        self.mock_room_manager.get_connected_players.return_value = []
        
        self.broadcast_service.broadcast_player_list_update("room123")
        
        call_args = self.mock_socketio.emit.call_args
        payload = call_args[0][1]
        
        assert len(payload['players']) == 0
        assert payload['connected_count'] == 0
        assert payload['total_count'] == 0

    def test_broadcast_with_malformed_room_state(self):
        """Test broadcast handles malformed room state gracefully"""
        # Missing required keys
        room_state = {
            'game_state': {
                'phase': 'waiting'
                # Missing other required keys
            }
        }
        
        self.mock_room_manager.get_room_state.return_value = room_state
        
        # Should not raise KeyError
        self.broadcast_service.broadcast_room_state_update("room123")

    def test_emit_with_none_data(self):
        """Test emission with None data"""
        self.broadcast_service.emit_to_room("test", None, "room123")
        
        self.mock_socketio.emit.assert_called_once_with("test", None, room="room123")

    def test_emit_with_large_payload(self):
        """Test emission with large payload data"""
        large_data = {"message": "x" * 10000}  # Large payload
        
        self.broadcast_service.emit_to_room("test", large_data, "room123")
        
        # Should still emit successfully
        self.mock_socketio.emit.assert_called_once()