"""
Base Handler Unit Tests

Tests for the base handler classes including BaseHandler, BaseRoomHandler, BaseGameHandler,
and all mixin classes with comprehensive coverage of initialization, validation, and response patterns.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from flask import Flask
from flask_socketio import SocketIO

from src.handlers.base_handler import (
    BaseHandler,
    BaseRoomHandler,
    BaseGameHandler,
    BaseInfoHandler,
    RoomHandlerMixin,
    GameHandlerMixin,
    ValidationHandlerMixin
)
from src.core.errors import ErrorCode, ValidationError


class ConcreteBaseHandler(BaseHandler):
    """Concrete implementation of BaseHandler for testing."""
    pass


class ConcreteRoomHandler(BaseRoomHandler):
    """Concrete implementation of BaseRoomHandler for testing."""
    pass


class ConcreteGameHandler(BaseGameHandler):
    """Concrete implementation of BaseGameHandler for testing."""
    pass


class TestBaseHandlerInitialization:
    """Test BaseHandler initialization and service access properties"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        # Mock the container
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = ConcreteBaseHandler()

    def test_initialization(self):
        """Test BaseHandler initialization"""
        assert self.handler._container is self.mock_container

    def test_room_manager_property(self):
        """Test room_manager property accessor"""
        mock_room_manager = Mock()
        self.mock_container.get.return_value = mock_room_manager

        result = self.handler.room_manager

        self.mock_container.get.assert_called_once_with('RoomManager')
        assert result is mock_room_manager

    def test_game_manager_property(self):
        """Test game_manager property accessor"""
        mock_game_manager = Mock()
        self.mock_container.get.return_value = mock_game_manager

        result = self.handler.game_manager

        self.mock_container.get.assert_called_once_with('GameManager')
        assert result is mock_game_manager

    def test_content_manager_property(self):
        """Test content_manager property accessor"""
        mock_content_manager = Mock()
        self.mock_container.get.return_value = mock_content_manager

        result = self.handler.content_manager

        self.mock_container.get.assert_called_once_with('ContentManager')
        assert result is mock_content_manager

    def test_validation_service_property(self):
        """Test validation_service property accessor"""
        mock_validation_service = Mock()
        self.mock_container.get.return_value = mock_validation_service

        result = self.handler.validation_service

        self.mock_container.get.assert_called_once_with('ValidationService')
        assert result is mock_validation_service

    def test_error_response_factory_property(self):
        """Test error_response_factory property accessor"""
        mock_error_factory = Mock()
        self.mock_container.get.return_value = mock_error_factory

        result = self.handler.error_response_factory

        self.mock_container.get.assert_called_once_with('ErrorResponseFactory')
        assert result is mock_error_factory

    def test_session_service_property(self):
        """Test session_service property accessor"""
        mock_session_service = Mock()
        self.mock_container.get.return_value = mock_session_service

        result = self.handler.session_service

        self.mock_container.get.assert_called_once_with('SessionService')
        assert result is mock_session_service

    def test_broadcast_service_property(self):
        """Test broadcast_service property accessor"""
        mock_broadcast_service = Mock()
        self.mock_container.get.return_value = mock_broadcast_service

        result = self.handler.broadcast_service

        self.mock_container.get.assert_called_once_with('BroadcastService')
        assert result is mock_broadcast_service

    def test_auto_flow_service_property(self):
        """Test auto_flow_service property accessor"""
        mock_auto_flow = Mock()
        self.mock_container.get.return_value = mock_auto_flow

        result = self.handler.auto_flow_service

        self.mock_container.get.assert_called_once_with('AutoGameFlowService')
        assert result is mock_auto_flow

    def test_app_config_property(self):
        """Test app_config property accessor"""
        mock_config = Mock()
        self.mock_container.get_config.return_value = mock_config

        result = self.handler.app_config

        self.mock_container.get_config.assert_called_once_with('app_config')
        assert result is mock_config


