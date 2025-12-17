"""
Token Bucket Rate Limiter

Implements a token bucket algorithm for rate limiting with pluggable backends:
- In-memory backend (default): Simple per-process rate limiting
- Redis backend (optional): Multi-process accurate rate limiting
"""

import time
import logging
import threading
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class RateLimiterBackend(ABC):
    """Abstract base class for rate limiter backends."""
    
    @abstractmethod
    def acquire(self, provider_name: str, tokens: int, timeout: float) -> bool:
        """
        Attempt to acquire tokens from the bucket.
        
        Args:
            provider_name: Name of the provider
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait (seconds), 0 for no wait
            
        Returns:
            True if tokens acquired, False if timeout
        """
        pass
    
    @abstractmethod
    def release(self, provider_name: str, tokens: int) -> None:
        """
        Release tokens back to the bucket (for reservation cancellation).
        
        Args:
            provider_name: Name of the provider
            tokens: Number of tokens to release
        """
        pass
    
    @abstractmethod
    def get_status(self, provider_name: str) -> Dict[str, Any]:
        """
        Get current status of the token bucket.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            Dict with keys: available_tokens, last_refill_ts, rate_per_sec
        """
        pass


class InMemoryRateLimiter(RateLimiterBackend):
    """In-memory token bucket rate limiter (per-process)."""
    
    def __init__(self, get_rate_func):
        """
        Initialize in-memory rate limiter.
        
        Args:
            get_rate_func: Function that takes provider_name and returns rate per second
        """
        self.get_rate_func = get_rate_func
        self.buckets: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
    
    def _get_or_create_bucket(self, provider_name: str) -> Dict[str, Any]:
        """Get or create a token bucket for a provider."""
        if provider_name not in self.buckets:
            rate = self.get_rate_func(provider_name)
            self.buckets[provider_name] = {
                "tokens": float(rate),  # Start with full bucket
                "rate_per_sec": rate,
                "last_refill": time.time(),
                "max_tokens": rate,  # Bucket capacity = rate per second
            }
        return self.buckets[provider_name]
    
    def _refill_tokens(self, bucket: Dict[str, Any]) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - bucket["last_refill"]
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * bucket["rate_per_sec"]
        bucket["tokens"] = min(bucket["max_tokens"], bucket["tokens"] + tokens_to_add)
        bucket["last_refill"] = now
    
    def acquire(self, provider_name: str, tokens: int = 1, timeout: float = 0.0) -> bool:
        """Acquire tokens from the bucket."""
        start_time = time.time()
        
        while True:
            with self.lock:
                bucket = self._get_or_create_bucket(provider_name)
                self._refill_tokens(bucket)
                
                if bucket["tokens"] >= tokens:
                    bucket["tokens"] -= tokens
                    return True
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                return False
            
            # Sleep briefly before retrying
            time.sleep(0.1)
    
    def release(self, provider_name: str, tokens: int = 1) -> None:
        """Release tokens back to the bucket."""
        with self.lock:
            bucket = self._get_or_create_bucket(provider_name)
            bucket["tokens"] = min(bucket["max_tokens"], bucket["tokens"] + tokens)
    
    def get_status(self, provider_name: str) -> Dict[str, Any]:
        """Get current bucket status."""
        with self.lock:
            bucket = self._get_or_create_bucket(provider_name)
            self._refill_tokens(bucket)
            
            return {
                "available_tokens": int(bucket["tokens"]),
                "last_refill_ts": bucket["last_refill"],
                "rate_per_sec": bucket["rate_per_sec"],
                "max_tokens": bucket["max_tokens"],
            }


class RedisRateLimiter(RateLimiterBackend):
    """Redis-backed token bucket rate limiter (multi-process)."""
    
    def __init__(self, redis_url: str, get_rate_func):
        """
        Initialize Redis rate limiter.
        
        Args:
            redis_url: Redis connection URL
            get_rate_func: Function that takes provider_name and returns rate per second
        """
        try:
            import redis
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.get_rate_func = get_rate_func
            logger.info(f"Redis rate limiter initialized: {redis_url}")
        except ImportError:
            raise ImportError("redis package is required for Redis backend. Install with: pip install redis")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Redis: {e}")
    
    def _get_bucket_key(self, provider_name: str) -> str:
        """Get Redis key for provider bucket."""
        return f"ratelimit:bucket:{provider_name}"
    
    def _get_or_create_bucket(self, provider_name: str) -> Dict[str, Any]:
        """Get or create bucket data from Redis."""
        key = self._get_bucket_key(provider_name)
        bucket_data = self.redis_client.hgetall(key)
        
        if not bucket_data:
            # Initialize new bucket
            rate = self.get_rate_func(provider_name)
            bucket_data = {
                "tokens": str(float(rate)),
                "rate_per_sec": str(rate),
                "last_refill": str(time.time()),
                "max_tokens": str(rate),
            }
            self.redis_client.hset(key, mapping=bucket_data)
        
        # Convert to proper types
        return {
            "tokens": float(bucket_data["tokens"]),
            "rate_per_sec": float(bucket_data["rate_per_sec"]),
            "last_refill": float(bucket_data["last_refill"]),
            "max_tokens": float(bucket_data["max_tokens"]),
        }
    
    def _refill_and_acquire(self, provider_name: str, tokens: int) -> bool:
        """Atomically refill tokens and attempt acquisition using Lua script."""
        key = self._get_bucket_key(provider_name)
        rate = self.get_rate_func(provider_name)
        
        # Lua script for atomic refill and acquire
        lua_script = """
        local key = KEYS[1]
        local tokens_requested = tonumber(ARGV[1])
        local rate_per_sec = tonumber(ARGV[2])
        local max_tokens = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        
        -- Get current bucket state
        local bucket = redis.call('HGETALL', key)
        local current_tokens, last_refill
        
        if #bucket == 0 then
            -- Initialize new bucket
            current_tokens = max_tokens
            last_refill = now
        else
            -- Parse existing bucket
            local bucket_map = {}
            for i = 1, #bucket, 2 do
                bucket_map[bucket[i]] = bucket[i + 1]
            end
            current_tokens = tonumber(bucket_map['tokens'])
            last_refill = tonumber(bucket_map['last_refill'])
        end
        
        -- Refill tokens based on elapsed time
        local elapsed = now - last_refill
        local tokens_to_add = elapsed * rate_per_sec
        current_tokens = math.min(max_tokens, current_tokens + tokens_to_add)
        
        -- Try to acquire
        if current_tokens >= tokens_requested then
            current_tokens = current_tokens - tokens_requested
            redis.call('HSET', key, 'tokens', tostring(current_tokens), 'last_refill', tostring(now), 'rate_per_sec', tostring(rate_per_sec), 'max_tokens', tostring(max_tokens))
            return 1
        else
            -- Update refill time even if acquisition failed
            redis.call('HSET', key, 'tokens', tostring(current_tokens), 'last_refill', tostring(now), 'rate_per_sec', tostring(rate_per_sec), 'max_tokens', tostring(max_tokens))
            return 0
        end
        """
        
        result = self.redis_client.eval(
            lua_script,
            1,  # Number of keys
            key,  # KEYS[1]
            tokens,  # ARGV[1]
            rate,  # ARGV[2]
            rate,  # ARGV[3] (max_tokens = rate)
            time.time()  # ARGV[4]
        )
        
        return result == 1
    
    def acquire(self, provider_name: str, tokens: int = 1, timeout: float = 0.0) -> bool:
        """Acquire tokens from Redis bucket."""
        start_time = time.time()
        
        while True:
            if self._refill_and_acquire(provider_name, tokens):
                return True
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                return False
            
            # Sleep briefly before retrying
            time.sleep(0.1)
    
    def release(self, provider_name: str, tokens: int = 1) -> None:
        """Release tokens back to Redis bucket."""
        key = self._get_bucket_key(provider_name)
        
        # Lua script for atomic release
        lua_script = """
        local key = KEYS[1]
        local tokens_to_release = tonumber(ARGV[1])
        local max_tokens = tonumber(ARGV[2])
        
        local bucket = redis.call('HGETALL', key)
        if #bucket == 0 then
            return 0
        end
        
        local bucket_map = {}
        for i = 1, #bucket, 2 do
            bucket_map[bucket[i]] = bucket[i + 1]
        end
        
        local current_tokens = tonumber(bucket_map['tokens'])
        current_tokens = math.min(max_tokens, current_tokens + tokens_to_release)
        
        redis.call('HSET', key, 'tokens', tostring(current_tokens))
        return 1
        """
        
        rate = self.get_rate_func(provider_name)
        self.redis_client.eval(lua_script, 1, key, tokens, rate)
    
    def get_status(self, provider_name: str) -> Dict[str, Any]:
        """Get current bucket status from Redis."""
        bucket = self._get_or_create_bucket(provider_name)
        
        # Refill tokens for accurate status
        now = time.time()
        elapsed = now - bucket["last_refill"]
        tokens_to_add = elapsed * bucket["rate_per_sec"]
        available = min(bucket["max_tokens"], bucket["tokens"] + tokens_to_add)
        
        return {
            "available_tokens": int(available),
            "last_refill_ts": bucket["last_refill"],
            "rate_per_sec": int(bucket["rate_per_sec"]),
            "max_tokens": int(bucket["max_tokens"]),
        }


