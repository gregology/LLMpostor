"""
Concurrency Control Service for LLMpostor Game

Handles locking mechanisms and request deduplication for thread-safe operations.
Extracted from RoomManager to follow Single Responsibility Principle.
"""

import logging
import threading
import time
from contextlib import contextmanager
from typing import Dict
from src.config.game_settings import get_game_settings

logger = logging.getLogger(__name__)


class ConcurrencyControlService:
    """Manages concurrency control, locking, and request deduplication."""
    
    def __init__(self):
        # Per-room locks for fine-grained control
        self._room_locks: Dict[str, threading.RLock] = {}
        # Lock for managing room locks themselves
        self._locks_lock = threading.Lock()
        # Request deduplication
        self._recent_requests: Dict[str, float] = {}
        self.game_settings = get_game_settings()
        self._request_window = self.game_settings.request_dedup_window
    
    def get_room_lock(self, room_id: str) -> threading.RLock:
        """Get or create a lock for a specific room."""
        with self._locks_lock:
            if room_id not in self._room_locks:
                self._room_locks[room_id] = threading.RLock()
            return self._room_locks[room_id]
    
    def cleanup_room_lock(self, room_id: str):
        """Clean up lock for a deleted room."""
        with self._locks_lock:
            if room_id in self._room_locks:
                del self._room_locks[room_id]
    
    @contextmanager
    def room_operation(self, room_id: str):
        """Context manager for thread-safe room operations."""
        room_lock = self.get_room_lock(room_id)
        with room_lock:
            yield
    
    def check_duplicate_request(self, request_key: str) -> bool:
        """Check if this is a duplicate request within the time window."""
        current_time = time.time()
        
        # Clean up old requests
        expired_keys = [key for key, timestamp in self._recent_requests.items() 
                       if current_time - timestamp > self._request_window]
        for key in expired_keys:
            del self._recent_requests[key]
        
        # Check if request is duplicate
        if request_key in self._recent_requests:
            return True
        
        # Record this request
        self._recent_requests[request_key] = current_time
        return False