class TestBaseHandlerSessionManagement:
    """Test BaseHandler session management methods"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = ConcreteBaseHandler()

        # Mock session service
        self.mock_session_service = Mock()
        self.mock_container.get.return_value = self.mock_session_service

        # Mock Flask request
        self.mock_request = Mock()
        self.mock_request.sid = "test_socket_123"

    def test_get_current_session_success(self):
        """Test getting current session successfully"""
        mock_session = {"room_id": "test_room", "player_name": "test_player"}
        self.mock_session_service.get_session.return_value = mock_session

        with patch('src.handlers.base_handler.request', self.mock_request):
            result = self.handler.get_current_session()

        self.mock_session_service.get_session.assert_called_once_with("test_socket_123")
        assert result == mock_session

    def test_get_current_session_none(self):
        """Test getting current session when none exists"""
        self.mock_session_service.get_session.return_value = None

        with patch('src.handlers.base_handler.request', self.mock_request):
            result = self.handler.get_current_session()

        assert result is None

    def test_require_session_success(self):
        """Test requiring session when session exists"""
        mock_session = {"room_id": "test_room", "player_name": "test_player"}
        self.mock_session_service.get_session.return_value = mock_session

        with patch('src.handlers.base_handler.request', self.mock_request):
            result = self.handler.require_session()

        assert result == mock_session

    def test_require_session_failure(self):
        """Test requiring session when no session exists"""
        self.mock_session_service.get_session.return_value = None

        with patch('src.handlers.base_handler.request', self.mock_request):
            with pytest.raises(ValidationError) as exc_info:
                self.handler.require_session()

        assert exc_info.value.code == ErrorCode.NOT_IN_ROOM
        assert exc_info.value.message == 'You are not currently in a room'


class TestBaseHandlerDataValidation:
    """Test BaseHandler data validation methods"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = ConcreteBaseHandler()

    def test_validate_data_dict_success(self):
        """Test successful data dictionary validation"""
        test_data = {"room_id": "test_room", "player_name": "test_player"}
        required_fields = ["room_id", "player_name"]

        result = self.handler.validate_data_dict(test_data, required_fields)

        assert result == test_data

    def test_validate_data_dict_not_dict(self):
        """Test validation failure when data is not a dictionary"""
        test_data = "not_a_dict"

        with pytest.raises(ValidationError) as exc_info:
            self.handler.validate_data_dict(test_data)

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Invalid data format - expected dictionary" in exc_info.value.message

    def test_validate_data_dict_missing_room_id(self):
        """Test validation failure when room_id is missing"""
        test_data = {"player_name": "test_player"}
        required_fields = ["room_id", "player_name"]

        with pytest.raises(ValidationError) as exc_info:
            self.handler.validate_data_dict(test_data, required_fields)

        assert exc_info.value.code == ErrorCode.MISSING_ROOM_ID
        assert exc_info.value.message == "Room ID is required"

    def test_validate_data_dict_missing_player_name(self):
        """Test validation failure when player_name is missing"""
        test_data = {"room_id": "test_room"}
        required_fields = ["room_id", "player_name"]

        with pytest.raises(ValidationError) as exc_info:
            self.handler.validate_data_dict(test_data, required_fields)

        assert exc_info.value.code == ErrorCode.MISSING_PLAYER_NAME
        assert exc_info.value.message == "Player name is required"

    def test_validate_data_dict_missing_response(self):
        """Test validation failure when response is missing"""
        test_data = {"room_id": "test_room"}
        required_fields = ["response"]

        with pytest.raises(ValidationError) as exc_info:
            self.handler.validate_data_dict(test_data, required_fields)

        assert exc_info.value.code == ErrorCode.EMPTY_RESPONSE
        assert exc_info.value.message == "Response is required"

    def test_validate_data_dict_missing_guess_index(self):
        """Test validation failure when guess_index is missing"""
        test_data = {"room_id": "test_room"}
        required_fields = ["guess_index"]

        with pytest.raises(ValidationError) as exc_info:
            self.handler.validate_data_dict(test_data, required_fields)

        assert exc_info.value.code == ErrorCode.MISSING_GUESS
        assert exc_info.value.message == "Guess index is required"

    def test_validate_data_dict_missing_generic_field(self):
        """Test validation failure for generic missing field"""
        test_data = {"room_id": "test_room"}
        required_fields = ["custom_field"]

        with pytest.raises(ValidationError) as exc_info:
            self.handler.validate_data_dict(test_data, required_fields)

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert exc_info.value.message == "Missing required field: custom_field"

    def test_validate_data_dict_no_required_fields(self):
        """Test validation when no required fields specified"""
        test_data = {"any_field": "any_value"}

        result = self.handler.validate_data_dict(test_data)

        assert result == test_data

    def test_validate_data_dict_empty_required_fields(self):
        """Test validation with empty required fields list"""
        test_data = {"any_field": "any_value"}

        result = self.handler.validate_data_dict(test_data, [])

        assert result == test_data


