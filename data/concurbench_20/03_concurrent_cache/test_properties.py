"""
Property-Based Tests for Concurrent LRU Cache

Tests safety properties including capacity bounds, key uniqueness,
read-write consistency, and LRU eviction correctness.
"""

import pytest
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from collections import OrderedDict
from hypothesis import given, settings, strategies as st
from hypothesis import HealthCheck


@dataclass
class LRUCacheSUT:
    """System Under Test: Thread-safe LRU Cache implementation."""
    
    capacity: int
    cache: OrderedDict = field(default_factory=OrderedDict)
    lock: threading.RLock = field(default_factory=threading.RLock)
    read_count: int = 0
    access_history: List[tuple] = field(default_factory=list)  # Track all accesses
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve value and update LRU order."""
        with self.lock:
            self.access_history.append(('get', key, threading.current_thread().ident))
            if key in self.cache:
                # Move to end (most recently used)
                value = self.cache.pop(key)
                self.cache[key] = value
                return value
            return None
    
    def put(self, key: str, value: Any) -> Optional[str]:
        """Insert or update entry, evicting LRU if necessary."""
        with self.lock:
            evicted = None
            self.access_history.append(('put', key, threading.current_thread().ident))
            
            if key in self.cache:
                # Update existing entry
                self.cache.pop(key)
                self.cache[key] = value
            else:
                # Check capacity and evict if needed
                if len(self.cache) >= self.capacity:
                    # Evict least recently used (first item)
                    evicted, _ = self.cache.popitem(last=False)
                self.cache[key] = value
            
            return evicted
    
    def delete(self, key: str) -> bool:
        """Remove key from cache."""
        with self.lock:
            self.access_history.append(('delete', key, threading.current_thread().ident))
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def size(self) -> int:
        """Thread-safe size check."""
        with self.lock:
            return len(self.cache)
    
    def clear(self):
        """Clear all entries."""
        with self.lock:
            self.cache.clear()
            self.access_history.clear()
    
    def get_lru_key(self) -> Optional[str]:
        """Get the least recently used key (for testing)."""
        with self.lock:
            if len(self.cache) == 0:
                return None
            # First key in OrderedDict is LRU
            return next(iter(self.cache))


class TestLRUCacheProperties:
    """Property-based tests for LRU cache."""
    
    @given(st.lists(st.tuples(st.text(min_size=1, max_size=10), st.integers()), 
                    min_size=5, max_size=30))
    @settings(max_examples=40, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_capacity_bound(self, operations: List[tuple]):
        """
        Property: Cache size never exceeds capacity.
        
        Verifies capacity_bound from spec.lean.
        """
        capacity = 10
        cache = LRUCacheSUT(capacity=capacity)
        
        for key, value in operations:
            cache.put(key, value)
            assert cache.size() <= capacity, f"Cache exceeded capacity: {cache.size()} > {capacity}"
    
    @given(st.lists(st.tuples(st.text(min_size=1, max_size=5), st.integers()),
                    min_size=10, max_size=20))
    @settings(max_examples=30, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_key_uniqueness(self, operations: List[tuple]):
        """
        Property: Each key appears at most once in cache.
        
        Verifies key_uniqueness from spec.lean.
        """
        capacity = 15
        cache = LRUCacheSUT(capacity=capacity)
        
        for key, value in operations:
            cache.put(key, value)
            
            # Count occurrences of each key
            with cache.lock:
                key_counts = {}
                for k in cache.cache.keys():
                    key_counts[k] = key_counts.get(k, 0) + 1
                
                for k, count in key_counts.items():
                    assert count == 1, f"Key {k} appears {count} times (should be 1)"
    
    @given(st.integers(min_value=3, max_value=8))
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_lru_eviction_correctness(self, capacity: int):
        """
        Property: Evicted entry is always the least recently used.
        
        Verifies lru_ordering from spec.lean.
        """
        cache = LRUCacheSUT(capacity=capacity)
        
        # Fill cache to capacity
        keys = [f"key_{i}" for i in range(capacity)]
        for key in keys:
            cache.put(key, key)
        
        # Access middle key to make it more recent
        middle_idx = capacity // 2
        cache.get(keys[middle_idx])
        
        # Insert new key, should evict keys[0] (oldest, since keys[middle_idx] was refreshed)
        evicted = cache.put("new_key", "new_value")
        
        assert evicted == keys[0], f"Wrong key evicted: {evicted} (expected {keys[0]})"
        assert cache.get(keys[middle_idx]) is not None, "Recently accessed key was evicted"
        assert cache.get("new_key") is not None, "Newly inserted key not found"
    
    @given(st.lists(st.text(min_size=1, max_size=5), min_size=10, max_size=20))
    @settings(max_examples=25, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_concurrent_read_write_safety(self, keys: List[str]):
        """
        Property: Concurrent operations preserve cache invariants.
        
        Tests read_write_mutex and atomic_updates properties.
        """
        capacity = 15
        cache = LRUCacheSUT(capacity=capacity)
        errors = []
        
        # Pre-populate cache
        for i, key in enumerate(keys[:capacity]):
            cache.put(key, i)
        
        def reader(read_keys):
            try:
                for key in read_keys:
                    value = cache.get(key)
                    # Verify no partial reads or corruption
                    if value is not None and not isinstance(value, int):
                        errors.append(f"Corrupted value read: {value}")
            except Exception as e:
                errors.append(f"Reader error: {e}")
        
        def writer(write_items):
            try:
                for key, value in write_items:
                    cache.put(key, value)
                    # Verify capacity constraint
                    if cache.size() > capacity:
                        errors.append(f"Capacity violated: {cache.size()} > {capacity}")
            except Exception as e:
                errors.append(f"Writer error: {e}")
        
        # Create concurrent reader and writer threads
        num_threads = 4
        reader_threads = [
            threading.Thread(target=reader, args=(keys[i::num_threads],))
            for i in range(num_threads // 2)
        ]
        
        writer_threads = [
            threading.Thread(target=writer, args=([(k, i) for i, k in enumerate(keys[i::num_threads])],))
            for i in range(num_threads // 2, num_threads)
        ]
        
        all_threads = reader_threads + writer_threads
        
        # Start all threads
        for t in all_threads:
            t.start()
        
        # Wait for completion
        for t in all_threads:
            t.join(timeout=3.0)
        
        # Verification
        assert len(errors) == 0, f"Concurrency errors: {errors}"
        assert cache.size() <= capacity, f"Final capacity violation: {cache.size()} > {capacity}"
    
    def test_lru_order_after_get(self):
        """
        Property: Accessing an entry moves it to most-recently-used position.
        
        Tests the LRU update mechanism.
        """
        capacity = 5
        cache = LRUCacheSUT(capacity=capacity)
        
        # Fill cache
        for i in range(capacity):
            cache.put(f"key_{i}", i)
        
        # key_0 is currently LRU
        assert cache.get_lru_key() == "key_0"
        
        # Access key_0, making it MRU
        cache.get("key_0")
        
        # Now key_1 should be LRU
        assert cache.get_lru_key() == "key_1"
        
        # Insert new item, should evict key_1
        evicted = cache.put("new_key", 999)
        assert evicted == "key_1", f"Wrong eviction: {evicted}"
        assert cache.get("key_0") is not None, "key_0 should still exist (was recently accessed)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
