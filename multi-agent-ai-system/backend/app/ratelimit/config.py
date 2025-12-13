"""
Rate Limiting Configuration Module

Loads and validates rate limiting and quota management configuration
from environment variables with sensible defaults.
"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting and quota management."""
    
    # Global settings
    enabled: bool = True
    redis_url: Optional[str] = None
    
    # Provider rate limits (requests per second)
    provider_groq_rate_per_sec: int = 50
    provider_openai_rate_per_sec: int = 20
    
    # Quota settings
    quota_window_days: int = 30
    default_daily_quota_tokens: int = 100000
    quota_enforcement: str = "soft"  # soft|hard
    
    # Routing settings
    routing_policy: str = "primary"  # primary|cost_weighted|latency_weighted
    provider_cooldown_sec: int = 60
    
    # Token estimation
    default_tokens_per_request: int = 1
    
    @classmethod
    def from_env(cls) -> "RateLimitConfig":
        """Load configuration from environment variables."""
        return cls(
            enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
            redis_url=os.getenv("REDIS_URL"),
            
            provider_groq_rate_per_sec=int(os.getenv("PROVIDER_GROQ_RATE_PER_SEC", "50")),
            provider_openai_rate_per_sec=int(os.getenv("PROVIDER_OPENAI_RATE_PER_SEC", "20")),
            
            quota_window_days=int(os.getenv("QUOTA_WINDOW_DAYS", "30")),
            default_daily_quota_tokens=int(os.getenv("DEFAULT_DAILY_QUOTA_TOKENS", "100000")),
            quota_enforcement=os.getenv("QUOTA_ENFORCEMENT", "soft").lower(),
            
            routing_policy=os.getenv("ROUTING_POLICY", "primary").lower(),
            provider_cooldown_sec=int(os.getenv("PROVIDER_COOLDOWN_SEC", "60")),
            
            default_tokens_per_request=int(os.getenv("DEFAULT_TOKENS_PER_REQUEST", "1")),
        )
    
    def get_provider_rate(self, provider: str) -> int:
        """Get rate limit for a specific provider (requests per second)."""
        provider_lower = provider.lower()
        
        if provider_lower == "groq":
            return self.provider_groq_rate_per_sec
        elif provider_lower == "openai":
            return self.provider_openai_rate_per_sec
        else:
            # Default to conservative rate for unknown providers
            return 10
    
    def validate(self) -> None:
        """Validate configuration values."""
        if self.quota_enforcement not in ("soft", "hard"):
            raise ValueError(f"Invalid quota_enforcement: {self.quota_enforcement}. Must be 'soft' or 'hard'.")
        
        if self.routing_policy not in ("primary", "cost_weighted", "latency_weighted"):
            raise ValueError(f"Invalid routing_policy: {self.routing_policy}. Must be 'primary', 'cost_weighted', or 'latency_weighted'.")
        
        if self.quota_window_days <= 0:
            raise ValueError("quota_window_days must be positive")
        
        if self.provider_cooldown_sec < 0:
            raise ValueError("provider_cooldown_sec must be non-negative")


# Global configuration instance
_config: Optional[RateLimitConfig] = None


def load_rate_limit_config() -> RateLimitConfig:
    """
    Load and return the global rate limit configuration.
    
    Returns:
        RateLimitConfig instance loaded from environment variables
    """
    global _config
    
    if _config is None:
        _config = RateLimitConfig.from_env()
        _config.validate()
    
    return _config


def reload_config() -> RateLimitConfig:
    """
    Force reload configuration from environment variables.
    Useful for testing or dynamic reconfiguration.
    
    Returns:
        Newly loaded RateLimitConfig instance
    """
    global _config
    _config = RateLimitConfig.from_env()
    _config.validate()
    return _config