class TestBaseHandlerResponseMethods:
    """Test BaseHandler response emission methods"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = ConcreteBaseHandler()

        # Mock error response factory
        self.mock_error_factory = Mock()
        self.mock_container.get.return_value = self.mock_error_factory

    def test_emit_success(self):
        """Test emitting success response"""
        test_data = {"result": "success"}
        mock_response = {"success": True, "data": test_data}
        self.mock_error_factory.create_success_response.return_value = mock_response

        with patch('src.handlers.base_handler.emit') as mock_emit:
            self.handler.emit_success("test_event", test_data)

        self.mock_error_factory.create_success_response.assert_called_once_with(test_data)
        mock_emit.assert_called_once_with("test_event", mock_response)

    def test_emit_success_no_data(self):
        """Test emitting success response with no data"""
        mock_response = {"success": True, "data": {}}
        self.mock_error_factory.create_success_response.return_value = mock_response

        with patch('src.handlers.base_handler.emit') as mock_emit:
            self.handler.emit_success("test_event")

        self.mock_error_factory.create_success_response.assert_called_once_with({})
        mock_emit.assert_called_once_with("test_event", mock_response)

    def test_emit_error(self):
        """Test emitting error response"""
        error_code = ErrorCode.INVALID_DATA
        error_message = "Test error message"
        mock_response = {"success": False, "error": {"code": error_code, "message": error_message}}
        self.mock_error_factory.create_error_response.return_value = mock_response

        with patch('src.handlers.base_handler.emit') as mock_emit:
            self.handler.emit_error("test_event", error_code, error_message)

        self.mock_error_factory.create_error_response.assert_called_once_with(error_code, error_message)
        mock_emit.assert_called_once_with("test_event", mock_response)


class TestBaseHandlerLogging:
    """Test BaseHandler logging methods"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = ConcreteBaseHandler()

        # Mock Flask request
        self.mock_request = Mock()
        self.mock_request.sid = "test_socket_456"

    def test_log_handler_start(self):
        """Test logging handler start"""
        with patch('src.handlers.base_handler.request', self.mock_request), \
             patch('src.handlers.base_handler.logger') as mock_logger:

            self.handler.log_handler_start("test_handler")

        mock_logger.info.assert_called_once_with('test_handler called by client: test_socket_456')

    def test_log_handler_start_with_data(self):
        """Test logging handler start with data"""
        test_data = {"test": "data"}

        with patch('src.handlers.base_handler.request', self.mock_request), \
             patch('src.handlers.base_handler.logger') as mock_logger:

            self.handler.log_handler_start("test_handler", test_data)

        mock_logger.info.assert_called_once_with('test_handler called by client: test_socket_456')
        mock_logger.debug.assert_called_once_with("test_handler data: {'test': 'data'}")

    def test_log_handler_success(self):
        """Test logging handler success"""
        with patch('src.handlers.base_handler.request', self.mock_request), \
             patch('src.handlers.base_handler.logger') as mock_logger:

            self.handler.log_handler_success("test_handler")

        mock_logger.info.assert_called_once_with(
            'test_handler completed successfully for client: test_socket_456'
        )

    def test_log_handler_success_with_message(self):
        """Test logging handler success with message"""
        success_message = "Operation completed"

        with patch('src.handlers.base_handler.request', self.mock_request), \
             patch('src.handlers.base_handler.logger') as mock_logger:

            self.handler.log_handler_success("test_handler", success_message)

        mock_logger.info.assert_called_once_with(
            'test_handler completed successfully for client: test_socket_456 - Operation completed'
        )


