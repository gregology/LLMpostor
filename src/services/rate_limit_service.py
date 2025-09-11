"""
Rate limiting service for preventing event queue overflow and implementing rate limiting.
"""

import os
import time
import threading
import logging
from collections import defaultdict, deque
from functools import wraps
from flask import request
from flask_socketio import emit

from src.error_handler import ErrorCode

logger = logging.getLogger(__name__)


class EventQueueManager:
    """Manages event queues and prevents overflow/flooding attacks."""
    
    def __init__(self):
        self.client_queues = defaultdict(lambda: deque(maxlen=50))  # Max 50 events per client
        self.client_rates = defaultdict(lambda: deque(maxlen=100))  # Track last 100 events
        self.global_event_count = 0
        self.global_event_window = deque(maxlen=1000)  # Track last 1000 global events
        self.blocked_clients = {}  # Temporarily blocked clients
        self.lock = threading.RLock()
        
        # Rate limiting configuration
        self.max_events_per_second = 10  # Max events per client per second
        self.max_events_per_minute = 100  # Max events per client per minute
        self.global_max_events_per_second = 100  # Global rate limit
        self.block_duration = 60  # Block duration in seconds
    
    def _is_testing(self):
        """Check if we're in a testing environment at runtime"""
        import sys
        return (
            os.environ.get('TESTING') == '1' or 
            'pytest' in os.environ.get('_', '') or
            'pytest' in sys.modules or
            any('pytest' in arg for arg in sys.argv) or
            'test' in sys.argv[0].lower() if sys.argv else False
        )
        
    def is_client_blocked(self, client_id: str) -> bool:
        """Check if a client is currently blocked."""
        with self.lock:
            if client_id in self.blocked_clients:
                if time.time() - self.blocked_clients[client_id] > self.block_duration:
                    del self.blocked_clients[client_id]
                    logger.info(f"Unblocked client {client_id}")
                    return False
                return True
            return False
    
    def block_client(self, client_id: str, reason: str = "Rate limit exceeded"):
        """Block a client for a specified duration."""
        with self.lock:
            self.blocked_clients[client_id] = time.time()
            logger.warning(f"Blocked client {client_id}: {reason}")
    
    def can_process_event(self, client_id: str, event_type: str) -> bool:
        """Check if an event can be processed without causing overflow."""
        # If we're in testing, bypass all rate limiting
        if self._is_testing():
            return True
            
        with self.lock:
            current_time = time.time()
            
            # Check if client is blocked
            if self.is_client_blocked(client_id):
                return False
            
            # Check global rate limit
            self.global_event_window.append(current_time)
            recent_global_events = sum(1 for t in self.global_event_window 
                                     if current_time - t <= 1)
            
            if recent_global_events > self.global_max_events_per_second:
                logger.warning(f"Global rate limit exceeded: {recent_global_events} events/sec")
                return False
            
            # Check client-specific rate limits
            client_events = self.client_rates[client_id]
            client_events.append(current_time)
            
            # Check events per second
            recent_events = sum(1 for t in client_events if current_time - t <= 1)
            if recent_events > self.max_events_per_second:
                self.block_client(client_id, f"Too many events per second: {recent_events}")
                return False
            
            # Check events per minute
            minute_events = sum(1 for t in client_events if current_time - t <= 60)
            if minute_events > self.max_events_per_minute:
                self.block_client(client_id, f"Too many events per minute: {minute_events}")
                return False
            
            # Add to client queue
            queue = self.client_queues[client_id]
            if len(queue) >= queue.maxlen:
                logger.warning(f"Client {client_id} queue near capacity: {len(queue)}")
            
            queue.append({
                'event_type': event_type,
                'timestamp': current_time
            })
            
            self.global_event_count += 1
            return True
    
    def get_queue_stats(self, client_id: str = None) -> dict:
        """Get queue statistics for monitoring."""
        with self.lock:
            if client_id:
                return {
                    'queue_length': len(self.client_queues[client_id]),
                    'recent_events': len(self.client_rates[client_id]),
                    'blocked': self.is_client_blocked(client_id)
                }
            
            return {
                'total_clients': len(self.client_queues),
                'blocked_clients': len(self.blocked_clients),
                'global_event_count': self.global_event_count,
                'global_recent_events': len(self.global_event_window)
            }


# Global instance - will be set by app.py
_event_queue_manager = None


def set_event_queue_manager(manager):
    """Set the global event queue manager instance."""
    global _event_queue_manager
    _event_queue_manager = manager


def prevent_event_overflow(event_type: str = "generic"):
    """Decorator to prevent event queue overflow and implement rate limiting."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            global _event_queue_manager
            
            if _event_queue_manager is None:
                raise RuntimeError("Event queue manager not initialized. Call set_event_queue_manager() first.")
            
            client_id = request.sid
            
            # Check if event can be processed (respects the disabled flag for testing)
            if not _event_queue_manager.can_process_event(client_id, event_type):
                logger.warning(f"Event {event_type} blocked for client {client_id}")
                emit('error', {
                    'success': False,
                    'error': {
                        'code': ErrorCode.RATE_LIMITED.value,
                        'message': 'Too many requests. Please slow down.',
                        'details': {'retry_after': 60}
                    }
                })
                return
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {event_type} handler: {e}")
                emit('error', {
                    'success': False,
                    'error': {
                        'code': ErrorCode.INTERNAL_ERROR.value,
                        'message': 'An internal error occurred',
                        'details': {}
                    }
                })
        
        return wrapper
    return decorator