"""
Unit tests for src/utils/error_handling.py

Tests error handling decorators, response formatting, exception conversion,
and logging integration.
"""

import pytest
import logging
from unittest.mock import Mock, patch, call
from typing import Dict, Any

from src.utils.error_handling import (
    log_handler_error,
    log_handler_action,
    create_standard_success_response,
    create_standard_error_response,
    handle_validation_error,
    handle_generic_error,
    with_error_logging,
    safely_execute,
    validate_required_fields,
    ensure_user_session
)
from src.core.errors import ErrorCode, ValidationError


class TestLoggingFunctions:
    """Test logging utility functions."""

    def test_log_handler_error_basic(self, caplog):
        """Test basic error logging functionality."""
        with caplog.at_level(logging.ERROR):
            error = ValueError("Test error")
            log_handler_error("TestHandler", error)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"
        assert "TestHandler" in caplog.records[0].message
        assert "ValueError" in caplog.records[0].message
        assert "Test error" in caplog.records[0].message

    def test_log_handler_error_with_context(self, caplog):
        """Test error logging with context information."""
        with caplog.at_level(logging.ERROR):
            error = ValueError("Test error")
            context = {"room_id": "test-room", "player": "test-player"}
            log_handler_error("TestHandler", error, context)

        assert len(caplog.records) == 1
        log_message = caplog.records[0].message
        assert "TestHandler" in log_message
        assert "ValueError" in log_message
        assert "Test error" in log_message
        assert "Context:" in log_message
        assert "room_id" in log_message
        assert "test-player" in log_message

    def test_log_handler_error_without_context(self, caplog):
        """Test error logging without context."""
        with caplog.at_level(logging.ERROR):
            error = RuntimeError("Runtime issue")
            log_handler_error("TestHandler", error, None)

        assert len(caplog.records) == 1
        log_message = caplog.records[0].message
        assert "Context:" not in log_message
        assert "RuntimeError" in log_message

    def test_log_handler_action_basic(self, caplog):
        """Test basic action logging functionality."""
        with caplog.at_level(logging.INFO):
            log_handler_action("TestHandler", "test action")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        assert "TestHandler" in caplog.records[0].message
        assert "test action" in caplog.records[0].message

    def test_log_handler_action_with_context(self, caplog):
        """Test action logging with context information."""
        with caplog.at_level(logging.INFO):
            context = {"user_id": "123", "operation": "join_room"}
            log_handler_action("TestHandler", "performing action", context)

        assert len(caplog.records) == 1
        log_message = caplog.records[0].message
        assert "TestHandler" in log_message
        assert "performing action" in log_message
        assert "Context:" in log_message
        assert "user_id" in log_message

    def test_log_handler_action_without_context(self, caplog):
        """Test action logging without context."""
        with caplog.at_level(logging.INFO):
            log_handler_action("TestHandler", "simple action", None)

        assert len(caplog.records) == 1
        log_message = caplog.records[0].message
        assert "Context:" not in log_message
        assert "simple action" in log_message


class TestResponseFormatting:
    """Test response formatting functions."""

    def test_create_standard_success_response_basic(self):
        """Test creating basic success response."""
        data = {"result": "success", "value": 42}
        response = create_standard_success_response(data)

        expected = {
            "success": True,
            "data": {"result": "success", "value": 42}
        }
        assert response == expected

    def test_create_standard_success_response_empty_data(self):
        """Test creating success response with empty data."""
        response = create_standard_success_response({})

        expected = {
            "success": True,
            "data": {}
        }
        assert response == expected

    def test_create_standard_success_response_complex_data(self):
        """Test creating success response with complex nested data."""
        data = {
            "players": ["Alice", "Bob"],
            "game_state": {
                "phase": "waiting",
                "round": 1
            },
            "metadata": {
                "timestamp": 1234567890,
                "version": "1.0"
            }
        }
        response = create_standard_success_response(data)

        assert response["success"] is True
        assert response["data"] == data

    def test_create_standard_error_response_basic(self):
        """Test creating basic error response."""
        response = create_standard_error_response(
            ErrorCode.INVALID_DATA,
            "Invalid input provided"
        )

        expected = {
            "success": False,
            "error": {
                "code": "INVALID_DATA",
                "message": "Invalid input provided",
                "details": {}
            }
        }
        assert response == expected

    def test_create_standard_error_response_with_details(self):
        """Test creating error response with details."""
        details = {"field": "username", "reason": "too_short"}
        response = create_standard_error_response(
            ErrorCode.INVALID_DATA,
            "Validation failed",
            details
        )

        expected = {
            "success": False,
            "error": {
                "code": "INVALID_DATA",
                "message": "Validation failed",
                "details": {"field": "username", "reason": "too_short"}
            }
        }
        assert response == expected

    def test_create_standard_error_response_none_details(self):
        """Test creating error response with None details."""
        response = create_standard_error_response(
            ErrorCode.ROOM_NOT_FOUND,
            "Room does not exist",
            None
        )

        assert response["success"] is False
        assert response["error"]["details"] == {}


class TestExceptionHandling:
    """Test exception handling and conversion functions."""

    @patch('src.utils.error_handling.log_handler_error')
    def test_handle_validation_error(self, mock_log):
        """Test handling of ValidationError."""
        error = ValidationError(
            ErrorCode.INVALID_DATA,
            "Test validation error",
            {"field": "test"}
        )

        response = handle_validation_error(error, "TestHandler")

        # Check logging was called
        mock_log.assert_called_once_with(
            "TestHandler",
            error,
            {"error_code": "INVALID_DATA"}
        )

        # Check response format
        expected = {
            "success": False,
            "error": {
                "code": "INVALID_DATA",
                "message": "Test validation error",
                "details": {"field": "test"}
            }
        }
        assert response == expected

    @patch('src.utils.error_handling.log_handler_error')
    def test_handle_generic_error_value_error(self, mock_log):
        """Test handling of ValueError."""
        error = ValueError("Invalid value provided")

        response = handle_generic_error(error, "TestHandler")

        # Check logging was called
        mock_log.assert_called_once_with("TestHandler", error)

        # Check response format
        expected = {
            "success": False,
            "error": {
                "code": "INVALID_DATA",
                "message": "Invalid value provided",
                "details": {}
            }
        }
        assert response == expected

    @patch('src.utils.error_handling.log_handler_error')
    def test_handle_generic_error_key_error(self, mock_log):
        """Test handling of KeyError."""
        error = KeyError("'missing_key'")

        response = handle_generic_error(error, "TestHandler")

        # Check logging was called
        mock_log.assert_called_once_with("TestHandler", error)

        # Check response format
        expected = {
            "success": False,
            "error": {
                "code": "MISSING_DATA",
                "message": "Missing required data: \"'missing_key'\"",
                "details": {}
            }
        }
        assert response == expected

    @patch('src.utils.error_handling.log_handler_error')
    def test_handle_generic_error_type_error(self, mock_log):
        """Test handling of TypeError."""
        error = TypeError("unsupported operand type(s)")

        response = handle_generic_error(error, "TestHandler")

        # Check logging was called
        mock_log.assert_called_once_with("TestHandler", error)

        # Check response format
        expected = {
            "success": False,
            "error": {
                "code": "INVALID_DATA",
                "message": "Invalid data type provided",
                "details": {}
            }
        }
        assert response == expected

    @patch('src.utils.error_handling.log_handler_error')
    def test_handle_generic_error_unknown_exception(self, mock_log):
        """Test handling of unknown exception type."""
        error = RuntimeError("Unknown runtime error")

        response = handle_generic_error(error, "TestHandler")

        # Check logging was called
        mock_log.assert_called_once_with("TestHandler", error)

        # Check response format
        expected = {
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": {}
            }
        }
        assert response == expected


