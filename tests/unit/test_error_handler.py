"""
Unit tests for the ErrorHandler module.

Tests validation functions, error formatting, and error handling utilities.
"""

import pytest
from unittest.mock import patch
from src.error_handler import ErrorHandler, ErrorCode, ValidationError, with_error_handling


class TestErrorHandler:
    """Test cases for ErrorHandler class."""
    
    def test_validate_room_id_valid(self):
        """Test room ID validation with valid inputs."""
        # Valid room IDs
        valid_ids = [
            "test-room",
            "room_123",
            "MyRoom",
            "room-with-hyphens",
            "room_with_underscores",
            "a",  # Single character
            "a" * 50  # Max length
        ]
        
        for room_id in valid_ids:
            result = ErrorHandler.validate_room_id(room_id)
            assert result == room_id.strip()
    
    def test_validate_room_id_invalid(self):
        """Test room ID validation with invalid inputs."""
        # Empty or None
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_room_id("")
        assert exc_info.value.code == ErrorCode.MISSING_ROOM_ID
        
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_room_id(None)
        assert exc_info.value.code == ErrorCode.MISSING_ROOM_ID
        
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_room_id("   ")
        assert exc_info.value.code == ErrorCode.MISSING_ROOM_ID
        
        # Too long
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_room_id("a" * 51)
        assert exc_info.value.code == ErrorCode.INVALID_ROOM_ID
        
        # Invalid characters
        invalid_ids = [
            "room with spaces",
            "room@special",
            "room#hash",
            "room$dollar",
            "room%percent",
            "room.dot"
        ]
        
        for room_id in invalid_ids:
            with pytest.raises(ValidationError) as exc_info:
                ErrorHandler.validate_room_id(room_id)
            assert exc_info.value.code == ErrorCode.INVALID_ROOM_ID
    
    def test_validate_player_name_valid(self):
        """Test player name validation with valid inputs."""
        valid_names = [
            "Alice",
            "Bob123",
            "Player One",
            "A",  # Single character
            "A" * 20  # Max length
        ]
        
        for name in valid_names:
            result = ErrorHandler.validate_player_name(name)
            assert result == name.strip()
    
    def test_validate_player_name_invalid(self):
        """Test player name validation with invalid inputs."""
        # Empty or None
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_player_name("")
        assert exc_info.value.code == ErrorCode.MISSING_PLAYER_NAME
        
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_player_name(None)
        assert exc_info.value.code == ErrorCode.MISSING_PLAYER_NAME
        
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_player_name("   ")
        assert exc_info.value.code == ErrorCode.MISSING_PLAYER_NAME
        
        # Too long
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_player_name("A" * 21)
        assert exc_info.value.code == ErrorCode.PLAYER_NAME_TOO_LONG
    
    def test_validate_response_text_valid(self):
        """Test response text validation with valid inputs."""
        valid_responses = [
            "This is a valid response.",
            "A",  # Single character
            "A" * 100  # Max length
        ]
        
        for response in valid_responses:
            result = ErrorHandler.validate_response_text(response)
            assert result == response.strip()
    
    def test_validate_response_text_invalid(self):
        """Test response text validation with invalid inputs."""
        # Empty or None
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_response_text("")
        assert exc_info.value.code == ErrorCode.EMPTY_RESPONSE
        
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_response_text(None)
        assert exc_info.value.code == ErrorCode.EMPTY_RESPONSE
        
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_response_text("   ")
        assert exc_info.value.code == ErrorCode.EMPTY_RESPONSE
        
        # Too long
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_response_text("A" * 1001)
        assert exc_info.value.code == ErrorCode.RESPONSE_TOO_LONG
    
    def test_validate_guess_index_valid(self):
        """Test guess index validation with valid inputs."""
        # Valid indices
        assert ErrorHandler.validate_guess_index(0, 5) == 0
        assert ErrorHandler.validate_guess_index(2, 5) == 2
        assert ErrorHandler.validate_guess_index(4, 5) == 4
    
    def test_validate_guess_index_invalid(self):
        """Test guess index validation with invalid inputs."""
        # None
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_guess_index(None, 5)
        assert exc_info.value.code == ErrorCode.MISSING_GUESS
        
        # Not an integer
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_guess_index("2", 5)
        assert exc_info.value.code == ErrorCode.INVALID_GUESS_FORMAT
        
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_guess_index(2.5, 5)
        assert exc_info.value.code == ErrorCode.INVALID_GUESS_FORMAT
        
        # Out of range
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_guess_index(-1, 5)
        assert exc_info.value.code == ErrorCode.INVALID_GUESS_INDEX
        
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_guess_index(5, 5)
        assert exc_info.value.code == ErrorCode.INVALID_GUESS_INDEX
    
    def test_validate_socket_data_valid(self):
        """Test socket data validation with valid inputs."""
        # Valid data
        data = {"room_id": "test", "player_name": "Alice"}
        result = ErrorHandler.validate_socket_data(data, ["room_id", "player_name"])
        assert result == data
        
        # No required fields
        result = ErrorHandler.validate_socket_data(data)
        assert result == data
    
    def test_validate_socket_data_invalid(self):
        """Test socket data validation with invalid inputs."""
        # Not a dictionary
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_socket_data("not a dict")
        assert exc_info.value.code == ErrorCode.INVALID_DATA
        
        # Missing single specific field (should return specific error)
        data = {"room_id": "test"}
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_socket_data(data, ["room_id", "player_name"])
        assert exc_info.value.code == ErrorCode.MISSING_PLAYER_NAME
        
        # Missing multiple fields (should return generic error)
        data = {}
        with pytest.raises(ValidationError) as exc_info:
            ErrorHandler.validate_socket_data(data, ["room_id", "player_name"])
        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "room_id" in exc_info.value.message
    
    @patch('src.error_handler.emit')
    def test_emit_error(self, mock_emit):
        """Test error emission to client."""
        ErrorHandler.emit_error(ErrorCode.INVALID_DATA, "Test error", {"detail": "value"})
        
        mock_emit.assert_called_once_with('error', {
            "success": False,
            "error": {
                "code": "INVALID_DATA",
                "message": "Test error",
                "details": {"detail": "value"}
            }
        })
    
    @patch('src.error_handler.emit')
    def test_emit_validation_error(self, mock_emit):
        """Test validation error emission to client."""
        error = ValidationError(ErrorCode.MISSING_ROOM_ID, "Room ID required", {"field": "room_id"})
        ErrorHandler.emit_validation_error(error)
        
        mock_emit.assert_called_once_with('error', {
            "success": False,
            "error": {
                "code": "MISSING_ROOM_ID",
                "message": "Room ID required",
                "details": {"field": "room_id"}
            }
        })
    
    def test_handle_exception_validation_error(self):
        """Test exception handling for ValidationError."""
        error = ValidationError(ErrorCode.INVALID_DATA, "Invalid data")
        code, message = ErrorHandler.handle_exception(error, "test_context")
        
        assert code == ErrorCode.INVALID_DATA
        assert message == "Invalid data"
    
    @patch('src.error_handler.logger')
    def test_handle_exception_generic_error(self, mock_logger):
        """Test exception handling for generic exceptions."""
        error = ValueError("Some error")
        code, message = ErrorHandler.handle_exception(error, "test_context")
        
        assert code == ErrorCode.INTERNAL_ERROR
        assert message == "An internal error occurred"
        mock_logger.error.assert_called()
    
    def test_create_success_response(self):
        """Test success response creation."""
        data = {"key": "value"}
        response = ErrorHandler.create_success_response(data)
        
        assert response == {
            "success": True,
            "data": data
        }
    
    @patch('src.error_handler.logger')
    def test_log_error_context(self, mock_logger):
        """Test error context logging."""
        ErrorHandler.log_error_context("test context", room_id="test", player_id="123")
        
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "test context" in call_args
        assert "room_id" in call_args
        assert "player_id" in call_args


