"""
Error Handler for LLMpostor Game

Provides comprehensive error handling, validation, and error response formatting.
"""

import logging
from typing import Dict, Any, Optional, Tuple, Union
from enum import Enum
from flask_socketio import emit
import traceback
import re
import json
import hashlib
import html

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """Standardized error codes for the application."""
    
    # Connection and Authentication Errors
    INVALID_DATA = "INVALID_DATA"
    MISSING_ROOM_ID = "MISSING_ROOM_ID"
    MISSING_PLAYER_NAME = "MISSING_PLAYER_NAME"
    INVALID_ROOM_ID = "INVALID_ROOM_ID"
    PLAYER_NAME_TOO_LONG = "PLAYER_NAME_TOO_LONG"
    ALREADY_IN_ROOM = "ALREADY_IN_ROOM"
    PLAYER_NAME_TAKEN = "PLAYER_NAME_TAKEN"
    NOT_IN_ROOM = "NOT_IN_ROOM"
    
    # Room Management Errors
    ROOM_NOT_FOUND = "ROOM_NOT_FOUND"
    LEAVE_FAILED = "LEAVE_FAILED"
    ROOM_FULL = "ROOM_FULL"
    INSUFFICIENT_PLAYERS = "INSUFFICIENT_PLAYERS"
    
    # Game Flow Errors
    CANNOT_START_ROUND = "CANNOT_START_ROUND"
    NO_PROMPTS_AVAILABLE = "NO_PROMPTS_AVAILABLE"
    PROMPT_ERROR = "PROMPT_ERROR"
    START_ROUND_FAILED = "START_ROUND_FAILED"
    WRONG_PHASE = "WRONG_PHASE"
    PHASE_EXPIRED = "PHASE_EXPIRED"
    
    # Response Submission Errors
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    RESPONSE_TOO_LONG = "RESPONSE_TOO_LONG"
    SUBMIT_FAILED = "SUBMIT_FAILED"
    ALREADY_SUBMITTED = "ALREADY_SUBMITTED"
    
    # Guess Submission Errors
    MISSING_GUESS = "MISSING_GUESS"
    INVALID_GUESS_FORMAT = "INVALID_GUESS_FORMAT"
    INVALID_GUESS_INDEX = "INVALID_GUESS_INDEX"
    SUBMIT_GUESS_FAILED = "SUBMIT_GUESS_FAILED"
    ALREADY_GUESSED = "ALREADY_GUESSED"
    
    # Results and Data Errors
    NO_RESULTS_AVAILABLE = "NO_RESULTS_AVAILABLE"
    DATA_CORRUPTION = "DATA_CORRUPTION"
    
    # System Errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    
    # Data Integrity Errors
    DATA_CHECKSUM_MISMATCH = "DATA_CHECKSUM_MISMATCH"
    MALFORMED_PAYLOAD = "MALFORMED_PAYLOAD"
    SUSPICIOUS_DATA_PATTERNS = "SUSPICIOUS_DATA_PATTERNS"
    DATA_SIZE_EXCEEDED = "DATA_SIZE_EXCEEDED"
    ENCODING_ERROR = "ENCODING_ERROR"
    INJECTION_ATTEMPT = "INJECTION_ATTEMPT"