class TestErrorLoggingDecorator:
    """Test with_error_logging decorator."""

    @patch('src.utils.error_handling.log_handler_action')
    def test_with_error_logging_success(self, mock_log):
        """Test decorator with successful function execution."""
        @with_error_logging("TestHandler")
        def test_function(x, y):
            return x + y

        result = test_function(2, 3)

        assert result == 5
        assert mock_log.call_count == 2
        mock_log.assert_has_calls([
            call("TestHandler", "Starting test_function"),
            call("TestHandler", "Completed test_function")
        ])

    @patch('src.utils.error_handling.log_handler_action')
    @patch('src.utils.error_handling.handle_validation_error')
    def test_with_error_logging_validation_error(self, mock_handle_error, mock_log):
        """Test decorator with ValidationError."""
        error = ValidationError(ErrorCode.INVALID_DATA, "Test error")
        mock_handle_error.return_value = {"success": False}

        @with_error_logging("TestHandler")
        def test_function():
            raise error

        with pytest.raises(ValidationError):
            test_function()

        # Should log start but not completion
        mock_log.assert_called_once_with("TestHandler", "Starting test_function")
        mock_handle_error.assert_called_once_with(error, "TestHandler")

    @patch('src.utils.error_handling.log_handler_action')
    @patch('src.utils.error_handling.handle_generic_error')
    def test_with_error_logging_generic_error(self, mock_handle_error, mock_log):
        """Test decorator with generic exception."""
        error = ValueError("Test error")
        mock_handle_error.return_value = {"success": False}

        @with_error_logging("TestHandler")
        def test_function():
            raise error

        with pytest.raises(ValueError):
            test_function()

        # Should log start but not completion
        mock_log.assert_called_once_with("TestHandler", "Starting test_function")
        mock_handle_error.assert_called_once_with(error, "TestHandler")

    @patch('src.utils.error_handling.log_handler_action')
    def test_with_error_logging_preserves_function_attributes(self, mock_log):
        """Test that decorator preserves function attributes."""
        @with_error_logging("TestHandler")
        def documented_function(x):
            """This function has documentation."""
            return x * 2

        assert documented_function.__name__ == "documented_function"
        assert "documentation" in documented_function.__doc__


class TestSafelyExecute:
    """Test safely_execute utility function."""

    def test_safely_execute_success(self):
        """Test successful function execution."""
        def test_func():
            return "success"

        result = safely_execute(test_func)
        assert result == "success"

    def test_safely_execute_with_exception_default_return(self, caplog):
        """Test function execution with exception and default return."""
        def test_func():
            raise ValueError("Test error")

        with caplog.at_level(logging.ERROR):
            result = safely_execute(test_func, default_return="default")

        assert result == "default"
        assert len(caplog.records) == 1
        assert "Error in safely_execute" in caplog.records[0].message

    def test_safely_execute_with_custom_error_handler(self):
        """Test function execution with custom error handler."""
        error_handled = []

        def custom_error_handler(error):
            error_handled.append(str(error))

        def test_func():
            raise RuntimeError("Custom error")

        result = safely_execute(
            test_func,
            error_handler=custom_error_handler,
            default_return="handled"
        )

        assert result == "handled"
        assert error_handled == ["Custom error"]

    def test_safely_execute_no_default_return(self, caplog):
        """Test function execution with no default return specified."""
        def test_func():
            raise ValueError("Test error")

        with caplog.at_level(logging.ERROR):
            result = safely_execute(test_func)

        assert result is None
        assert len(caplog.records) == 1

    def test_safely_execute_error_handler_and_logging(self, caplog):
        """Test that custom error handler prevents default logging."""
        def custom_error_handler(error):
            pass  # Do nothing

        def test_func():
            raise ValueError("Test error")

        with caplog.at_level(logging.ERROR):
            safely_execute(test_func, error_handler=custom_error_handler)

        # Should not have logged anything since custom handler was provided
        assert len(caplog.records) == 0


