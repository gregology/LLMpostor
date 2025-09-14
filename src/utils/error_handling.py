"""
Error Handling Utilities

Provides common error handling patterns and utilities used across handlers.
"""

import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from src.core.errors import ErrorCode, ValidationError

logger = logging.getLogger(__name__)


def log_handler_error(handler_name: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log handler errors with consistent formatting.
    
    Args:
        handler_name: Name of the handler where error occurred
        error: Exception that occurred
        context: Optional context information
    """
    context_str = f" Context: {context}" if context else ""
    logger.error(f"Error in {handler_name}: {type(error).__name__}: {str(error)}{context_str}")


def log_handler_action(handler_name: str, action: str, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log handler actions with consistent formatting.
    
    Args:
        handler_name: Name of the handler
        action: Action being performed
        context: Optional context information
    """
    context_str = f" Context: {context}" if context else ""
    logger.info(f"{handler_name}: {action}{context_str}")


def create_standard_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create standardized success response format.
    
    Args:
        data: Response data
        
    Returns:
        Formatted success response
    """
    return {
        "success": True,
        "data": data
    }


def create_standard_error_response(code: ErrorCode, message: str, details: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Create standardized error response format.
    
    Args:
        code: Error code
        message: Error message
        details: Optional error details
        
    Returns:
        Formatted error response
    """
    return {
        "success": False,
        "error": {
            "code": code.value,
            "message": message,
            "details": details or {}
        }
    }


def handle_validation_error(error: ValidationError, handler_name: str) -> Dict[str, Any]:
    """
    Handle validation errors with consistent logging and response formatting.
    
    Args:
        error: ValidationError instance
        handler_name: Name of the handler where error occurred
        
    Returns:
        Formatted error response
    """
    log_handler_error(handler_name, error, {"error_code": error.code.value})
    return create_standard_error_response(error.code, error.message, error.details)


def handle_generic_error(error: Exception, handler_name: str) -> Dict[str, Any]:
    """
    Handle generic errors with consistent logging and response formatting.
    
    Args:
        error: Exception instance
        handler_name: Name of the handler where error occurred
        
    Returns:
        Formatted error response
    """
    log_handler_error(handler_name, error)
    
    # Map common exceptions to appropriate error codes
    error_code = ErrorCode.INTERNAL_ERROR
    error_message = "An internal error occurred"
    
    if isinstance(error, ValueError):
        error_code = ErrorCode.INVALID_DATA
        error_message = str(error)
    elif isinstance(error, KeyError):
        error_code = ErrorCode.MISSING_DATA
        error_message = f"Missing required data: {str(error)}"
    elif isinstance(error, TypeError):
        error_code = ErrorCode.INVALID_DATA
        error_message = "Invalid data type provided"
    
    return create_standard_error_response(error_code, error_message)


def with_error_logging(handler_name: str):
    """
    Decorator to add consistent error logging to handler methods.
    
    Args:
        handler_name: Name of the handler for logging
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                log_handler_action(handler_name, f"Starting {func.__name__}")
                result = func(*args, **kwargs)
                log_handler_action(handler_name, f"Completed {func.__name__}")
                return result
            except ValidationError as e:
                response = handle_validation_error(e, handler_name)
                raise e  # Re-raise for upstream handling
            except Exception as e:
                response = handle_generic_error(e, handler_name)
                raise e  # Re-raise for upstream handling
        
        return wrapper
    return decorator


def safely_execute(func: Callable, error_handler: Optional[Callable[..., Any]] = None, default_return: Any = None) -> Any:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        error_handler: Optional error handler function
        default_return: Default return value on error
        
    Returns:
        Function result or default value
    """
    try:
        return func()
    except Exception as e:
        if error_handler is not None:
            error_handler(e)
        else:
            logger.exception(f"Error in safely_execute: {e}")
        return default_return


def validate_required_fields(data: Dict[str, Any], required_fields: list, handler_name: str) -> None:
    """
    Validate that required fields are present in data.
    
    Args:
        data: Data dictionary to validate
        required_fields: List of required field names
        handler_name: Handler name for error context
        
    Raises:
        ValidationError: If required fields are missing
    """
    if not isinstance(data, dict):
        raise ValidationError(
            ErrorCode.INVALID_DATA,
            "Invalid data format - expected dictionary"
        )
    
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise ValidationError(
            ErrorCode.INVALID_DATA,
            f"Missing required fields: {', '.join(missing_fields)}"
        )


def ensure_user_session(session_info: Optional[Dict[str, Any]], handler_name: str) -> Dict[str, Any]:
    """
    Ensure user has a valid session.
    
    Args:
        session_info: Session information
        handler_name: Handler name for error context
        
    Returns:
        Valid session info
        
    Raises:
        ValidationError: If session is invalid
    """
    if not session_info:
        raise ValidationError(
            ErrorCode.NOT_IN_ROOM,
            'You are not currently in a room'
        )
    
    return session_info