"""
Validation Service for LLMpostor Game

Provides input validation and sanitization functionality separated from error response handling.
"""

import logging
import re
import html
import json
from typing import Dict, Any, Optional

from src.core.errors import ErrorCode, ValidationError

logger = logging.getLogger(__name__)


class ValidationService:
    """Service responsible for input validation and sanitization."""
    
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
    
    # Room ID pattern: alphanumeric, hyphens, underscores
    ROOM_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    
    def __init__(self):
        """Initialize ValidationService with configuration"""
        self._config = None
    
    def get_max_response_length(self):
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
    
    def validate_room_id(self, room_id: str) -> str:
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
        
        if len(room_id) > self.MAX_ROOM_ID_LENGTH:
            raise ValidationError(
                ErrorCode.INVALID_ROOM_ID,
                f"Room ID must be {self.MAX_ROOM_ID_LENGTH} characters or less",
                {"max_length": self.MAX_ROOM_ID_LENGTH, "actual_length": len(room_id)}
            )
        
        if not self.ROOM_ID_PATTERN.match(room_id):
            raise ValidationError(
                ErrorCode.INVALID_ROOM_ID,
                "Room ID can only contain letters, numbers, hyphens, and underscores"
            )
        
        # Normalize to lowercase to prevent case sensitivity issues
        return room_id.lower()
    
    def validate_player_name(self, player_name: str) -> str:
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
        
        if len(player_name) > self.MAX_PLAYER_NAME_LENGTH:
            raise ValidationError(
                ErrorCode.PLAYER_NAME_TOO_LONG,
                f"Player name must be {self.MAX_PLAYER_NAME_LENGTH} characters or less",
                {"max_length": self.MAX_PLAYER_NAME_LENGTH, "actual_length": len(player_name)}
            )
        
        return player_name
    
    def validate_response_text(self, response_text: str) -> str:
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
        
        if len(response_text) < self.MIN_RESPONSE_LENGTH:
            raise ValidationError(
                ErrorCode.EMPTY_RESPONSE,
                "Response is too short"
            )
        
        max_length = self.get_max_response_length()
        if len(response_text) > max_length:
            raise ValidationError(
                ErrorCode.RESPONSE_TOO_LONG,
                f"Response must be {max_length} characters or less",
                {"max_length": max_length, "actual_length": len(response_text)}
            )
        
        return response_text
    
    def validate_guess_index(self, guess_index: Any, max_index: int) -> int:
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
    
    def validate_socket_data(self, data: Any, required_fields: Optional[list] = None) -> Dict:
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
    
    def validate_payload_integrity(self, data: Any) -> Dict:
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
        if len(payload_str) > self.MAX_PAYLOAD_SIZE:
            raise ValidationError(
                ErrorCode.DATA_SIZE_EXCEEDED,
                f"Payload size exceeds maximum allowed size of {self.MAX_PAYLOAD_SIZE} bytes",
                {"size": len(payload_str), "max_size": self.MAX_PAYLOAD_SIZE}
            )
        
        # Security validation
        self._scan_for_injection_attempts(data)
        
        # Data structure validation
        self._validate_data_structure(data)
        
        return data
    
    def validate_text_integrity(self, text: str, field_name: str = "text") -> str:
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
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                logger.warning(f"Injection attempt detected in {field_name}: {pattern}")
                raise ValidationError(
                    ErrorCode.INJECTION_ATTEMPT,
                    f"{field_name} contains potentially malicious content"
                )
        
        # Basic HTML escaping for safety
        sanitized_text = html.escape(text)
        
        return sanitized_text
    
    def sanitize_user_input(self, text: str, max_length: Optional[int] = None) -> str:
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
    
    def _scan_for_injection_attempts(self, data: Dict, path: str = "") -> None:
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
                self.validate_text_integrity(value, current_path)
            elif isinstance(value, dict):
                self._scan_for_injection_attempts(value, current_path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, str):
                        self.validate_text_integrity(item, f"{current_path}[{i}]")
                    elif isinstance(item, dict):
                        self._scan_for_injection_attempts(item, f"{current_path}[{i}]")
    
    def _validate_data_structure(self, data: Dict) -> None:
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