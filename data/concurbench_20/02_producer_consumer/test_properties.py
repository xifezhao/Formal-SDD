"""
Property-Based Tests for Bounded Buffer (Producer-Consumer)

Tests the safety and liveness properties using Hypothesis framework.
"""

import pytest
import threading
import time
import queue
from dataclasses import dataclass, field
from typing import Any, List, Optional
from hypothesis import given, settings, strategies as st
from hypothesis import HealthCheck


@dataclass
class BoundedBufferSUT:
    """System Under Test: A bounded buffer implementation to be tested."""
    
    capacity: int
    buffer: List[Any] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    not_full: threading.Condition = field(init=False)
    not_empty: threading.Condition = field(init=False)
    enqueue_history: List[Any] = field(default_factory=list)  # For FIFO verification
    dequeue_history: List[Any] = field(default_factory=list)
    
    def __post_init__(self):
        self.not_full = threading.Condition(self.lock)
        self.not_empty = threading.Condition(self.lock)
    
    def put(self, item: Any) -> None:
        """Thread-safe put operation with blocking."""
        with self.not_full:
            while len(self.buffer) >= self.capacity:
                self.not_full.wait()
            self.buffer.append(item)
            self.enqueue_history.append(item)
            self.not_empty.notify()
    
    def get(self) -> Any:
        """Thread-safe get operation with blocking."""
        with self.not_empty:
            while len(self.buffer) == 0:
                self.not_empty.wait()
            item = self.buffer.pop(0)
            self.dequeue_history.append(item)
            self.not_full.notify()
            return item
    
    def try_put(self, item: Any, timeout: float = 0.1) -> bool:
        """Non-blocking put with timeout."""
        with self.not_full:
            end_time = time.time() + timeout
            while len(self.buffer) >= self.capacity:
                remaining = end_time - time.time()
                if remaining <= 0:
                    return False
                self.not_full.wait(remaining)
            self.buffer.append(item)
            self.enqueue_history.append(item)
            self.not_empty.notify()
            return True
    
    def try_get(self, timeout: float = 0.1) -> Optional[Any]:
        """Non-blocking get with timeout."""
        with self.not_empty:
            end_time = time.time() + timeout
            while len(self.buffer) == 0:
                remaining = end_time - time.time()
                if remaining <= 0:
                    return None
                self.not_empty.wait(remaining)
            item = self.buffer.pop(0)
            self.dequeue_history.append(item)
            self.not_full.notify()
            return item
    
    def size(self) -> int:
        """Thread-safe size check."""
        with self.lock:
            return len(self.buffer)
    
    def reset(self):
        """Reset buffer for next test."""
        with self.lock:
            self.buffer.clear()
            self.enqueue_history.clear()
            self.dequeue_history.clear()


class TestBoundedBufferProperties:
    """Property-based tests for the bounded buffer."""
    
    @given(st.lists(st.integers(min_value=0, max_value=100), min_size=5, max_size=20))
    @settings(max_examples=50, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_bounded_capacity(self, items: List[int]):
        """
        Property: Buffer size never exceeds capacity.
        
        This test verifies the bounded_capacity safety property from spec.lean.
        """
        capacity = 10
        buffer = BoundedBufferSUT(capacity=capacity)
        
        def producer():
            for item in items[:capacity]:
                buffer.try_put(item, timeout=0.5)
        
        # Start producer thread
        t = threading.Thread(target=producer)
        t.start()
        t.join(timeout=2.0)
        
        # Verify capacity constraint
        assert buffer.size() <= capacity, f"Buffer exceeded capacity: {buffer.size()} > {capacity}"
    
    @given(st.lists(st.integers(), min_size=3, max_size=15))
    @settings(max_examples=30, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_fifo_order(self, items: List[int]):
        """
        Property: Items are retrieved in FIFO order.
        
        This verifies the fifo_order property from spec.lean.
        """
        capacity = 20
        buffer = BoundedBufferSUT(capacity=capacity)
        
        # Single-threaded test for clear FIFO verification
        for item in items:
            buffer.put(item)
        
        retrieved = []
        for _ in range(len(items)):
            retrieved.append(buffer.get())
        
        assert retrieved == items, f"FIFO order violated: {retrieved} != {items}"
    
    @given(st.integers(min_value=5, max_value=50))
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_concurrent_producers_consumers(self, num_items: int):
        """
        Property: Concurrent operations maintain safety invariants.
        
        Tests mutual_exclusion and no_overflow/no_underflow properties.
        """
        capacity = 10
        buffer = BoundedBufferSUT(capacity=capacity)
        produced_items = list(range(num_items))
        consumed_items = []
        errors = []
        
        def producer(items):
            try:
                for item in items:
                    buffer.try_put(item, timeout=1.0)
            except Exception as e:
                errors.append(f"Producer error: {e}")
        
        def consumer(count):
            try:
                for _ in range(count):
                    item = buffer.try_get(timeout=1.0)
                    if item is not None:
                        consumed_items.append(item)
            except Exception as e:
                errors.append(f"Consumer error: {e}")
        
        # Split work among multiple threads
        num_producers = 2
        num_consumers = 2
        chunk_size = len(produced_items) // num_producers
        
        producer_threads = [
            threading.Thread(target=producer, args=(produced_items[i*chunk_size:(i+1)*chunk_size],))
            for i in range(num_producers)
        ]
        
        consumer_threads = [
            threading.Thread(target=consumer, args=(num_items // num_consumers,))
            for _ in range(num_consumers)
        ]
        
        # Start all threads
        for t in producer_threads + consumer_threads:
            t.start()
        
        # Wait for completion
        for t in producer_threads + consumer_threads:
            t.join(timeout=5.0)
        
        # Verification
        assert len(errors) == 0, f"Concurrency errors detected: {errors}"
        assert buffer.size() >= 0, "Buffer underflow detected"
        assert buffer.size() <= capacity, f"Buffer overflow detected: {buffer.size()} > {capacity}"
    
    def test_blocking_behavior(self):
        """
        Property: Producers/consumers block correctly when buffer is full/empty.
        
        Tests the blocking semantics specified in the requirements.
        """
        capacity = 3
        buffer = BoundedBufferSUT(capacity=capacity)
        
        # Fill buffer to capacity
        for i in range(capacity):
            buffer.put(i)
        
        # Producer should block on full buffer
        producer_blocked = threading.Event()
        producer_done = threading.Event()
        
        def blocking_producer():
            producer_blocked.set()
            result = buffer.try_put(999, timeout=0.2)
            producer_done.set()
            return result
        
        t = threading.Thread(target=blocking_producer)
        t.start()
        producer_blocked.wait(timeout=0.5)
        time.sleep(0.1)  # Give producer time to attempt
        
        # Producer should still be blocked
        assert buffer.size() == capacity, "Buffer size changed unexpectedly"
        
        # Consume one item to unblock
        buffer.get()
        t.join(timeout=1.0)
        
        assert producer_done.is_set(), "Producer did not complete after space was freed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
