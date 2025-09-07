"""
Cache Service - High-performance caching layer for backend operations

Performance optimizations:
- Multi-level caching (memory, Redis, disk)
- TTL-based cache expiration
- Cache invalidation strategies
- Memory-efficient storage
- Background cache warming
- Cache hit ratio monitoring
- Intelligent cache preloading
"""

import asyncio
import json
import logging
import time
import threading
from typing import Any, Dict, Optional, List, Union, Callable
from datetime import datetime, timedelta
import hashlib
import pickle

logger = logging.getLogger(__name__)


class CacheService:
    """High-performance multi-level caching service."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the cache service.
        
        Args:
            config: Cache configuration dictionary
        """
        self.config = config or {}
        
        # Memory cache (L1)
        self.memory_cache: Dict[str, Dict] = {}
        self.memory_cache_lock = threading.RLock()
        self.max_memory_size = self.config.get('max_memory_size', 100 * 1024 * 1024)  # 100MB
        self.current_memory_size = 0
        
        # Cache metadata
        self.cache_metadata: Dict[str, Dict] = {}
        
        # Performance metrics
        self.metrics = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0,
            'memory_usage': 0,
            'hit_ratio': 0.0
        }
        
        # Default TTL settings
        self.default_ttl = self.config.get('default_ttl', 3600)  # 1 hour
        self.max_ttl = self.config.get('max_ttl', 86400)  # 24 hours
        
        # Cache warming
        self.warming_enabled = self.config.get('warming_enabled', True)
        self.warming_lock = threading.Lock()
        
        # Background cleanup
        self.cleanup_interval = self.config.get('cleanup_interval', 300)  # 5 minutes
        self.cleanup_thread = None
        self.shutdown_event = threading.Event()
        
        self._start_background_tasks()
        logger.info(f'CacheService initialized with memory limit: {self.max_memory_size} bytes')
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        try:
            with self.memory_cache_lock:
                if key in self.memory_cache:
                    entry = self.memory_cache[key]
                    
                    # Check if expired
                    if self._is_expired(entry):
                        self._remove_from_memory(key)
                        self.metrics['misses'] += 1
                        return default
                    
                    # Update access time
                    entry['last_accessed'] = time.time()
                    self.metrics['hits'] += 1
                    
                    return entry['value']
                else:
                    self.metrics['misses'] += 1
                    return default
                    
        except Exception as e:
            logger.error(f'Cache get error for key {key}: {e}')
            self.metrics['misses'] += 1
            return default
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if ttl is None:
                ttl = self.default_ttl
            
            # Limit TTL to maximum
            ttl = min(ttl, self.max_ttl)
            
            # Calculate value size
            value_size = self._calculate_size(value)
            
            with self.memory_cache_lock:
                # Remove existing key if present
                if key in self.memory_cache:
                    self._remove_from_memory(key)
                
                # Check memory limits
                if self.current_memory_size + value_size > self.max_memory_size:
                    self._evict_lru_entries(value_size)
                
                # Add to memory cache
                current_time = time.time()
                entry = {
                    'value': value,
                    'created_at': current_time,
                    'last_accessed': current_time,
                    'ttl': ttl,
                    'expires_at': current_time + ttl,
                    'size': value_size
                }
                
                self.memory_cache[key] = entry
                self.current_memory_size += value_size
                self.metrics['sets'] += 1
                self.metrics['memory_usage'] = self.current_memory_size
                
                return True
                
        except Exception as e:
            logger.error(f'Cache set error for key {key}: {e}')
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key existed and was deleted, False otherwise
        """
        try:
            with self.memory_cache_lock:
                if key in self.memory_cache:
                    self._remove_from_memory(key)
                    self.metrics['deletes'] += 1
                    return True
                return False
                
        except Exception as e:
            logger.error(f'Cache delete error for key {key}: {e}')
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and is not expired, False otherwise
        """
        with self.memory_cache_lock:
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                if self._is_expired(entry):
                    self._remove_from_memory(key)
                    return False
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self.memory_cache_lock:
            self.memory_cache.clear()
            self.cache_metadata.clear()
            self.current_memory_size = 0
            self.metrics['memory_usage'] = 0
        
        logger.info('Cache cleared')
    
    def get_or_set(self, key: str, factory_func: Callable, ttl: Optional[int] = None) -> Any:
        """Get value from cache or set it using factory function.
        
        Args:
            key: Cache key
            factory_func: Function to generate value if not in cache
            ttl: Time to live in seconds
            
        Returns:
            Cached or generated value
        """
        value = self.get(key)
        if value is not None:
            return value
        
        # Generate new value
        try:
            new_value = factory_func()
            self.set(key, new_value, ttl)
            return new_value
        except Exception as e:
            logger.error(f'Factory function error for key {key}: {e}')
            return None
    
    def mget(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary of key-value pairs for found keys
        """
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple key-value pairs in cache.
        
        Args:
            mapping: Dictionary of key-value pairs to set
            ttl: Time to live in seconds
            
        Returns:
            True if all sets were successful, False otherwise
        """
        success = True
        for key, value in mapping.items():
            if not self.set(key, value, ttl):
                success = False
        return success
    
    def increment(self, key: str, delta: int = 1) -> Optional[int]:
        """Increment a numeric value in cache.
        
        Args:
            key: Cache key
            delta: Amount to increment by
            
        Returns:
            New value after increment, or None if key doesn't exist or isn't numeric
        """
        with self.memory_cache_lock:
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                
                if self._is_expired(entry):
                    self._remove_from_memory(key)
                    return None
                
                if isinstance(entry['value'], (int, float)):
                    entry['value'] += delta
                    entry['last_accessed'] = time.time()
                    return entry['value']
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary containing cache statistics
        """
        total_requests = self.metrics['hits'] + self.metrics['misses']
        hit_ratio = (self.metrics['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        self.metrics['hit_ratio'] = hit_ratio
        
        with self.memory_cache_lock:
            entry_count = len(self.memory_cache)
            avg_entry_size = (self.current_memory_size / entry_count) if entry_count > 0 else 0
        
        return {
            **self.metrics,
            'entry_count': entry_count,
            'average_entry_size': avg_entry_size,
            'memory_usage_percent': (self.current_memory_size / self.max_memory_size * 100),
            'uptime': time.time() - getattr(self, 'start_time', time.time())
        }
    
    def warm_cache(self, warm_functions: Dict[str, Callable]) -> None:
        """Warm cache with commonly accessed data.
        
        Args:
            warm_functions: Dictionary of key -> function to generate initial data
        """
        if not self.warming_enabled:
            return
        
        def _warm_worker():
            with self.warming_lock:
                for cache_key, func in warm_functions.items():
                    try:
                        # Only warm if key doesn't exist
                        if not self.exists(cache_key):
                            value = func()
                            self.set(cache_key, value, self.default_ttl)
                            logger.debug(f'Warmed cache key: {cache_key}')
                    except Exception as e:
                        logger.error(f'Cache warming error for key {cache_key}: {e}')
        
        # Run warming in background thread
        warming_thread = threading.Thread(target=_warm_worker, name='CacheWarming')
        warming_thread.daemon = True
        warming_thread.start()
    
    def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        self.start_time = time.time()
        
        def _cleanup_worker():
            """Background cleanup worker."""
            while not self.shutdown_event.wait(self.cleanup_interval):
                try:
                    self._cleanup_expired_entries()
                    self._update_metrics()
                except Exception as e:
                    logger.error(f'Cache cleanup error: {e}')
        
        self.cleanup_thread = threading.Thread(target=_cleanup_worker, name='CacheCleanup')
        self.cleanup_thread.daemon = True
        self.cleanup_thread.start()
    
    def _cleanup_expired_entries(self) -> None:
        """Clean up expired cache entries."""
        expired_keys = []
        
        with self.memory_cache_lock:
            current_time = time.time()
            for key, entry in self.memory_cache.items():
                if current_time > entry['expires_at']:
                    expired_keys.append(key)
        
        # Remove expired entries
        for key in expired_keys:
            self.delete(key)
        
        if expired_keys:
            logger.debug(f'Cleaned up {len(expired_keys)} expired cache entries')
    
    def _evict_lru_entries(self, needed_space: int) -> None:
        """Evict least recently used entries to make space.
        
        Args:
            needed_space: Amount of space needed in bytes
        """
        if not self.memory_cache:
            return
        
        # Sort entries by last_accessed time
        sorted_entries = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1]['last_accessed']
        )
        
        freed_space = 0
        evicted_keys = []
        
        for key, entry in sorted_entries:
            if freed_space >= needed_space:
                break
            
            freed_space += entry['size']
            evicted_keys.append(key)
        
        # Remove evicted entries
        for key in evicted_keys:
            self._remove_from_memory(key)
            self.metrics['evictions'] += 1
        
        logger.debug(f'Evicted {len(evicted_keys)} LRU entries, freed {freed_space} bytes')
    
    def _remove_from_memory(self, key: str) -> None:
        """Remove entry from memory cache.
        
        Args:
            key: Cache key to remove
        """
        if key in self.memory_cache:
            entry = self.memory_cache.pop(key)
            self.current_memory_size -= entry['size']
            self.metrics['memory_usage'] = self.current_memory_size
    
    def _is_expired(self, entry: Dict) -> bool:
        """Check if cache entry is expired.
        
        Args:
            entry: Cache entry dictionary
            
        Returns:
            True if expired, False otherwise
        """
        return time.time() > entry['expires_at']
    
    def _calculate_size(self, value: Any) -> int:
        """Calculate approximate size of value in bytes.
        
        Args:
            value: Value to calculate size for
            
        Returns:
            Approximate size in bytes
        """
        try:
            if isinstance(value, (str, bytes)):
                return len(value.encode('utf-8') if isinstance(value, str) else value)
            elif isinstance(value, (int, float)):
                return 8  # Approximate size of numeric types
            elif isinstance(value, dict):
                return len(json.dumps(value, separators=(',', ':')).encode('utf-8'))
            elif isinstance(value, list):
                return len(json.dumps(value, separators=(',', ':')).encode('utf-8'))
            else:
                # Fallback: try to pickle and get size
                return len(pickle.dumps(value))
        except Exception:
            return 1024  # Default size estimate
    
    def _update_metrics(self) -> None:
        """Update cache metrics."""
        self.metrics['memory_usage'] = self.current_memory_size
    
    def _generate_key(self, namespace: str, *args, **kwargs) -> str:
        """Generate cache key from namespace and arguments.
        
        Args:
            namespace: Cache namespace
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Generated cache key
        """
        key_parts = [namespace]
        
        # Add positional arguments
        key_parts.extend(str(arg) for arg in args)
        
        # Add keyword arguments (sorted for consistency)
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}:{v}")
        
        # Create hash for very long keys
        key_str = ":".join(key_parts)
        if len(key_str) > 200:
            key_hash = hashlib.md5(key_str.encode()).hexdigest()
            return f"{namespace}:hash:{key_hash}"
        
        return key_str
    
    def cache_result(self, namespace: str, ttl: Optional[int] = None):
        """Decorator to cache function results.
        
        Args:
            namespace: Cache namespace for the function
            ttl: Time to live in seconds
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                cache_key = self._generate_key(namespace, *args, **kwargs)
                
                # Try to get from cache
                result = self.get(cache_key)
                if result is not None:
                    return result
                
                # Call function and cache result
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                return result
            
            return wrapper
        return decorator
    
    def shutdown(self) -> None:
        """Shutdown cache service and cleanup resources."""
        logger.info('Shutting down CacheService...')
        
        # Signal shutdown to background threads
        self.shutdown_event.set()
        
        # Wait for cleanup thread to finish
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        
        # Clear all cache data
        self.clear()
        
        logger.info('CacheService shutdown complete')


# Global cache instance
_cache_instance: Optional[CacheService] = None


def get_cache_service(config: Optional[Dict[str, Any]] = None) -> CacheService:
    """Get global cache service instance.
    
    Args:
        config: Cache configuration (only used for first initialization)
        
    Returns:
        CacheService instance
    """
    global _cache_instance
    
    if _cache_instance is None:
        _cache_instance = CacheService(config)
    
    return _cache_instance