class TestWithErrorHandlingDecorator:
    """Test cases for the with_error_handling decorator."""
    
    @patch('src.error_handler.ErrorHandler.emit_validation_error')
    def test_decorator_catches_validation_error(self, mock_emit):
        """Test that decorator catches ValidationError."""
        @with_error_handling
        def test_function():
            raise ValidationError(ErrorCode.INVALID_DATA, "Test error")
        
        test_function()
        mock_emit.assert_called_once()
    
    @patch('src.error_handler.ErrorHandler.emit_error')
    @patch('src.error_handler.ErrorHandler.handle_exception')
    def test_decorator_catches_generic_error(self, mock_handle, mock_emit):
        """Test that decorator catches generic exceptions."""
        mock_handle.return_value = (ErrorCode.INTERNAL_ERROR, "Internal error")
        
        @with_error_handling
        def test_function():
            raise ValueError("Test error")
        
        test_function()
        mock_handle.assert_called_once()
        mock_emit.assert_called_once_with(ErrorCode.INTERNAL_ERROR, "Internal error")
    
    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""
        @with_error_handling
        def test_function():
            """Test docstring."""
            return "success"
        
        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test docstring."
    
    def test_decorator_allows_successful_execution(self):
        """Test that decorator allows successful function execution."""
        @with_error_handling
        def test_function(x, y):
            return x + y
        
        result = test_function(2, 3)
        assert result == 5