class TestRoomHandlerMixin:
    """Test RoomHandlerMixin functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        # Create a test class that inherits from RoomHandlerMixin
        class TestRoomMixin(RoomHandlerMixin):
            pass

        self.mixin = TestRoomMixin()

        # Mock Flask request
        self.mock_request = Mock()
        self.mock_request.sid = "test_socket_789"

    def test_join_socketio_room(self):
        """Test joining Socket.IO room"""
        room_id = "test_room_123"

        with patch('src.handlers.base_handler.join_room') as mock_join_room, \
             patch('src.handlers.base_handler.request', self.mock_request), \
             patch('src.handlers.base_handler.logger') as mock_logger:

            self.mixin.join_socketio_room(room_id)

        mock_join_room.assert_called_once_with(room_id)
        mock_logger.debug.assert_called_once_with(
            'Client test_socket_789 joined Socket.IO room: test_room_123'
        )

    def test_leave_socketio_room(self):
        """Test leaving Socket.IO room"""
        room_id = "test_room_456"

        with patch('src.handlers.base_handler.leave_room') as mock_leave_room, \
             patch('src.handlers.base_handler.request', self.mock_request), \
             patch('src.handlers.base_handler.logger') as mock_logger:

            self.mixin.leave_socketio_room(room_id)

        mock_leave_room.assert_called_once_with(room_id)
        mock_logger.debug.assert_called_once_with(
            'Client test_socket_789 left Socket.IO room: test_room_456'
        )

    def test_broadcast_to_room(self):
        """Test broadcasting to room"""
        room_id = "test_room_broadcast"
        event_name = "test_event"
        test_data = {"message": "test broadcast"}

        with patch('src.handlers.base_handler.emit') as mock_emit, \
             patch('src.handlers.base_handler.logger') as mock_logger:

            self.mixin.broadcast_to_room(room_id, event_name, test_data)

        mock_emit.assert_called_once_with(event_name, test_data, to=room_id)
        mock_logger.debug.assert_called_once_with(
            'Broadcasted test_event to room: test_room_broadcast'
        )


class TestGameHandlerMixin:
    """Test GameHandlerMixin functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        # Create a test class that inherits from GameHandlerMixin and has a game_manager
        class TestGameMixin(GameHandlerMixin):
            def __init__(self):
                self.game_manager = Mock()

        self.mixin = TestGameMixin()

    def test_validate_game_phase_success(self):
        """Test successful game phase validation"""
        room_id = "test_room"
        required_phase = "responding"
        mock_game_state = {"phase": "responding", "room_id": room_id}

        self.mixin.game_manager.get_game_state.return_value = mock_game_state

        result = self.mixin.validate_game_phase(room_id, required_phase)

        self.mixin.game_manager.get_game_state.assert_called_once_with(room_id)
        assert result == mock_game_state

    def test_validate_game_phase_no_game_state(self):
        """Test game phase validation when no game state exists"""
        room_id = "nonexistent_room"
        required_phase = "responding"

        self.mixin.game_manager.get_game_state.return_value = None

        with pytest.raises(ValidationError) as exc_info:
            self.mixin.validate_game_phase(room_id, required_phase)

        assert exc_info.value.code == ErrorCode.ROOM_NOT_FOUND
        assert exc_info.value.message == 'Room not found or game not active'

    def test_validate_game_phase_wrong_phase(self):
        """Test game phase validation with wrong phase"""
        room_id = "test_room"
        required_phase = "guessing"
        mock_game_state = {"phase": "responding", "room_id": room_id}

        self.mixin.game_manager.get_game_state.return_value = mock_game_state

        with pytest.raises(ValidationError) as exc_info:
            self.mixin.validate_game_phase(room_id, required_phase)

        assert exc_info.value.code == ErrorCode.WRONG_PHASE
        assert exc_info.value.message == 'Action only allowed during guessing phase'

    def test_check_phase_not_expired_success(self):
        """Test checking phase not expired when phase is active"""
        room_id = "test_room"

        self.mixin.game_manager.is_phase_expired.return_value = False

        # Should not raise exception
        self.mixin.check_phase_not_expired(room_id)

        self.mixin.game_manager.is_phase_expired.assert_called_once_with(room_id)

    def test_check_phase_not_expired_failure(self):
        """Test checking phase not expired when phase has expired"""
        room_id = "test_room"

        self.mixin.game_manager.is_phase_expired.return_value = True

        with pytest.raises(ValidationError) as exc_info:
            self.mixin.check_phase_not_expired(room_id)

        assert exc_info.value.code == ErrorCode.PHASE_EXPIRED
        assert exc_info.value.message == 'Current phase has expired'

    def test_check_can_start_round_success(self):
        """Test checking can start round when allowed"""
        room_id = "test_room"

        self.mixin.game_manager.can_start_round.return_value = (True, "")

        # Should not raise exception
        self.mixin.check_can_start_round(room_id)

        self.mixin.game_manager.can_start_round.assert_called_once_with(room_id)

    def test_check_can_start_round_failure(self):
        """Test checking can start round when not allowed"""
        room_id = "test_room"
        failure_reason = "Not enough players"

        self.mixin.game_manager.can_start_round.return_value = (False, failure_reason)

        with pytest.raises(ValidationError) as exc_info:
            self.mixin.check_can_start_round(room_id)

        assert exc_info.value.code == ErrorCode.CANNOT_START_ROUND
        assert exc_info.value.message == failure_reason


