"""
Error Handler for LLMpostor Game

Provides backward compatibility wrapper and decorator for socket handlers.
"""

import logging
from src.core.errors import ErrorCode, ValidationError
from src.services.validation_service import ValidationService
from src.services.error_response_factory import ErrorResponseFactory

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Legacy wrapper for backward compatibility during transition."""
    
    # Static method compatibility for existing code
    @staticmethod
    def validate_room_id(room_id: str) -> str:
        validation_service = ValidationService()
        return validation_service.validate_room_id(room_id)
    
    @staticmethod
    def validate_player_name(player_name: str) -> str:
        validation_service = ValidationService()
        return validation_service.validate_player_name(player_name)
    
    @staticmethod
    def validate_response_text(response_text: str) -> str:
        validation_service = ValidationService()
        return validation_service.validate_response_text(response_text)
    
    @staticmethod
    def validate_guess_index(guess_index, max_index: int) -> int:
        validation_service = ValidationService()
        return validation_service.validate_guess_index(guess_index, max_index)
    
    @staticmethod
    def validate_socket_data(data, required_fields=None):
        validation_service = ValidationService()
        return validation_service.validate_socket_data(data, required_fields)
    
    @staticmethod
    def validate_payload_integrity(data):
        validation_service = ValidationService()
        return validation_service.validate_payload_integrity(data)
    
    @staticmethod
    def validate_text_integrity(text: str, field_name: str = "text") -> str:
        validation_service = ValidationService()
        return validation_service.validate_text_integrity(text, field_name)
    
    @staticmethod
    def sanitize_user_input(text: str, max_length=None) -> str:
        validation_service = ValidationService()
        return validation_service.sanitize_user_input(text, max_length)
    
    @staticmethod
    def create_success_response(data):
        factory = ErrorResponseFactory()
        return factory.create_success_response(data)
    
    @staticmethod
    def create_error_response(code: ErrorCode, message: str, details=None):
        factory = ErrorResponseFactory()
        return factory.create_error_response(code, message, details)
    
    @staticmethod
    def emit_error(code: ErrorCode, message: str, details=None):
        factory = ErrorResponseFactory()
        return factory.emit_error(code, message, details)
    
    @staticmethod
    def emit_validation_error(error: ValidationError):
        factory = ErrorResponseFactory()
        return factory.emit_validation_error(error)
    
    @staticmethod
    def handle_exception(e: Exception, context: str = "Unknown"):
        factory = ErrorResponseFactory()
        return factory.handle_exception(e, context)
    
    @staticmethod
    def generate_data_checksum(data):
        factory = ErrorResponseFactory()
        return factory.generate_data_checksum(data)
    
    @staticmethod
    def verify_data_checksum(data, expected_checksum: str) -> bool:
        factory = ErrorResponseFactory()
        return factory.verify_data_checksum(data, expected_checksum)
    
    @staticmethod
    def log_error_context(context: str, **kwargs):
        factory = ErrorResponseFactory()
        return factory.log_error_context(context, **kwargs)


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
            factory = ErrorResponseFactory()
            factory.emit_validation_error(e)
        except Exception as e:
            factory = ErrorResponseFactory()
            error_code, error_message = factory.handle_exception(e, func.__name__)
            factory.emit_error(error_code, error_message)
    
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper