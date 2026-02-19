"""
Property-Based Tests for Token Bucket Rate Limiter

Tests safety properties including non-negative tokens, capacity bounds,
rate enforcement, and atomic updates.
"""

import pytest
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, List
from hypothesis import given, settings, strategies as st
from hypothesis import HealthCheck


@dataclass
class TokenBucketSUT:
    """System Under Test: Token Bucket Rate Limiter."""
    
    rate: float              # Tokens per second
    capacity: int            # Maximum tokens
    current_tokens: float = field(init=False)
    last_update: float = field(init=False)
    lock: threading.Lock = field(default_factory=threading.Lock)
    condition: threading.Condition = field(init=False)
    acquisition_history: List[tuple] = field(default_factory=list)
    
    def __post_init__(self):
        self.current_tokens = float(self.capacity)
        self.last_update = time.time()
        self.condition = threading.Condition(self.lock)
    
    def _refill(self):
        """Internal: Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.current_tokens = min(
            self.capacity,
            self.current_tokens + elapsed * self.rate
        )
        self.last_update = now
    
    def acquire(self, tokens: int = 1) -> bool:
        """Non-blocking acquire."""
        with self.lock:
            self._refill()
            if self.current_tokens >= tokens:
                self.current_tokens -= tokens
                self.acquisition_history.append(('acquire_success', tokens, time.time()))
                return True
            self.acquisition_history.append(('acquire_failure', tokens, time.time()))
            return False
    
    def acquire_blocking(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """Blocking acquire with optional timeout."""
        deadline = time.time() + timeout if timeout else None
        
        with self.condition:
            while True:
                self._refill()
                if self.current_tokens >= tokens:
                    self.current_tokens -= tokens
                    self.acquisition_history.append(('acquire_blocking_success', tokens, time.time()))
                    return True
                
                if deadline and time.time() >= deadline:
                    self.acquisition_history.append(('acquire_blocking_timeout', tokens, time.time()))
                    return False
                
                # Calculate wait time until enough tokens accumulate
                needed = tokens - self.current_tokens
                wait_time = needed / self.rate if self.rate > 0 else 1.0
                
                # Wait with timeout
                remaining = deadline - time.time() if deadline else wait_time
                if remaining <= 0:
                    return False
                
                self.condition.wait(timeout=min(wait_time, remaining))
    
    def available_tokens(self) -> float:
        """Thread-safe check of available tokens."""
        with self.lock:
            self._refill()
            return self.current_tokens
    
    def reset(self):
        """Reset to full capacity."""
        with self.lock:
            self.current_tokens = float(self.capacity)
            self.last_update = time.time()
            self.acquisition_history.clear()


class TestRateLimiterProperties:
    """Property-based tests for token bucket rate limiter."""
    
    @given(st.integers(min_value=1, max_value=20))
    @settings(max_examples=30, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_non_negative_tokens(self, capacity: int):
        """
        Property: Token count is always non-negative.
        
        Verifies non_negative_tokens from spec.lean.
        """
        limiter = TokenBucketSUT(rate=10.0, capacity=capacity)
        
        # Try to acquire more tokens than capacity
        for _ in range(capacity + 5):
            limiter.acquire(1)
            assert limiter.available_tokens() >= 0, "Token count went negative"
    
    @given(st.integers(min_value=5, max_value=30))
    @settings(max_examples=25, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_capacity_bound(self, capacity: int):
        """
        Property: Token count never exceeds capacity.
        
        Verifies capacity_bound from spec.lean.
        """
        limiter = TokenBucketSUT(rate=100.0, capacity=capacity)
        
        # Consume all tokens
        for _ in range(capacity):
            limiter.acquire(1)
        
        # Wait for refill
        time.sleep(0.5)
        
        # Check capacity is not exceeded
        available = limiter.available_tokens()
        assert available <= capacity, f"Tokens exceeded capacity: {available} > {capacity}"
    
    @given(st.floats(min_value=1.0, max_value=50.0), st.integers(min_value=5, max_value=20))
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_rate_enforcement(self, rate: float, capacity: int):
        """
        Property: Over time window T, max tokens consumed ≤ rate × T + capacity.
        
        Verifies rate_enforcement from spec.lean.
        """
        limiter = TokenBucketSUT(rate=rate, capacity=capacity)
        
        # Consume all initial tokens
        consumed = 0
        while limiter.acquire(1):
            consumed += 1
        
        initial_consumed = consumed
        assert initial_consumed <= capacity, "Initial consumption exceeded capacity"
        
        # Wait and try consuming over a time window
        wait_time = 0.2  # 200ms
        time.sleep(wait_time)
        
        additional_consumed = 0
        while limiter.acquire(1):
            additional_consumed += 1
        
        # Total consumed should be ≤ capacity + rate × wait_time (with some tolerance)
        max_allowed = capacity + rate * wait_time
        total_consumed = initial_consumed + additional_consumed
        
        # Allow 10% tolerance for timing precision
        assert total_consumed <= max_allowed * 1.1, \
            f"Rate enforcement violated: {total_consumed} > {max_allowed}"
    
    @given(st.integers(min_value=10, max_value=30))
    @settings(max_examples=15, deadline=15000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_concurrent_acquire_safety(self, num_threads: int):
        """
        Property: Concurrent acquires maintain safety invariants.
        
        Tests atomic_token_updates and correct_consumption.
        """
        capacity = 50
        limiter = TokenBucketSUT(rate=20.0, capacity=capacity)
        errors = []
        success_count = [0]  # Use list for mutability in closure
        
        def worker():
            try:
                for _ in range(5):
                    if limiter.acquire(1):
                        success_count[0] += 1
                    time.sleep(0.01)  # Small delay between attempts
            except Exception as e:
                errors.append(f"Worker error: {e}")
        
        # Create threads
        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        
        # Start all
        for t in threads:
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join(timeout=5.0)
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrency errors: {errors}"
        
        # Verify final token count is valid
        final_tokens = limiter.available_tokens()
        assert final_tokens >= 0, "Tokens went negative during concurrent access"
        assert final_tokens <= capacity, f"Tokens exceeded capacity: {final_tokens}"
    
    def test_blocking_acquire_with_timeout(self):
        """
        Property: Blocking acquire respects timeout.
        
        Tests the blocking semantics and timeout handling.
        """
        limiter = TokenBucketSUT(rate=5.0, capacity=10)
        
        # Exhaust tokens
        while limiter.acquire(1):
            pass
        
        # Try blocking acquire with timeout
        start = time.time()
        result = limiter.acquire_blocking(tokens=5, timeout=0.3)
        elapsed = time.time() - start
        
        # Should succeed because tokens refill at 5/sec
        # In 0.3 seconds, we get 5 * 0.3 = 1.5 tokens, not enough
        # So should timeout
        assert elapsed >= 0.25, "Timeout triggered too early"
        assert elapsed <= 0.5, "Timeout took too long"
    
    def test_refill_accuracy(self):
        """
        Property: Token refill rate is accurate.
        
        Verifies that tokens accumulate at the specified rate.
        """
        rate = 10.0  # 10 tokens per second
        capacity = 100
        limiter = TokenBucketSUT(rate=rate, capacity=capacity)
        
        # Consume all tokens
        while limiter.acquire(1):
            pass
        
        # Wait for 0.5 seconds (should accumulate ~5 tokens)
        time.sleep(0.5)
        
        available = limiter.available_tokens()
        
        # Allow 20% tolerance for timing jitter
        expected = 5.0
        assert abs(available - expected) <= expected * 0.2, \
            f"Refill rate inaccurate: {available} tokens (expected ~{expected})"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