class TestValidationHandlerMixin:
    """Test ValidationHandlerMixin functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        # Create a test class that inherits from ValidationHandlerMixin
        class TestValidationMixin(ValidationHandlerMixin):
            def __init__(self):
                self.validation_service = Mock()

            def validate_data_dict(self, data, required_fields=None):
                # Mock implementation for testing
                if not isinstance(data, dict):
                    raise ValidationError(ErrorCode.INVALID_DATA, "Invalid data format")
                if required_fields:
                    for field in required_fields:
                        if field not in data:
                            if field == 'room_id':
                                raise ValidationError(ErrorCode.MISSING_ROOM_ID, "Room ID is required")
                            elif field == 'player_name':
                                raise ValidationError(ErrorCode.MISSING_PLAYER_NAME, "Player name is required")
                            elif field == 'response':
                                raise ValidationError(ErrorCode.EMPTY_RESPONSE, "Response is required")
                            elif field == 'guess_index':
                                raise ValidationError(ErrorCode.MISSING_GUESS, "Guess index is required")
                return data

        self.mixin = TestValidationMixin()

    def test_validate_room_join_data_success(self):
        """Test successful room join data validation"""
        test_data = {"room_id": "test_room", "player_name": "test_player"}
        self.mixin.validation_service.validate_room_id.return_value = "test_room"
        self.mixin.validation_service.validate_player_name.return_value = "test_player"

        room_id, player_name = self.mixin.validate_room_join_data(test_data)

        self.mixin.validation_service.validate_room_id.assert_called_once_with("test_room")
        self.mixin.validation_service.validate_player_name.assert_called_once_with("test_player")
        assert room_id == "test_room"
        assert player_name == "test_player"

    def test_validate_room_join_data_missing_room_id(self):
        """Test room join data validation with missing room_id"""
        test_data = {"player_name": "test_player"}

        with pytest.raises(ValidationError) as exc_info:
            self.mixin.validate_room_join_data(test_data)

        assert exc_info.value.code == ErrorCode.MISSING_ROOM_ID

    def test_validate_room_join_data_missing_player_name(self):
        """Test room join data validation with missing player_name"""
        test_data = {"room_id": "test_room"}

        with pytest.raises(ValidationError) as exc_info:
            self.mixin.validate_room_join_data(test_data)

        assert exc_info.value.code == ErrorCode.MISSING_PLAYER_NAME

    def test_validate_response_data_success(self):
        """Test successful response data validation"""
        test_data = {"response": "This is my response"}
        self.mixin.validation_service.validate_response_text.return_value = "This is my response"

        result = self.mixin.validate_response_data(test_data)

        self.mixin.validation_service.validate_response_text.assert_called_once_with("This is my response")
        assert result == "This is my response"

    def test_validate_response_data_missing_response(self):
        """Test response data validation with missing response"""
        test_data = {"other_field": "value"}

        with pytest.raises(ValidationError) as exc_info:
            self.mixin.validate_response_data(test_data)

        assert exc_info.value.code == ErrorCode.EMPTY_RESPONSE

    def test_validate_guess_data_success(self):
        """Test successful guess data validation"""
        test_data = {"guess_index": 2}
        max_index = 5
        self.mixin.validation_service.validate_guess_index.return_value = 2

        result = self.mixin.validate_guess_data(test_data, max_index)

        self.mixin.validation_service.validate_guess_index.assert_called_once_with(2, max_index)
        assert result == 2

    def test_validate_guess_data_missing_guess_index(self):
        """Test guess data validation with missing guess_index"""
        test_data = {"other_field": "value"}
        max_index = 5

        with pytest.raises(ValidationError) as exc_info:
            self.mixin.validate_guess_data(test_data, max_index)

        assert exc_info.value.code == ErrorCode.MISSING_GUESS


class TestBaseRoomHandler:
    """Test BaseRoomHandler class"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = ConcreteRoomHandler()

    def test_inheritance(self):
        """Test BaseRoomHandler inherits from correct classes"""
        assert isinstance(self.handler, BaseHandler)
        assert isinstance(self.handler, RoomHandlerMixin)
        assert isinstance(self.handler, ValidationHandlerMixin)

    def test_has_all_base_handler_methods(self):
        """Test BaseRoomHandler has all BaseHandler methods"""
        assert hasattr(self.handler, 'get_current_session')
        assert hasattr(self.handler, 'require_session')
        assert hasattr(self.handler, 'validate_data_dict')
        assert hasattr(self.handler, 'emit_success')
        assert hasattr(self.handler, 'emit_error')

    def test_has_all_room_mixin_methods(self):
        """Test BaseRoomHandler has all RoomHandlerMixin methods"""
        assert hasattr(self.handler, 'join_socketio_room')
        assert hasattr(self.handler, 'leave_socketio_room')
        assert hasattr(self.handler, 'broadcast_to_room')

    def test_has_all_validation_mixin_methods(self):
        """Test BaseRoomHandler has all ValidationHandlerMixin methods"""
        assert hasattr(self.handler, 'validate_room_join_data')
        assert hasattr(self.handler, 'validate_response_data')
        assert hasattr(self.handler, 'validate_guess_data')


