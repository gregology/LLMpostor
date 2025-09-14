"""
Core error definitions for LLMpostor Game

Provides error codes and validation exception that don't depend on other services.
"""

from enum import Enum
from typing import Dict, Optional


class ErrorCode(Enum):
    """Standardized error codes for the application."""
    
    # Connection and Authentication Errors
    INVALID_DATA = "INVALID_DATA"
    MISSING_DATA = "MISSING_DATA"
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