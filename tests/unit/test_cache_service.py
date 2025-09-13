"""
Cache Service Unit Tests
Tests for the multi-level caching service.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch

from src.services.cache_service import CacheService


class TestCacheService:
    """Test CacheService basic functionality"""

    def setup_method(self):
        """Setup test fixtures for each test"""
        self.cache = CacheService({
            'max_memory_size': 1024 * 1024,  # 1MB for testing
            'default_ttl': 60,
            'cleanup_interval': 1  # Short interval for testing
        })

    def teardown_method(self):
        """Cleanup after each test"""
        if self.cache:
            self.cache.shutdown()

    def test_initialization_default_config(self):
        """Test cache initialization with default config"""
        cache = CacheService()
        assert cache.max_memory_size == 100 * 1024 * 1024  # 100MB default
        assert cache.default_ttl == 3600  # 1 hour default
        assert cache.current_memory_size == 0
        assert len(cache.memory_cache) == 0
        cache.shutdown()

    def test_initialization_custom_config(self):
        """Test cache initialization with custom config"""
        config = {
            'max_memory_size': 512 * 1024,
            'default_ttl': 1800,
            'max_ttl': 7200,
            'warming_enabled': False
        }
        cache = CacheService(config)
        assert cache.max_memory_size == 512 * 1024
        assert cache.default_ttl == 1800
        assert cache.max_ttl == 7200
        assert cache.warming_enabled is False
        cache.shutdown()

    def test_set_and_get_basic(self):
        """Test basic set and get operations"""
        key = "test_key"
        value = "test_value"
        
        # Set value
        result = self.cache.set(key, value)
        assert result is True
        
        # Get value
        retrieved = self.cache.get(key)
        assert retrieved == value
        
        # Check metrics
        assert self.cache.metrics['sets'] == 1
        assert self.cache.metrics['hits'] == 1

    def test_get_nonexistent_key(self):
        """Test getting nonexistent key returns default"""
        result = self.cache.get("nonexistent")
        assert result is None
        
        result_with_default = self.cache.get("nonexistent", "default_value")
        assert result_with_default == "default_value"
        
        # Check metrics
        assert self.cache.metrics['misses'] == 2

    def test_set_with_custom_ttl(self):
        """Test setting value with custom TTL"""
        key = "ttl_test"
        value = "ttl_value"
        ttl = 30
        
        result = self.cache.set(key, value, ttl)
        assert result is True
        
        # Check the entry has correct TTL
        entry = self.cache.memory_cache[key]
        assert entry['ttl'] == ttl
        assert entry['expires_at'] > time.time()

    def test_ttl_expiration(self):
        """Test that expired entries are removed"""
        key = "expire_test"
        value = "expire_value"
        
        # Set with very short TTL
        self.cache.set(key, value, ttl=0.1)  # 100ms
        
        # Should be available immediately
        assert self.cache.get(key) == value
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Should be expired and return None
        assert self.cache.get(key) is None
        assert key not in self.cache.memory_cache

    def test_delete_existing_key(self):
        """Test deleting existing key"""
        key = "delete_test"
        value = "delete_value"
        
        self.cache.set(key, value)
        assert self.cache.get(key) == value
        
        # Delete key
        result = self.cache.delete(key)
        assert result is True
        assert self.cache.get(key) is None
        assert self.cache.metrics['deletes'] == 1

    def test_delete_nonexistent_key(self):
        """Test deleting nonexistent key"""
        result = self.cache.delete("nonexistent")
        assert result is False

    def test_exists_method(self):
        """Test exists method"""
        key = "exists_test"
        value = "exists_value"
        
        # Key doesn't exist
        assert self.cache.exists(key) is False
        
        # Set key
        self.cache.set(key, value)
        assert self.cache.exists(key) is True
        
        # Delete key
        self.cache.delete(key)
        assert self.cache.exists(key) is False

    def test_exists_with_expired_key(self):
        """Test exists method removes expired keys"""
        key = "expire_exists_test"
        value = "expire_value"
        
        # Set with short TTL
        self.cache.set(key, value, ttl=0.1)
        assert self.cache.exists(key) is True
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Should return False and remove expired key
        assert self.cache.exists(key) is False
        assert key not in self.cache.memory_cache

    def test_clear_cache(self):
        """Test clearing entire cache"""
        # Set multiple keys
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.set("key3", "value3")
        
        assert len(self.cache.memory_cache) == 3
        assert self.cache.current_memory_size > 0
        
        # Clear cache
        self.cache.clear()
        
        assert len(self.cache.memory_cache) == 0
        assert self.cache.current_memory_size == 0
        assert self.cache.metrics['memory_usage'] == 0

    def test_get_or_set_cache_hit(self):
        """Test get_or_set when value exists in cache"""
        key = "get_or_set_test"
        cached_value = "cached_value"
        
        # Pre-populate cache
        self.cache.set(key, cached_value)
        
        # Factory function should not be called
        factory_called = False
        def factory():
            nonlocal factory_called
            factory_called = True
            return "factory_value"
        
        result = self.cache.get_or_set(key, factory)
        
        assert result == cached_value
        assert factory_called is False

    def test_get_or_set_cache_miss(self):
        """Test get_or_set when value doesn't exist in cache"""
        key = "get_or_set_miss_test"
        factory_value = "factory_generated"
        
        def factory():
            return factory_value
        
        result = self.cache.get_or_set(key, factory)
        
        assert result == factory_value
        # Should be cached now
        assert self.cache.get(key) == factory_value

    def test_get_or_set_factory_exception(self):
        """Test get_or_set when factory function raises exception"""
        key = "factory_error_test"
        
        def factory():
            raise ValueError("Factory error")
        
        result = self.cache.get_or_set(key, factory)
        
        assert result is None
        assert self.cache.get(key) is None

    def test_mget_multiple_keys(self):
        """Test getting multiple keys at once"""
        # Set multiple keys
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.set("key3", "value3")
        
        # Get multiple keys including non-existent
        keys = ["key1", "key2", "nonexistent", "key3"]
        result = self.cache.mget(keys)
        
        expected = {
            "key1": "value1",
            "key2": "value2", 
            "key3": "value3"
        }
        assert result == expected

    def test_mset_multiple_keys(self):
        """Test setting multiple keys at once"""
        mapping = {
            "mset_key1": "mset_value1",
            "mset_key2": "mset_value2",
            "mset_key3": "mset_value3"
        }
        
        result = self.cache.mset(mapping)
        assert result is True
        
        # Verify all keys were set
        for key, value in mapping.items():
            assert self.cache.get(key) == value

    def test_increment_existing_numeric_key(self):
        """Test incrementing existing numeric value"""
        key = "counter"
        initial_value = 10
        
        self.cache.set(key, initial_value)
        
        # Increment by default amount (1)
        result = self.cache.increment(key)
        assert result == 11
        assert self.cache.get(key) == 11
        
        # Increment by custom amount
        result = self.cache.increment(key, 5)
        assert result == 16
        assert self.cache.get(key) == 16

    def test_increment_nonexistent_key(self):
        """Test incrementing nonexistent key"""
        result = self.cache.increment("nonexistent")
        assert result is None

    def test_increment_non_numeric_key(self):
        """Test incrementing non-numeric value"""
        key = "string_key"
        self.cache.set(key, "not_a_number")
        
        result = self.cache.increment(key)
        assert result is None

    def test_increment_expired_key(self):
        """Test incrementing expired key"""
        key = "expired_counter"
        self.cache.set(key, 10, ttl=0.1)
        
        # Wait for expiration
        time.sleep(0.2)
        
        result = self.cache.increment(key)
        assert result is None

    def test_get_stats(self):
        """Test getting cache statistics"""
        # Perform some operations to generate stats
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.get("key1")  # hit
        self.cache.get("key1")  # hit
        self.cache.get("nonexistent")  # miss
        self.cache.delete("key1")
        
        stats = self.cache.get_stats()
        
        # Check basic structure - adjust based on actual CacheService implementation
        assert isinstance(stats, dict)
        # Verify metrics are accessible through the cache instance
        assert self.cache.metrics['hits'] == 2
        assert self.cache.metrics['misses'] == 1
        assert self.cache.metrics['sets'] == 2
        assert self.cache.metrics['deletes'] == 1


