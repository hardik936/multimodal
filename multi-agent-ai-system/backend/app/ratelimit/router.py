"""
Provider Router & Failover

Implements provider selection policies and automatic failover on rate limits or errors.
Integrates with circuit breaker for provider health tracking.
"""

import time
import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum

from app.reliability.circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException

logger = logging.getLogger(__name__)


class RoutingPolicy(Enum):
    """Routing policy options."""
    PRIMARY = "primary"
    COST_WEIGHTED = "cost_weighted"
    LATENCY_WEIGHTED = "latency_weighted"


@dataclass
class ProviderMetadata:
    """Metadata for a provider."""
    name: str
    priority: int  # Lower = higher priority
    cost_per_1k_tokens: float  # Approximate cost
    avg_latency_ms: float  # Approximate latency
    enabled: bool = True


class ProviderRegistry:
    """Registry of available providers with metadata."""
    
    # Default provider metadata
    PROVIDERS = {
        "groq": ProviderMetadata(
            name="groq",
            priority=1,
            cost_per_1k_tokens=0.0001,  # Very cheap
            avg_latency_ms=500,  # Fast
        ),
        "openai": ProviderMetadata(
            name="openai",
            priority=2,
            cost_per_1k_tokens=0.002,  # More expensive
            avg_latency_ms=1000,  # Slower
        ),
    }
    
    # Track degraded providers (provider_name -> cooldown_until_timestamp)
    _degraded_providers: Dict[str, float] = {}
    
    @classmethod
    def get_provider(cls, name: str) -> Optional[ProviderMetadata]:
        """Get provider metadata by name."""
        return cls.PROVIDERS.get(name.lower())
    
    @classmethod
    def get_all_providers(cls) -> List[ProviderMetadata]:
        """Get all registered providers."""
        return list(cls.PROVIDERS.values())
    
    @classmethod
    def mark_degraded(cls, provider_name: str, cooldown_sec: int):
        """Mark a provider as degraded with a cooldown period."""
        cooldown_until = time.time() + cooldown_sec
        cls._degraded_providers[provider_name] = cooldown_until
        logger.warning(f"Provider {provider_name} marked as degraded until {cooldown_until}")
    
    @classmethod
    def is_degraded(cls, provider_name: str) -> bool:
        """Check if a provider is currently degraded."""
        if provider_name not in cls._degraded_providers:
            return False
        
        cooldown_until = cls._degraded_providers[provider_name]
        if time.time() >= cooldown_until:
            # Cooldown expired, remove from degraded list
            del cls._degraded_providers[provider_name]
            logger.info(f"Provider {provider_name} cooldown expired, back to normal")
            return False
        
        return True
    
    @classmethod
    def get_available_providers(cls) -> List[ProviderMetadata]:
        """Get all non-degraded providers."""
        return [
            p for p in cls.get_all_providers()
            if p.enabled and not cls.is_degraded(p.name)
        ]


class ProviderRouter:
    """
    Routes requests to appropriate providers based on policy.
    Handles failover on rate limits and errors.
    """
    
    def __init__(self, config):
        """
        Initialize provider router.
        
        Args:
            config: RateLimitConfig instance
        """
        self.config = config
        self.policy = RoutingPolicy(config.routing_policy)
    
    def select_provider(
        self,
        workflow_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        preferred_provider: Optional[str] = None
    ) -> Optional[str]:
        """
        Select the best provider based on routing policy.
        
        Args:
            workflow_id: Workflow identifier
            tenant_id: Tenant identifier
            preferred_provider: Preferred provider (if any)
            
        Returns:
            Provider name, or None if no providers available
        """
        available = ProviderRegistry.get_available_providers()
        
        if not available:
            logger.error("No available providers")
            return None
        
        # If preferred provider is available, use it
        if preferred_provider:
            for provider in available:
                if provider.name == preferred_provider:
                    return provider.name
        
        # Apply routing policy
        if self.policy == RoutingPolicy.PRIMARY:
            # Use highest priority (lowest priority number)
            selected = min(available, key=lambda p: p.priority)
            return selected.name
        
        elif self.policy == RoutingPolicy.COST_WEIGHTED:
            # Prefer cheaper providers
            selected = min(available, key=lambda p: p.cost_per_1k_tokens)
            return selected.name
        
        elif self.policy == RoutingPolicy.LATENCY_WEIGHTED:
            # Prefer faster providers
            selected = min(available, key=lambda p: p.avg_latency_ms)
            return selected.name
        
        else:
            # Default to first available
            return available[0].name
    
    def get_fallback_providers(
        self,
        current_provider: str,
        workflow_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[str]:
        """
        Get ordered list of fallback providers.
        
        Args:
            current_provider: Current provider that failed
            workflow_id: Workflow identifier
            tenant_id: Tenant identifier
            
        Returns:
            List of provider names to try (in order)
        """
        available = ProviderRegistry.get_available_providers()
        
        # Filter out current provider
        fallbacks = [p for p in available if p.name != current_provider]
        
        # Sort by policy
        if self.policy == RoutingPolicy.PRIMARY:
            fallbacks.sort(key=lambda p: p.priority)
        elif self.policy == RoutingPolicy.COST_WEIGHTED:
            fallbacks.sort(key=lambda p: p.cost_per_1k_tokens)
        elif self.policy == RoutingPolicy.LATENCY_WEIGHTED:
            fallbacks.sort(key=lambda p: p.avg_latency_ms)
        
        return [p.name for p in fallbacks]
    
    def handle_provider_error(
        self,
        provider_name: str,
        error: Exception,
        mark_degraded: bool = True
    ) -> Dict[str, Any]:
        """
        Handle provider error and determine failover action.
        
        Args:
            provider_name: Provider that encountered error
            error: The exception that occurred
            mark_degraded: Whether to mark provider as degraded
            
        Returns:
            Dict with error info and failover recommendation
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        # Determine if error is retryable
        is_rate_limit = "429" in error_msg or "rate" in error_msg.lower()
        is_timeout = "timeout" in error_msg.lower()
        is_server_error = "500" in error_msg or "502" in error_msg or "503" in error_msg
        
        should_failover = is_rate_limit or is_timeout or is_server_error
        
        if should_failover and mark_degraded:
            ProviderRegistry.mark_degraded(provider_name, self.config.provider_cooldown_sec)
        
        return {
            "provider": provider_name,
            "error_type": error_type,
            "error_message": error_msg,
            "is_rate_limit": is_rate_limit,
            "is_timeout": is_timeout,
            "is_server_error": is_server_error,
            "should_failover": should_failover,
            "marked_degraded": should_failover and mark_degraded,
        }
    
    def execute_with_failover(
        self,
        func: Callable,
        workflow_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        max_attempts: int = 3
    ) -> Dict[str, Any]:
        """
        Execute a function with automatic provider failover.
        
        Args:
            func: Function to execute, should accept provider_name as first arg
            workflow_id: Workflow identifier
            tenant_id: Tenant identifier
            preferred_provider: Preferred provider to try first
            max_attempts: Maximum number of providers to try
            
        Returns:
            Dict with result and metadata
        """
        attempts = []
        last_error = None
        
        # Get initial provider
        provider = self.select_provider(workflow_id, tenant_id, preferred_provider)
        
        if not provider:
            return {
                "success": False,
                "error": "No available providers",
                "attempts": attempts,
            }
        
        for attempt_num in range(max_attempts):
            try:
                logger.info(f"Attempt {attempt_num + 1}/{max_attempts}: Using provider {provider}")
                
                # Execute function with selected provider
                result = func(provider)
                
                # Success!
                attempts.append({
                    "attempt": attempt_num + 1,
                    "provider": provider,
                    "success": True,
                })
                
                return {
                    "success": True,
                    "result": result,
                    "provider": provider,
                    "attempts": attempts,
                    "failover_count": attempt_num,
                }
            
            except Exception as e:
                last_error = e
                
                # Handle error and check if we should failover
                error_info = self.handle_provider_error(provider, e)
                
                attempts.append({
                    "attempt": attempt_num + 1,
                    "provider": provider,
                    "success": False,
                    "error": error_info,
                })
                
                logger.warning(
                    f"Provider {provider} failed (attempt {attempt_num + 1}): {error_info['error_message']}"
                )
                
                if not error_info["should_failover"]:
                    # Error is not retryable, fail immediately
                    break
                
                # Get fallback providers
                fallbacks = self.get_fallback_providers(provider, workflow_id, tenant_id)
                
                if not fallbacks:
                    logger.error("No fallback providers available")
                    break
                
                # Try next provider
                provider = fallbacks[0]
                logger.info(f"Failing over to provider: {provider}")
        
        # All attempts failed
        return {
            "success": False,
            "error": str(last_error) if last_error else "All providers failed",
            "attempts": attempts,
            "failover_count": len(attempts) - 1,
        }


# Global router instance
_provider_router: Optional[ProviderRouter] = None


def get_provider_router() -> ProviderRouter:
    """
    Get the global provider router instance.
    
    Returns:
        ProviderRouter instance
    """
    global _provider_router
    
    if _provider_router is None:
        from .config import load_rate_limit_config
        config = load_rate_limit_config()
        _provider_router = ProviderRouter(config)
    
    return _provider_router