class TestValidationError:
    """Test cases for ValidationError exception."""
    
    def test_validation_error_creation(self):
        """Test ValidationError creation with all parameters."""
        details = {"field": "room_id", "value": "invalid"}
        error = ValidationError(ErrorCode.INVALID_ROOM_ID, "Invalid room ID", details)
        
        assert error.code == ErrorCode.INVALID_ROOM_ID
        assert error.message == "Invalid room ID"
        assert error.details == details
        assert str(error) == "Invalid room ID"
    
    def test_validation_error_without_details(self):
        """Test ValidationError creation without details."""
        error = ValidationError(ErrorCode.MISSING_PLAYER_NAME, "Player name required")
        
        assert error.code == ErrorCode.MISSING_PLAYER_NAME
        assert error.message == "Player name required"
        assert error.details == {}


class TestErrorCode:
    """Test cases for ErrorCode enum."""
    
    def test_error_codes_exist(self):
        """Test that all expected error codes exist."""
        expected_codes = [
            'INVALID_DATA', 'MISSING_ROOM_ID', 'MISSING_PLAYER_NAME',
            'INVALID_ROOM_ID', 'PLAYER_NAME_TOO_LONG', 'ALREADY_IN_ROOM',
            'PLAYER_NAME_TAKEN', 'NOT_IN_ROOM', 'ROOM_NOT_FOUND',
            'LEAVE_FAILED', 'ROOM_FULL', 'CANNOT_START_ROUND',
            'NO_PROMPTS_AVAILABLE', 'PROMPT_ERROR', 'START_ROUND_FAILED',
            'WRONG_PHASE', 'PHASE_EXPIRED', 'EMPTY_RESPONSE',
            'RESPONSE_TOO_LONG', 'SUBMIT_FAILED', 'ALREADY_SUBMITTED',
            'MISSING_GUESS', 'INVALID_GUESS_FORMAT', 'INVALID_GUESS_INDEX',
            'SUBMIT_GUESS_FAILED', 'ALREADY_GUESSED', 'NO_RESULTS_AVAILABLE',
            'DATA_CORRUPTION', 'INTERNAL_ERROR', 'SERVICE_UNAVAILABLE',
            'RATE_LIMITED'
        ]
        
        for code_name in expected_codes:
            assert hasattr(ErrorCode, code_name)
            assert ErrorCode[code_name].value == code_name