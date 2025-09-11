"""
Error Response Factory for LLMpostor Game

Provides standardized error and success response creation functionality.
"""

import logging
import hashlib
import json
from typing import Dict, Any, Optional

from src.core.errors import ErrorCode, ValidationError
from flask_socketio import emit

logger = logging.getLogger(__name__)


class ErrorResponseFactory:
    """Factory responsible for creating standardized error and success responses."""
    
    def __init__(self):
        """Initialize ErrorResponseFactory"""
        pass
    
    def create_success_response(self, data: Dict) -> Dict:
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
    
    def create_error_response(self, code: ErrorCode, message: str, details: Optional[Dict] = None) -> Dict:
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
    
    def emit_error(self, code: ErrorCode, message: str, details: Optional[Dict] = None):
        """
        Emit standardized error response to client.
        
        Args:
            code: Error code enum
            message: Human-readable error message
            details: Optional additional error details
        """
        error_response = self.create_error_response(code, message, details)
        
        logger.warning(f"Emitting error: {code.value} - {message}")
        emit('error', error_response)
    
    def emit_validation_error(self, error: ValidationError):
        """
        Emit validation error response to client.
        
        Args:
            error: ValidationError instance
        """
        self.emit_error(error.code, error.message, error.details)
    
    def handle_exception(self, e: Exception, context: str = "Unknown") -> tuple[ErrorCode, str]:
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
        import traceback
        logger.error(f"Unexpected exception in {context}: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        
        # Return generic internal error
        return ErrorCode.INTERNAL_ERROR, "An internal error occurred"
    
    def generate_data_checksum(self, data: Dict) -> str:
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
    
    def verify_data_checksum(self, data: Dict, expected_checksum: str) -> bool:
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
        actual_checksum = self.generate_data_checksum(data)
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
    
    def log_error_context(self, context: str, **kwargs):
        """
        Log error context for debugging.
        
        Args:
            context: Description of the context
            **kwargs: Additional context data
        """
        context_data = {k: v for k, v in kwargs.items() if v is not None}
        logger.error(f"Error context - {context}: {context_data}")