class ValidationError(Exception):
    """Custom exception for validation errors."""
    
    def __init__(self, code: ErrorCode, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ErrorHandler:
    """Centralized error handling and validation."""
    
    # Validation constants
    MAX_ROOM_ID_LENGTH = 50
    MAX_PLAYER_NAME_LENGTH = 20
    MIN_RESPONSE_LENGTH = 1
    MAX_PAYLOAD_SIZE = 10240  # 10KB max payload size
    
    # Security patterns
    INJECTION_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript\s*:',  # JavaScript protocol
        r'on\w+\s*=',  # Event handlers
        r'<\s*iframe[^>]*>',  # Iframes
        r'<\s*object[^>]*>',  # Objects
        r'<\s*embed[^>]*>',  # Embeds
        r'\.\./+',  # Path traversal
        r'[;\'"]\s*(drop|delete|insert|update|create|alter)\s+',  # SQL keywords
        r'union\s+select',  # SQL union
        r'\x00',  # Null bytes
    ]
    
    def __init__(self):
        """Initialize ErrorHandler with configuration"""
        self._config = None
    
    @classmethod
    def get_max_response_length(cls):
        """Get maximum response length from configuration"""
        try:
            from config_factory import get_config
            config = get_config()
            return config.max_response_length
        except Exception:
            # Fallback to environment variable if config not available
            import os
            try:
                return int(os.environ.get('MAX_RESPONSE_LENGTH', 100))
            except (ValueError, TypeError):
                return 100
    
    # Keep backwards compatibility - this will be the default, overridden at runtime
    MAX_RESPONSE_LENGTH = 100
    
    # Room ID pattern: alphanumeric, hyphens, underscores
    ROOM_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    
    @staticmethod
    def validate_room_id(room_id: str) -> str:
        """
        Validate and sanitize room ID.
        
        Args:
            room_id: Raw room ID string
            
        Returns:
            Sanitized room ID
            
        Raises:
            ValidationError: If room ID is invalid
        """
        if not room_id or not isinstance(room_id, str):
            raise ValidationError(
                ErrorCode.MISSING_ROOM_ID,
                "Room ID is required"
            )
        
        room_id = room_id.strip()
        
        if not room_id:
            raise ValidationError(
                ErrorCode.MISSING_ROOM_ID,
                "Room ID cannot be empty"
            )
        
        if len(room_id) > ErrorHandler.MAX_ROOM_ID_LENGTH:
            raise ValidationError(
                ErrorCode.INVALID_ROOM_ID,
                f"Room ID must be {ErrorHandler.MAX_ROOM_ID_LENGTH} characters or less",
                {"max_length": ErrorHandler.MAX_ROOM_ID_LENGTH, "actual_length": len(room_id)}
            )
        
        if not ErrorHandler.ROOM_ID_PATTERN.match(room_id):
            raise ValidationError(
                ErrorCode.INVALID_ROOM_ID,
                "Room ID can only contain letters, numbers, hyphens, and underscores"
            )
        
        return room_id
    
    @staticmethod
    def validate_player_name(player_name: str) -> str:
        """
        Validate and sanitize player name.
        
        Args:
            player_name: Raw player name string
            
        Returns:
            Sanitized player name
            
        Raises:
            ValidationError: If player name is invalid
        """
        if not player_name or not isinstance(player_name, str):
            raise ValidationError(
                ErrorCode.MISSING_PLAYER_NAME,
                "Player name is required"
            )
        
        player_name = player_name.strip()
        
        if not player_name:
            raise ValidationError(
                ErrorCode.MISSING_PLAYER_NAME,
                "Player name cannot be empty"
            )
        
        if len(player_name) > ErrorHandler.MAX_PLAYER_NAME_LENGTH:
            raise ValidationError(
                ErrorCode.PLAYER_NAME_TOO_LONG,
                f"Player name must be {ErrorHandler.MAX_PLAYER_NAME_LENGTH} characters or less",
                {"max_length": ErrorHandler.MAX_PLAYER_NAME_LENGTH, "actual_length": len(player_name)}
            )
        
        return player_name
    
    @staticmethod
    def validate_response_text(response_text: str) -> str:
        """
        Validate and sanitize response text.
        
        Args:
            response_text: Raw response text
            
        Returns:
            Sanitized response text
            
        Raises:
            ValidationError: If response text is invalid
        """
        if not response_text or not isinstance(response_text, str):
            raise ValidationError(
                ErrorCode.EMPTY_RESPONSE,
                "Response cannot be empty"
            )
        
        response_text = response_text.strip()
        
        if not response_text:
            raise ValidationError(
                ErrorCode.EMPTY_RESPONSE,
                "Response cannot be empty"
            )
        
        if len(response_text) < ErrorHandler.MIN_RESPONSE_LENGTH:
            raise ValidationError(
                ErrorCode.EMPTY_RESPONSE,
                "Response is too short"
            )
        
        max_length = ErrorHandler.get_max_response_length()
        if len(response_text) > max_length:
            raise ValidationError(
                ErrorCode.RESPONSE_TOO_LONG,
                f"Response must be {max_length} characters or less",
                {"max_length": max_length, "actual_length": len(response_text)}
            )
        
        return response_text
    
    @staticmethod
    def validate_guess_index(guess_index: Any, max_index: int) -> int:
        """
        Validate guess index.
        
        Args:
            guess_index: Raw guess index value
            max_index: Maximum valid index
            
        Returns:
            Validated guess index
            
        Raises:
            ValidationError: If guess index is invalid
        """
        if guess_index is None:
            raise ValidationError(
                ErrorCode.MISSING_GUESS,
                "Guess index is required"
            )
        
        if not isinstance(guess_index, int):
            raise ValidationError(
                ErrorCode.INVALID_GUESS_FORMAT,
                "Guess index must be an integer"
            )
        
        if guess_index < 0 or guess_index >= max_index:
            raise ValidationError(
                ErrorCode.INVALID_GUESS_INDEX,
                f"Guess index must be between 0 and {max_index - 1}",
                {"min_index": 0, "max_index": max_index - 1, "provided_index": guess_index}
            )
        
        return guess_index
    
    @staticmethod
    def validate_socket_data(data: Any, required_fields: Optional[list] = None) -> Dict:
        """
        Validate Socket.IO event data.
        
        Args:
            data: Raw data from Socket.IO event
            required_fields: List of required field names
            
        Returns:
            Validated data dictionary
            
        Raises:
            ValidationError: If data is invalid
        """
        if not isinstance(data, dict):
            raise ValidationError(
                ErrorCode.INVALID_DATA,
                "Invalid data format - expected dictionary"
            )
        
        if required_fields:
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                # For specific common fields, provide more specific error codes
                if len(missing_fields) == 1:
                    field = missing_fields[0]
                    if field == 'room_id':
                        raise ValidationError(
                            ErrorCode.MISSING_ROOM_ID,
                            "Room ID is required"
                        )
                    elif field == 'player_name':
                        raise ValidationError(
                            ErrorCode.MISSING_PLAYER_NAME,
                            "Player name is required"
                        )
                    elif field == 'guess_index':
                        raise ValidationError(
                            ErrorCode.MISSING_GUESS,
                            "Guess index is required"
                        )
                
                # For multiple missing fields or other fields, use generic error
                raise ValidationError(
                    ErrorCode.INVALID_DATA,
                    f"Missing required fields: {', '.join(missing_fields)}",
                    {"missing_fields": missing_fields, "required_fields": required_fields}
                )
        
        return data
    
    @staticmethod
    def validate_payload_integrity(data: Union[str, bytes, Dict]) -> Dict:
        """
        Validate payload integrity and detect corruption/malicious content.
        
        Args:
            data: Raw payload data
            
        Returns:
            Validated and sanitized data
            
        Raises:
            ValidationError: If payload is corrupted or malicious
        """
        # Handle different input types
        if isinstance(data, (str, bytes)):
            try:
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                data = json.loads(data)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise ValidationError(
                    ErrorCode.MALFORMED_PAYLOAD,
                    f"Invalid payload format: {str(e)}"
                )
        
        if not isinstance(data, dict):
            raise ValidationError(
                ErrorCode.MALFORMED_PAYLOAD,
                "Payload must be a JSON object"
            )
        
        # Check payload size
        payload_str = json.dumps(data)
        if len(payload_str) > ErrorHandler.MAX_PAYLOAD_SIZE:
            raise ValidationError(
                ErrorCode.DATA_SIZE_EXCEEDED,
                f"Payload size exceeds maximum allowed size of {ErrorHandler.MAX_PAYLOAD_SIZE} bytes",
                {"size": len(payload_str), "max_size": ErrorHandler.MAX_PAYLOAD_SIZE}
            )
        
        # Security validation
        ErrorHandler._scan_for_injection_attempts(data)
        
        # Data structure validation
        ErrorHandler._validate_data_structure(data)
        
        return data
    
    @staticmethod
    def validate_text_integrity(text: str, field_name: str = "text") -> str:
        """
        Validate text field integrity and sanitize content.
        
        Args:
            text: Raw text content
            field_name: Name of the field for error reporting
            
        Returns:
            Sanitized text
            
        Raises:
            ValidationError: If text contains malicious content
        """
        if not isinstance(text, str):
            raise ValidationError(
                ErrorCode.INVALID_DATA,
                f"{field_name} must be a string"
            )
        
        # Check for encoding issues
        try:
            text.encode('utf-8')
        except UnicodeEncodeError:
            raise ValidationError(
                ErrorCode.ENCODING_ERROR,
                f"{field_name} contains invalid Unicode characters"
            )
        
        # Scan for injection patterns
        for pattern in ErrorHandler.INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                logger.warning(f"Injection attempt detected in {field_name}: {pattern}")
                raise ValidationError(
                    ErrorCode.INJECTION_ATTEMPT,
                    f"{field_name} contains potentially malicious content"
                )
        
        # Basic HTML escaping for safety
        sanitized_text = html.escape(text)
        
        return sanitized_text
    
    @staticmethod
    def generate_data_checksum(data: Dict) -> str:
        """
        Generate a checksum for data integrity verification.
        
        Args:
            data: Data dictionary
            
        Returns:
            SHA256 checksum hex string
        """
        # Normalize data for consistent checksums
        normalized = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    @staticmethod
    def verify_data_checksum(data: Dict, expected_checksum: str) -> bool:
        """
        Verify data integrity against expected checksum.
        
        Args:
            data: Data dictionary
            expected_checksum: Expected SHA256 checksum
            
        Returns:
            True if checksum matches, False otherwise
            
        Raises:
            ValidationError: If checksum doesn't match
        """
        actual_checksum = ErrorHandler.generate_data_checksum(data)
        if actual_checksum != expected_checksum:
            raise ValidationError(
                ErrorCode.DATA_CHECKSUM_MISMATCH,
                "Data integrity check failed - checksum mismatch",
                {
                    "expected": expected_checksum,
                    "actual": actual_checksum
                }
            )
        return True
    
    @staticmethod
    def _scan_for_injection_attempts(data: Dict, path: str = "") -> None:
        """
        Recursively scan data for injection attempts.
        
        Args:
            data: Data to scan
            path: Current path in data structure (for error reporting)
            
        Raises:
            ValidationError: If injection attempt is detected
        """
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            
            if isinstance(value, str):
                ErrorHandler.validate_text_integrity(value, current_path)
            elif isinstance(value, dict):
                ErrorHandler._scan_for_injection_attempts(value, current_path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, str):
                        ErrorHandler.validate_text_integrity(item, f"{current_path}[{i}]")
                    elif isinstance(item, dict):
                        ErrorHandler._scan_for_injection_attempts(item, f"{current_path}[{i}]")
    
    @staticmethod
    def _validate_data_structure(data: Dict) -> None:
        """
        Validate basic data structure integrity.
        
        Args:
            data: Data dictionary to validate
            
        Raises:
            ValidationError: If structure is invalid
        """
        # Check for suspicious nested depth (potential DoS via deep recursion)
        max_depth = 10
        
        def check_depth(obj, current_depth=0):
            if current_depth > max_depth:
                raise ValidationError(
                    ErrorCode.SUSPICIOUS_DATA_PATTERNS,
                    f"Data structure exceeds maximum nesting depth of {max_depth}"
                )
            
            if isinstance(obj, dict):
                for value in obj.values():
                    check_depth(value, current_depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, current_depth + 1)
        
        check_depth(data)
        
        # Check for excessive key counts (potential DoS via memory exhaustion)
        def count_keys(obj):
            if isinstance(obj, dict):
                count = len(obj)
                for value in obj.values():
                    count += count_keys(value)
                return count
            elif isinstance(obj, list):
                count = 0
                for item in obj:
                    count += count_keys(item)
                return count
            return 0
        
        total_keys = count_keys(data)
        if total_keys > 1000:  # Reasonable limit for game data
            raise ValidationError(
                ErrorCode.SUSPICIOUS_DATA_PATTERNS,
                f"Data structure contains excessive number of keys: {total_keys}"
            )
    
    @staticmethod
    def sanitize_user_input(text: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize user input with comprehensive cleaning.
        
        Args:
            text: Raw user input
            max_length: Optional maximum length to enforce
            
        Returns:
            Sanitized text
            
        Raises:
            ValidationError: If input is invalid after sanitization
        """
        if not isinstance(text, str):
            raise ValidationError(
                ErrorCode.INVALID_DATA,
                "Input must be a string"
            )
        
        # Basic sanitization
        text = text.strip()
        
        # Remove null bytes and control characters (except newlines and tabs)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Length validation
        if max_length and len(text) > max_length:
            text = text[:max_length]
        
        # Final validation
        if not text:
            raise ValidationError(
                ErrorCode.EMPTY_RESPONSE,
                "Input cannot be empty after sanitization"
            )
        
        return text
    
    @staticmethod
    def emit_error(code: ErrorCode, message: str, details: Optional[Dict] = None):
        """
        Emit standardized error response to client.
        
        Args:
            code: Error code enum
            message: Human-readable error message
            details: Optional additional error details
        """
        error_response = {
            "success": False,
            "error": {
                "code": code.value,
                "message": message,
                "details": details or {}
            }
        }
        
        logger.warning(f"Emitting error: {code.value} - {message}")
        emit('error', error_response)
    
    @staticmethod
    def emit_validation_error(error: ValidationError):
        """
        Emit validation error response to client.
        
        Args:
            error: ValidationError instance
        """
        ErrorHandler.emit_error(error.code, error.message, error.details)
    
    @staticmethod
    def handle_exception(e: Exception, context: str = "Unknown") -> Tuple[ErrorCode, str]:
        """
        Handle unexpected exceptions and return appropriate error code and message.
        
        Args:
            e: Exception instance
            context: Context where the exception occurred
            
        Returns:
            Tuple of (error_code, error_message)
        """
        if isinstance(e, ValidationError):
            return e.code, e.message
        
        # Log the full exception for debugging
        logger.error(f"Unexpected exception in {context}: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        
        # Return generic internal error
        return ErrorCode.INTERNAL_ERROR, "An internal error occurred"
    
    @staticmethod
    def create_success_response(data: Dict) -> Dict:
        """
        Create standardized success response.
        
        Args:
            data: Response data
            
        Returns:
            Standardized success response
        """
        return {
            "success": True,
            "data": data
        }
    
    @staticmethod
    def create_error_response(code: ErrorCode, message: str, details: Optional[Dict] = None) -> Dict:
        """
        Create standardized error response.
        
        Args:
            code: Error code enum
            message: Human-readable error message
            details: Optional additional error details
            
        Returns:
            Standardized error response
        """
        return {
            "success": False,
            "error": {
                "code": code.value,
                "message": message,
                "details": details or {}
            }
        }
    
    @staticmethod
    def log_error_context(context: str, **kwargs):
        """
        Log error context for debugging.
        
        Args:
            context: Description of the context
            **kwargs: Additional context data
        """
        context_data = {k: v for k, v in kwargs.items() if v is not None}
        logger.error(f"Error context - {context}: {context_data}")


def with_error_handling(func):
    """
    Decorator for Socket.IO event handlers to provide consistent error handling.
    
    Args:
        func: Socket.IO event handler function
        
    Returns:
        Wrapped function with error handling
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            ErrorHandler.emit_validation_error(e)
        except Exception as e:
            error_code, error_message = ErrorHandler.handle_exception(e, func.__name__)
            ErrorHandler.emit_error(error_code, error_message)
    
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper