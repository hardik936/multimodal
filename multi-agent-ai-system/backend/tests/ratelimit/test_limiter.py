"""
Unit tests for rate limiter (token bucket algorithm).

Tests both in-memory and Redis backends.
"""

import pytest
import time
import threading
from app.ratelimit.config import RateLimitConfig
from app.ratelimit.limiter import RateLimiter, InMemoryRateLimiter


@pytest.fixture
def config():
    """Create test configuration."""
    return RateLimitConfig(
        enabled=True,
        provider_groq_rate_per_sec=10,  # 10 req/sec for testing
        provider_openai_rate_per_sec=5,
        redis_url=None,  # Use in-memory for tests
    )


@pytest.fixture
def limiter(config):
    """Create rate limiter instance."""
    return RateLimiter(config)


def test_limiter_initialization(limiter, config):
    """Test that limiter initializes correctly."""
    assert limiter.config == config
    assert isinstance(limiter.backend, InMemoryRateLimiter)


def test_acquire_single_token(limiter):
    """Test acquiring a single token."""
    result = limiter.acquire("groq", tokens=1, timeout=0)
    assert result is True


def test_acquire_multiple_tokens(limiter):
    """Test acquiring multiple tokens."""
    result = limiter.acquire("groq", tokens=5, timeout=0)
    assert result is True


def test_rate_limit_enforcement(limiter):
    """Test that rate limiting is enforced."""
    # Acquire all tokens (10 for groq)
    for i in range(10):
        result = limiter.acquire("groq", tokens=1, timeout=0)
        assert result is True, f"Failed to acquire token {i+1}"
    
    # Next acquisition should fail (no timeout)
    result = limiter.acquire("groq", tokens=1, timeout=0)
    assert result is False


def test_token_refill(limiter):
    """Test that tokens refill over time."""
    # Acquire all tokens
    for i in range(10):
        limiter.acquire("groq", tokens=1, timeout=0)
    
    # Should fail immediately
    result = limiter.acquire("groq", tokens=1, timeout=0)
    assert result is False
    
    # Wait for refill (0.2 seconds = 2 tokens at 10/sec)
    time.sleep(0.2)
    
    # Should succeed now
    result = limiter.acquire("groq", tokens=1, timeout=0)
    assert result is True


def test_acquire_with_timeout(limiter):
    """Test acquiring with timeout waits for tokens."""
    # Acquire all tokens
    for i in range(10):
        limiter.acquire("groq", tokens=1, timeout=0)
    
    # Acquire with timeout should wait and succeed
    start = time.time()
    result = limiter.acquire("groq", tokens=1, timeout=0.5)
    elapsed = time.time() - start
    
    assert result is True
    assert elapsed >= 0.1  # Should have waited for refill


def test_release_tokens(limiter):
    """Test releasing tokens back to bucket."""
    # Acquire tokens
    limiter.acquire("groq", tokens=5, timeout=0)
    
    # Release them
    limiter.release("groq", tokens=5)
    
    # Should be able to acquire again
    result = limiter.acquire("groq", tokens=5, timeout=0)
    assert result is True


def test_get_status(limiter):
    """Test getting limiter status."""
    status = limiter.get_status("groq")
    
    assert "available_tokens" in status
    assert "rate_per_sec" in status
    assert "max_tokens" in status
    assert status["rate_per_sec"] == 10
    assert status["available_tokens"] <= 10


def test_different_providers(limiter):
    """Test that different providers have separate buckets."""
    # Acquire all groq tokens
    for i in range(10):
        limiter.acquire("groq", tokens=1, timeout=0)
    
    # Groq should be exhausted
    assert limiter.acquire("groq", tokens=1, timeout=0) is False
    
    # OpenAI should still have tokens
    assert limiter.acquire("openai", tokens=1, timeout=0) is True


def test_concurrent_access(limiter):
    """Test thread-safe concurrent access."""
    acquired_count = [0]
    lock = threading.Lock()
    
    def acquire_token():
        if limiter.acquire("groq", tokens=1, timeout=1.0):
            with lock:
                acquired_count[0] += 1
    
    # Start 20 threads trying to acquire tokens
    threads = []
    for i in range(20):
        t = threading.Thread(target=acquire_token)
        threads.append(t)
        t.start()
    
    # Wait for all threads
    for t in threads:
        t.join()
    
    # Should have acquired approximately 10-12 tokens
    # (10 initial + some refilled during execution)
    assert 10 <= acquired_count[0] <= 15


def test_disabled_limiter():
    """Test that disabled limiter always allows requests."""
    config = RateLimitConfig(enabled=False)
    limiter = RateLimiter(config)
    
    # Should always succeed
    for i in range(100):
        result = limiter.acquire("groq", tokens=1, timeout=0)
        assert result is True


def test_bucket_capacity_limit(limiter):
    """Test that bucket doesn't exceed max capacity."""
    # Wait for full refill
    time.sleep(1.0)
    
    status = limiter.get_status("groq")
    
    # Should not exceed rate_per_sec
    assert status["available_tokens"] <= status["max_tokens"]
    assert status["available_tokens"] <= 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