class TestBaseGameHandler:
    """Test BaseGameHandler class"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = ConcreteGameHandler()

    def test_inheritance(self):
        """Test BaseGameHandler inherits from correct classes"""
        assert isinstance(self.handler, BaseHandler)
        assert isinstance(self.handler, GameHandlerMixin)
        assert isinstance(self.handler, ValidationHandlerMixin)

    def test_has_all_base_handler_methods(self):
        """Test BaseGameHandler has all BaseHandler methods"""
        assert hasattr(self.handler, 'get_current_session')
        assert hasattr(self.handler, 'require_session')
        assert hasattr(self.handler, 'validate_data_dict')
        assert hasattr(self.handler, 'emit_success')
        assert hasattr(self.handler, 'emit_error')

    def test_has_all_game_mixin_methods(self):
        """Test BaseGameHandler has all GameHandlerMixin methods"""
        assert hasattr(self.handler, 'validate_game_phase')
        assert hasattr(self.handler, 'check_phase_not_expired')
        assert hasattr(self.handler, 'check_can_start_round')

    def test_has_all_validation_mixin_methods(self):
        """Test BaseGameHandler has all ValidationHandlerMixin methods"""
        assert hasattr(self.handler, 'validate_room_join_data')
        assert hasattr(self.handler, 'validate_response_data')
        assert hasattr(self.handler, 'validate_guess_data')


class TestBaseInfoHandler:
    """Test BaseInfoHandler class"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = BaseInfoHandler()

    def test_inheritance(self):
        """Test BaseInfoHandler inherits from BaseHandler only"""
        assert isinstance(self.handler, BaseHandler)
        # Should not inherit from mixins
        assert not isinstance(self.handler, RoomHandlerMixin)
        assert not isinstance(self.handler, GameHandlerMixin)
        assert not isinstance(self.handler, ValidationHandlerMixin)

    def test_has_base_handler_methods(self):
        """Test BaseInfoHandler has BaseHandler methods"""
        assert hasattr(self.handler, 'get_current_session')
        assert hasattr(self.handler, 'require_session')
        assert hasattr(self.handler, 'validate_data_dict')
        assert hasattr(self.handler, 'emit_success')
        assert hasattr(self.handler, 'emit_error')