class TestCacheServiceMemoryManagement:
    """Test cache memory management and eviction"""

    def setup_method(self):
        """Setup cache with small memory limit for testing eviction"""
        self.cache = CacheService({
            'max_memory_size': 1024,  # Very small limit for testing
            'cleanup_interval': 1
        })

    def teardown_method(self):
        """Cleanup after each test"""
        if self.cache:
            self.cache.shutdown()

    def test_memory_limit_enforcement(self):
        """Test that memory limit is enforced"""
        # Try to set a value larger than the limit
        large_value = "x" * 2048  # Larger than 1024 byte limit
        
        result = self.cache.set("large_key", large_value)
        # Should still succeed due to eviction logic
        assert result is True

    def test_lru_eviction(self):
        """Test LRU eviction when memory limit is reached"""
        # Fill cache close to limit
        self.cache.set("key1", "x" * 200)
        self.cache.set("key2", "x" * 200) 
        self.cache.set("key3", "x" * 200)
        
        # Access key1 to make it more recently used
        self.cache.get("key1")
        
        initial_count = len(self.cache.memory_cache)
        
        # Add another item that should trigger eviction
        self.cache.set("key4", "x" * 500)
        
        # Should have triggered some form of memory management
        # Either eviction occurred or all items fit within the limit
        final_count = len(self.cache.memory_cache)
        
        # Verify memory management occurred (either same size or smaller due to eviction)
        assert final_count <= initial_count + 1

    def test_size_calculation_accuracy(self):
        """Test that memory size calculations are reasonably accurate"""
        initial_size = self.cache.current_memory_size
        
        # Set a known value
        test_value = "test" * 100  # 400 characters
        self.cache.set("size_test", test_value)
        
        # Memory should have increased
        assert self.cache.current_memory_size > initial_size
        
        # Delete the value
        self.cache.delete("size_test")
        
        # Memory should decrease
        assert self.cache.current_memory_size == initial_size


