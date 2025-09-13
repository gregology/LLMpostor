"""
Unit tests for the ValidationService module.

Tests validation functions and error handling for input validation.
"""

import pytest
from src.services.validation_service import ValidationService
from src.core.errors import ErrorCode, ValidationError


class TestValidationService:
    """Test cases for ValidationService class."""
    
    def setup_method(self):
        """Setup validation service instance for tests."""
        self.validation_service = ValidationService()
    
    def test_validate_room_id_valid(self):
        """Test room ID validation with valid inputs."""
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
            result = self.validation_service.validate_room_id(room_id)
            assert result == room_id.strip().lower()
    
    def test_validate_room_id_invalid(self):
        """Test room ID validation with invalid inputs."""
        # Empty or None
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_room_id("")
        assert exc_info.value.code == ErrorCode.MISSING_ROOM_ID
        
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_room_id(None)
        assert exc_info.value.code == ErrorCode.MISSING_ROOM_ID
        
        # Too long
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_room_id("a" * 51)
        assert exc_info.value.code == ErrorCode.INVALID_ROOM_ID
        
        # Invalid characters
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_room_id("room@test")
        assert exc_info.value.code == ErrorCode.INVALID_ROOM_ID
        
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_room_id("room space")
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
            result = self.validation_service.validate_player_name(name)
            assert result == name.strip()
    
    def test_validate_player_name_invalid(self):
        """Test player name validation with invalid inputs."""
        # Empty or None
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_player_name("")
        assert exc_info.value.code == ErrorCode.MISSING_PLAYER_NAME
        
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_player_name(None)
        assert exc_info.value.code == ErrorCode.MISSING_PLAYER_NAME
        
        # Too long
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_player_name("A" * 21)
        assert exc_info.value.code == ErrorCode.PLAYER_NAME_TOO_LONG
    
    def test_validate_response_text_valid(self):
        """Test response text validation with valid inputs."""
        valid_responses = [
            "A good response",
            "123",
            "Short",
            "A" * 100  # Max length (default)
        ]
        
        for response in valid_responses:
            result = self.validation_service.validate_response_text(response)
            assert result == response.strip()
    
    def test_validate_response_text_invalid(self):
        """Test response text validation with invalid inputs."""
        # Empty or None
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_response_text("")
        assert exc_info.value.code == ErrorCode.EMPTY_RESPONSE
        
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_response_text(None)
        assert exc_info.value.code == ErrorCode.EMPTY_RESPONSE
        
        # Too short (after stripping)
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_response_text("   ")
        assert exc_info.value.code == ErrorCode.EMPTY_RESPONSE
    
    def test_validate_guess_index_valid(self):
        """Test guess index validation with valid inputs."""
        max_index = 5
        
        for i in range(max_index):
            result = self.validation_service.validate_guess_index(i, max_index)
            assert result == i
    
    def test_validate_guess_index_invalid(self):
        """Test guess index validation with invalid inputs."""
        max_index = 5
        
        # None
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_guess_index(None, max_index)
        assert exc_info.value.code == ErrorCode.MISSING_GUESS
        
        # Not an integer
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_guess_index("2", max_index)
        assert exc_info.value.code == ErrorCode.INVALID_GUESS_FORMAT
        
        # Out of range
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_guess_index(-1, max_index)
        assert exc_info.value.code == ErrorCode.INVALID_GUESS_INDEX
        
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_guess_index(max_index, max_index)
        assert exc_info.value.code == ErrorCode.INVALID_GUESS_INDEX
    
    def test_validate_socket_data_valid(self):
        """Test socket data validation with valid inputs."""
        valid_data = {"room_id": "test", "player_name": "Alice"}
        
        # No required fields
        result = self.validation_service.validate_socket_data(valid_data)
        assert result == valid_data
        
        # With required fields
        result = self.validation_service.validate_socket_data(valid_data, ["room_id"])
        assert result == valid_data
    
    def test_validate_socket_data_invalid(self):
        """Test socket data validation with invalid inputs."""
        # Not a dictionary
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_socket_data("invalid")
        assert exc_info.value.code == ErrorCode.INVALID_DATA
        
        # Missing required fields - gets specific error for player_name
        data = {"room_id": "test"}
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_socket_data(data, ["room_id", "player_name"])
        assert exc_info.value.code == ErrorCode.MISSING_PLAYER_NAME
        assert "Player name is required" in exc_info.value.message
    
    def test_sanitize_user_input_valid(self):
        """Test user input sanitization with valid inputs."""
        inputs = [
            "Clean text",
            "Text with    multiple spaces",
            "   Trimmed   ",
        ]
        
        expected = [
            "Clean text",
            "Text with multiple spaces",
            "Trimmed",
        ]
        
        for input_text, expected_text in zip(inputs, expected):
            result = self.validation_service.sanitize_user_input(input_text)
            assert result == expected_text
    
    def test_sanitize_user_input_with_length_limit(self):
        """Test user input sanitization with length limits."""
        long_text = "A" * 100
        result = self.validation_service.sanitize_user_input(long_text, max_length=50)
        assert len(result) == 50
        assert result == "A" * 50
    
    def test_sanitize_user_input_invalid(self):
        """Test user input sanitization with invalid inputs."""
        # Not a string
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.sanitize_user_input(123)
        assert exc_info.value.code == ErrorCode.INVALID_DATA
        
        # Empty after sanitization
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.sanitize_user_input("   ")
        assert exc_info.value.code == ErrorCode.EMPTY_RESPONSE
    
    def test_validate_text_integrity(self):
        """Test text integrity validation."""
        valid_text = "Clean text input"
        result = self.validation_service.validate_text_integrity(valid_text)
        # Should be HTML escaped
        assert result == "Clean text input"
        
        # Test HTML escaping
        html_text = "<script>alert('test')</script>"
        with pytest.raises(ValidationError) as exc_info:
            self.validation_service.validate_text_integrity(html_text)
        assert exc_info.value.code == ErrorCode.INJECTION_ATTEMPT