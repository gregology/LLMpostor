"""
Unit tests for the ErrorResponseFactory module.

Tests error response creation and formatting functionality.
"""

import pytest
from unittest.mock import patch
from src.services.error_response_factory import ErrorResponseFactory
from src.core.errors import ErrorCode, ValidationError


class TestErrorResponseFactory:
    """Test cases for ErrorResponseFactory class."""
    
    def setup_method(self):
        """Setup error response factory instance for tests."""
        self.factory = ErrorResponseFactory()
    
    def test_create_success_response(self):
        """Test success response creation."""
        data = {"test": "value", "count": 42}
        response = self.factory.create_success_response(data)
        
        expected = {
            "success": True,
            "data": data
        }
        assert response == expected
    
    def test_create_error_response(self):
        """Test error response creation."""
        response = self.factory.create_error_response(
            ErrorCode.INVALID_DATA, 
            "Test error",
            {"detail": "value"}
        )
        
        expected = {
            "success": False,
            "error": {
                "code": "INVALID_DATA",
                "message": "Test error",
                "details": {"detail": "value"}
            }
        }
        assert response == expected
    
    def test_create_error_response_without_details(self):
        """Test error response creation without details."""
        response = self.factory.create_error_response(
            ErrorCode.INTERNAL_ERROR,
            "Internal error"
        )
        
        expected = {
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal error",
                "details": {}
            }
        }
        assert response == expected
    
    @patch('src.services.error_response_factory.emit')
    def test_emit_error(self, mock_emit):
        """Test error emission to client."""
        self.factory.emit_error(
            ErrorCode.INVALID_DATA, 
            "Test error",
            {"detail": "value"}
        )
        
        mock_emit.assert_called_once_with('error', {
            "success": False,
            "error": {
                "code": "INVALID_DATA",
                "message": "Test error",
                "details": {"detail": "value"}
            }
        })
    
    @patch('src.services.error_response_factory.emit')
    def test_emit_validation_error(self, mock_emit):
        """Test validation error emission to client."""
        error = ValidationError(
            ErrorCode.MISSING_ROOM_ID, 
            "Room ID required", 
            {"field": "room_id"}
        )
        self.factory.emit_validation_error(error)
        
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
        code, message = self.factory.handle_exception(error, "test_context")
        
        assert code == ErrorCode.INVALID_DATA
        assert message == "Invalid data"
    
    @patch('src.services.error_response_factory.logger')
    def test_handle_exception_generic_error(self, mock_logger):
        """Test exception handling for generic exceptions."""
        error = ValueError("Some error")
        code, message = self.factory.handle_exception(error, "test_context")
        
        assert code == ErrorCode.INTERNAL_ERROR
        assert message == "An internal error occurred"
        mock_logger.error.assert_called()
    
    def test_generate_data_checksum(self):
        """Test data checksum generation."""
        data = {"test": "value", "number": 42}
        checksum1 = self.factory.generate_data_checksum(data)
        checksum2 = self.factory.generate_data_checksum(data)
        
        # Should be consistent
        assert checksum1 == checksum2
        assert len(checksum1) == 64  # SHA256 hex length
        
        # Different data should have different checksums
        different_data = {"test": "different", "number": 42}
        checksum3 = self.factory.generate_data_checksum(different_data)
        assert checksum1 != checksum3
    
    def test_verify_data_checksum_valid(self):
        """Test data checksum verification with valid checksum."""
        data = {"test": "value"}
        expected_checksum = self.factory.generate_data_checksum(data)
        
        # Should not raise exception
        result = self.factory.verify_data_checksum(data, expected_checksum)
        assert result is True
    
    def test_verify_data_checksum_invalid(self):
        """Test data checksum verification with invalid checksum."""
        data = {"test": "value"}
        wrong_checksum = "invalid_checksum"
        
        with pytest.raises(ValidationError) as exc_info:
            self.factory.verify_data_checksum(data, wrong_checksum)
        assert exc_info.value.code == ErrorCode.DATA_CHECKSUM_MISMATCH
    
    @patch('src.services.error_response_factory.logger')
    def test_log_error_context(self, mock_logger):
        """Test error context logging."""
        self.factory.log_error_context(
            "test context", 
            room_id="test", 
            player_id="123"
        )
        
        mock_logger.error.assert_called_once()
        # Check that the call includes our context
        args, kwargs = mock_logger.error.call_args
        assert "test context" in args[0]
        assert "room_id" in args[0]
        assert "player_id" in args[0]