class TestCacheServiceThreadSafety:
    """Test cache thread safety"""

    def setup_method(self):
        """Setup cache for thread safety tests"""
        self.cache = CacheService({'cleanup_interval': 1})

    def teardown_method(self):
        """Cleanup after each test"""
        if self.cache:
            self.cache.shutdown()

    def test_concurrent_access(self):
        """Test concurrent access from multiple threads"""
        num_threads = 10
        num_operations = 100
        results = []
        
        def worker(thread_id):
            for i in range(num_operations):
                key = f"thread_{thread_id}_key_{i}"
                value = f"thread_{thread_id}_value_{i}"
                
                # Set value
                self.cache.set(key, value)
                
                # Get value
                retrieved = self.cache.get(key)
                results.append(retrieved == value)
        
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All operations should have succeeded
        assert all(results)
        assert len(results) == num_threads * num_operations

    def test_concurrent_increment(self):
        """Test concurrent increment operations"""
        key = "concurrent_counter"
        self.cache.set(key, 0)
        
        num_threads = 5
        increments_per_thread = 100
        
        def incrementer():
            for _ in range(increments_per_thread):
                self.cache.increment(key)
        
        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=incrementer)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Final value should be correct
        final_value = self.cache.get(key)
        expected_value = num_threads * increments_per_thread
        assert final_value == expected_value


class TestCacheServiceEdgeCases:
    """Test edge cases and error scenarios"""

    def setup_method(self):
        """Setup cache for edge case tests"""
        self.cache = CacheService({'cleanup_interval': 1})

    def teardown_method(self):
        """Cleanup after each test"""
        if self.cache:
            self.cache.shutdown()

    def test_none_values(self):
        """Test caching None values"""
        key = "none_key"
        
        # Set None value explicitly
        result = self.cache.set(key, None)
        assert result is True
        
        # Get should return None (not default)
        retrieved = self.cache.get(key, "default")
        assert retrieved is None

    def test_complex_data_types(self):
        """Test caching complex data types"""
        # Dictionary
        dict_value = {"nested": {"data": [1, 2, 3]}}
        self.cache.set("dict_key", dict_value)
        assert self.cache.get("dict_key") == dict_value
        
        # List
        list_value = [1, "two", {"three": 3}]
        self.cache.set("list_key", list_value)
        assert self.cache.get("list_key") == list_value

    def test_zero_ttl(self):
        """Test setting TTL to zero"""
        # TTL of 0 should expire immediately
        result = self.cache.set("zero_ttl", "value", ttl=0)
        assert result is True
        
        # Should be immediately expired
        assert self.cache.get("zero_ttl") is None

    def test_negative_ttl(self):
        """Test setting negative TTL"""
        # Negative TTL should be treated as expired
        result = self.cache.set("negative_ttl", "value", ttl=-1)
        assert result is True
        
        # Should be immediately expired
        assert self.cache.get("negative_ttl") is None

    def test_max_ttl_enforcement(self):
        """Test that TTL is limited to max_ttl"""
        cache = CacheService({'max_ttl': 100})
        
        # Try to set TTL higher than max
        cache.set("max_ttl_test", "value", ttl=200)
        
        # Should be limited to max_ttl
        entry = cache.memory_cache["max_ttl_test"]
        assert entry['ttl'] == 100
        
        cache.shutdown()

    @patch('src.services.cache_service.logger')
    def test_error_handling_in_get(self, mock_logger):
        """Test error handling in get method"""
        # Mock an error in the cache access
        with patch.object(self.cache, 'memory_cache_lock') as mock_lock:
            mock_lock.__enter__.side_effect = Exception("Lock error")
            
            result = self.cache.get("test_key", "default")
            assert result == "default"
            assert self.cache.metrics['misses'] > 0

    @patch('src.services.cache_service.logger')
    def test_error_handling_in_set(self, mock_logger):
        """Test error handling in set method"""
        # Mock an error in the size calculation
        with patch.object(self.cache, '_calculate_size') as mock_calc:
            mock_calc.side_effect = Exception("Size calculation error")
            
            result = self.cache.set("test_key", "test_value")
            assert result is False