class TestValidationUtils:
    """Test validation utility functions."""

    def test_validate_required_fields_success(self):
        """Test successful validation of required fields."""
        data = {"field1": "value1", "field2": "value2", "field3": "value3"}
        required_fields = ["field1", "field2"]

        # Should not raise any exception
        validate_required_fields(data, required_fields, "TestHandler")

    def test_validate_required_fields_missing_single(self):
        """Test validation with single missing field."""
        data = {"field1": "value1"}
        required_fields = ["field1", "field2"]

        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, required_fields, "TestHandler")

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Missing required fields: field2" in exc_info.value.message

    def test_validate_required_fields_missing_multiple(self):
        """Test validation with multiple missing fields."""
        data = {"field1": "value1"}
        required_fields = ["field1", "field2", "field3"]

        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, required_fields, "TestHandler")

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "field2" in exc_info.value.message
        assert "field3" in exc_info.value.message

    def test_validate_required_fields_invalid_data_type(self):
        """Test validation with invalid data type."""
        data = "not a dictionary"
        required_fields = ["field1"]

        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, required_fields, "TestHandler")

        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert "Invalid data format - expected dictionary" in exc_info.value.message

    def test_validate_required_fields_none_data(self):
        """Test validation with None data."""
        required_fields = ["field1"]

        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(None, required_fields, "TestHandler")

        assert exc_info.value.code == ErrorCode.INVALID_DATA

    def test_validate_required_fields_empty_requirements(self):
        """Test validation with no required fields."""
        data = {"field1": "value1"}
        required_fields = []

        # Should not raise any exception
        validate_required_fields(data, required_fields, "TestHandler")

    def test_ensure_user_session_valid_session(self):
        """Test ensuring valid user session."""
        session_info = {"user_id": "123", "room_id": "test-room"}

        result = ensure_user_session(session_info, "TestHandler")
        assert result == session_info

    def test_ensure_user_session_none_session(self):
        """Test ensuring user session with None session."""
        with pytest.raises(ValidationError) as exc_info:
            ensure_user_session(None, "TestHandler")

        assert exc_info.value.code == ErrorCode.NOT_IN_ROOM
        assert "You are not currently in a room" in exc_info.value.message

    def test_ensure_user_session_empty_session(self):
        """Test ensuring user session with empty session."""
        with pytest.raises(ValidationError) as exc_info:
            ensure_user_session({}, "TestHandler")

        assert exc_info.value.code == ErrorCode.NOT_IN_ROOM

    def test_ensure_user_session_false_session(self):
        """Test ensuring user session with falsy session."""
        with pytest.raises(ValidationError) as exc_info:
            ensure_user_session(False, "TestHandler")

        assert exc_info.value.code == ErrorCode.NOT_IN_ROOM


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple functions."""

    @patch('src.utils.error_handling.log_handler_error')
    def test_validation_error_handling_flow(self, mock_log):
        """Test complete validation error handling flow."""
        # Create validation error
        error = ValidationError(
            ErrorCode.MISSING_DATA,
            "Required field missing",
            {"field": "username"}
        )

        # Handle the error
        response = handle_validation_error(error, "UserHandler")

        # Verify logging
        mock_log.assert_called_once_with(
            "UserHandler",
            error,
            {"error_code": "MISSING_DATA"}
        )

        # Verify response structure
        assert response["success"] is False
        assert response["error"]["code"] == "MISSING_DATA"
        assert response["error"]["message"] == "Required field missing"
        assert response["error"]["details"] == {"field": "username"}

    def test_field_validation_integration(self):
        """Test integration of field validation with error responses."""
        data = {"username": "test"}
        required_fields = ["username", "room_id"]

        try:
            validate_required_fields(data, required_fields, "TestHandler")
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            response = handle_validation_error(e, "TestHandler")

            assert response["success"] is False
            assert response["error"]["code"] == "INVALID_DATA"
            assert "room_id" in response["error"]["message"]

    def test_session_validation_integration(self):
        """Test integration of session validation with error handling."""
        try:
            ensure_user_session(None, "SessionHandler")
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            response = handle_validation_error(e, "SessionHandler")

            assert response["success"] is False
            assert response["error"]["code"] == "NOT_IN_ROOM"
            assert "not currently in a room" in response["error"]["message"]