class TestErrorHandlingPatterns:
    """Test error handling patterns across base handlers"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container
            self.handler = ConcreteBaseHandler()

    def test_validation_error_propagation(self):
        """Test that ValidationError exceptions are properly propagated"""
        with pytest.raises(ValidationError) as exc_info:
            self.handler.validate_data_dict("not_a_dict")

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Invalid data format" in exc_info.value.message

    def test_error_response_creation(self):
        """Test error response creation pattern"""
        mock_error_factory = Mock()
        self.mock_container.get.return_value = mock_error_factory
        mock_error_response = {"success": False, "error": {"code": "TEST_ERROR", "message": "Test message"}}
        mock_error_factory.create_error_response.return_value = mock_error_response

        with patch('src.handlers.base_handler.emit') as mock_emit:
            self.handler.emit_error("test_event", ErrorCode.INVALID_DATA, "Test message")

        mock_error_factory.create_error_response.assert_called_once_with(ErrorCode.INVALID_DATA, "Test message")
        mock_emit.assert_called_once_with("test_event", mock_error_response)

    def test_success_response_creation(self):
        """Test success response creation pattern"""
        mock_error_factory = Mock()
        self.mock_container.get.return_value = mock_error_factory
        test_data = {"result": "success"}
        mock_success_response = {"success": True, "data": test_data}
        mock_error_factory.create_success_response.return_value = mock_success_response

        with patch('src.handlers.base_handler.emit') as mock_emit:
            self.handler.emit_success("test_event", test_data)

        mock_error_factory.create_success_response.assert_called_once_with(test_data)
        mock_emit.assert_called_once_with("test_event", mock_success_response)


class TestIntegrationScenarios:
    """Test integration scenarios with multiple handler components"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        with patch('src.handlers.base_handler.get_container') as mock_get_container:
            self.mock_container = Mock()
            mock_get_container.return_value = self.mock_container

            # Setup service mocks
            self.mock_session_service = Mock()
            self.mock_validation_service = Mock()
            self.mock_error_factory = Mock()
            self.mock_game_manager = Mock()

            def get_service(service_name):
                services = {
                    'SessionService': self.mock_session_service,
                    'ValidationService': self.mock_validation_service,
                    'ErrorResponseFactory': self.mock_error_factory,
                    'GameManager': self.mock_game_manager
                }
                return services.get(service_name, Mock())

            self.mock_container.get.side_effect = get_service

            self.room_handler = ConcreteRoomHandler()
            self.game_handler = ConcreteGameHandler()

        # Mock Flask request
        self.mock_request = Mock()
        self.mock_request.sid = "test_socket_integration"

    def test_room_handler_complete_workflow(self):
        """Test complete room handler workflow"""
        # Setup
        test_data = {"room_id": "test_room", "player_name": "test_player"}
        mock_session = {"room_id": "test_room", "player_name": "test_player"}
        self.mock_session_service.get_session.return_value = mock_session
        self.mock_validation_service.validate_room_id.return_value = "test_room"
        self.mock_validation_service.validate_player_name.return_value = "test_player"

        with patch('src.handlers.base_handler.request', self.mock_request), \
             patch('src.handlers.base_handler.join_room') as mock_join_room:

            # Test data validation
            room_id, player_name = self.room_handler.validate_room_join_data(test_data)
            assert room_id == "test_room"
            assert player_name == "test_player"

            # Test session requirement
            session = self.room_handler.require_session()
            assert session == mock_session

            # Test room joining
            self.room_handler.join_socketio_room(room_id)
            mock_join_room.assert_called_once_with(room_id)

    def test_game_handler_complete_workflow(self):
        """Test complete game handler workflow"""
        # Setup
        room_id = "test_room"
        required_phase = "responding"
        mock_game_state = {"phase": "responding", "room_id": room_id, "players": ["player1", "player2"]}
        self.mock_game_manager.get_game_state.return_value = mock_game_state
        self.mock_game_manager.is_phase_expired.return_value = False
        self.mock_game_manager.can_start_round.return_value = (True, "")

        # Test phase validation
        game_state = self.game_handler.validate_game_phase(room_id, required_phase)
        assert game_state == mock_game_state

        # Test phase expiry check
        self.game_handler.check_phase_not_expired(room_id)

        # Test round start check
        self.game_handler.check_can_start_round(room_id)

        # Verify all calls
        self.mock_game_manager.get_game_state.assert_called_once_with(room_id)
        self.mock_game_manager.is_phase_expired.assert_called_once_with(room_id)
        self.mock_game_manager.can_start_round.assert_called_once_with(room_id)

    def test_error_handling_integration(self):
        """Test error handling integration across components"""
        # Test validation error from data validation
        with pytest.raises(ValidationError):
            self.room_handler.validate_data_dict("not_a_dict")

        # Test validation error from session requirement
        self.mock_session_service.get_session.return_value = None
        with pytest.raises(ValidationError):
            with patch('src.handlers.base_handler.request', self.mock_request):
                self.room_handler.require_session()

        # Test validation error from game phase check
        self.mock_game_manager.get_game_state.return_value = None
        with pytest.raises(ValidationError):
            self.game_handler.validate_game_phase("nonexistent_room", "responding")

    def test_service_dependency_access(self):
        """Test that all handlers can access their service dependencies"""
        # Test room handler service access
        assert self.room_handler.session_service is self.mock_session_service
        assert self.room_handler.validation_service is self.mock_validation_service
        assert self.room_handler.error_response_factory is self.mock_error_factory

        # Test game handler service access
        assert self.game_handler.game_manager is self.mock_game_manager
        assert self.game_handler.validation_service is self.mock_validation_service
        assert self.game_handler.error_response_factory is self.mock_error_factory