class RateLimiter:
    """
    Main rate limiter class with pluggable backends.
    
    Automatically selects backend based on configuration:
    - Redis backend if redis_url is provided
    - In-memory backend otherwise
    """
    
    def __init__(self, config):
        """
        Initialize rate limiter with configuration.
        
        Args:
            config: RateLimitConfig instance
        """
        self.config = config
        
        # Select backend
        if config.redis_url:
            logger.info("Using Redis rate limiter backend")
            self.backend = RedisRateLimiter(
                config.redis_url,
                config.get_provider_rate
            )
        else:
            logger.info("Using in-memory rate limiter backend")
            self.backend = InMemoryRateLimiter(config.get_provider_rate)
    
    def acquire(self, provider_name: str, tokens: int = 1, timeout: float = 0.0) -> bool:
        """
        Acquire tokens for a provider.
        
        Args:
            provider_name: Name of the provider (e.g., "groq", "openai")
            tokens: Number of tokens to acquire (default: 1)
            timeout: Maximum time to wait in seconds (default: 0 = no wait)
            
        Returns:
            True if tokens acquired, False if timeout
        """
        if not self.config.enabled:
            return True
        
        return self.backend.acquire(provider_name, tokens, timeout)
    
    def release(self, provider_name: str, tokens: int = 1) -> None:
        """
        Release tokens back to the bucket.
        
        Args:
            provider_name: Name of the provider
            tokens: Number of tokens to release
        """
        if not self.config.enabled:
            return
        
        self.backend.release(provider_name, tokens)
    
    def get_status(self, provider_name: str) -> Dict[str, Any]:
        """
        Get current rate limiter status for a provider.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            Dict with status information
        """
        if not self.config.enabled:
            return {
                "available_tokens": float('inf'),
                "last_refill_ts": time.time(),
                "rate_per_sec": 0,
                "max_tokens": 0,
                "enabled": False,
            }
        
        status = self.backend.get_status(provider_name)
        status["enabled"] = True
        return status


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance.
    
    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    
    if _rate_limiter is None:
        from .config import load_rate_limit_config
        config = load_rate_limit_config()
        _rate_limiter = RateLimiter(config)
    
    return _rate_limiter


def get_redis_client():
    """
    Get Redis client for pub/sub and other features.
    Returns None if Redis is not configured.
    """
    from .config import load_rate_limit_config
    config = load_rate_limit_config()
    
    if not config.redis_url:
        return None
    
    try:
        import redis
        return redis.from_url(config.redis_url, decode_responses=True)
    except Exception as e:
        logger.warning(f"Failed to get Redis client: {e}")
        return None

