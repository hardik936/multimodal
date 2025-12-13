"""
Integration tests for provider router and failover logic.

Tests routing policies, failover behavior, and error handling.
"""

import pytest
from unittest.mock import Mock, patch
from app.ratelimit.config import RateLimitConfig
from app.ratelimit.router import ProviderRouter, ProviderRegistry, RoutingPolicy


@pytest.fixture
def config():
    """Create test configuration."""
    return RateLimitConfig(
        enabled=True,
        routing_policy="primary",
        provider_cooldown_sec=5,
    )


@pytest.fixture
def router(config):
    """Create router instance."""
    return ProviderRouter(config)


@pytest.fixture
def reset_registry():
    """Reset provider registry before each test."""
    ProviderRegistry._degraded_providers.clear()
    yield
    ProviderRegistry._degraded_providers.clear()


def test_router_initialization(router, config):
    """Test router initializes correctly."""
    assert router.config == config
    assert router.policy == RoutingPolicy.PRIMARY


def test_select_provider_primary_policy(router, reset_registry):
    """Test primary policy selects highest priority provider."""
    provider = router.select_provider()
    assert provider == "groq"  # Groq has priority 1


def test_select_provider_with_preferred(router, reset_registry):
    """Test preferred provider is used if available."""
    provider = router.select_provider(preferred_provider="openai")
    assert provider == "openai"


def test_select_provider_cost_weighted():
    """Test cost-weighted policy selects cheapest provider."""
    config = RateLimitConfig(routing_policy="cost_weighted")
    router = ProviderRouter(config)
    
    provider = router.select_provider()
    assert provider == "groq"  # Groq is cheaper


def test_select_provider_latency_weighted():
    """Test latency-weighted policy selects fastest provider."""
    config = RateLimitConfig(routing_policy="latency_weighted")
    router = ProviderRouter(config)
    
    provider = router.select_provider()
    assert provider == "groq"  # Groq is faster


def test_get_fallback_providers(router, reset_registry):
    """Test getting fallback providers excludes current provider."""
    fallbacks = router.get_fallback_providers("groq")
    
    assert "groq" not in fallbacks
    assert "openai" in fallbacks


def test_handle_provider_error_rate_limit(router, reset_registry):
    """Test handling rate limit errors."""
    error = Exception("429 Rate limit exceeded")
    
    result = router.handle_provider_error("groq", error, mark_degraded=True)
    
    assert result["is_rate_limit"] is True
    assert result["should_failover"] is True
    assert result["marked_degraded"] is True
    assert ProviderRegistry.is_degraded("groq") is True


def test_handle_provider_error_timeout(router, reset_registry):
    """Test handling timeout errors."""
    error = Exception("Request timeout")
    
    result = router.handle_provider_error("groq", error, mark_degraded=True)
    
    assert result["is_timeout"] is True
    assert result["should_failover"] is True


def test_handle_provider_error_server_error(router, reset_registry):
    """Test handling server errors."""
    error = Exception("500 Internal Server Error")
    
    result = router.handle_provider_error("groq", error, mark_degraded=True)
    
    assert result["is_server_error"] is True
    assert result["should_failover"] is True


def test_handle_provider_error_non_retryable(router, reset_registry):
    """Test handling non-retryable errors."""
    error = Exception("Invalid API key")
    
    result = router.handle_provider_error("groq", error, mark_degraded=False)
    
    assert result["should_failover"] is False
    assert ProviderRegistry.is_degraded("groq") is False


def test_provider_degraded_cooldown(router, reset_registry):
    """Test provider cooldown mechanism."""
    import time
    
    # Mark provider as degraded with 1 second cooldown
    config = RateLimitConfig(provider_cooldown_sec=1)
    router = ProviderRouter(config)
    
    error = Exception("429 Rate limit")
    router.handle_provider_error("groq", error, mark_degraded=True)
    
    # Should be degraded
    assert ProviderRegistry.is_degraded("groq") is True
    
    # Wait for cooldown
    time.sleep(1.1)
    
    # Should no longer be degraded
    assert ProviderRegistry.is_degraded("groq") is False


def test_execute_with_failover_success_first_try(router, reset_registry):
    """Test successful execution on first try."""
    mock_func = Mock(return_value="success")
    
    result = router.execute_with_failover(
        func=mock_func,
        workflow_id="test-workflow",
        max_attempts=3
    )
    
    assert result["success"] is True
    assert result["result"] == "success"
    assert result["provider"] == "groq"
    assert result["failover_count"] == 0
    assert len(result["attempts"]) == 1


def test_execute_with_failover_success_after_retry(router, reset_registry):
    """Test successful execution after failover."""
    call_count = [0]
    
    def mock_func(provider):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call fails with rate limit
            raise Exception("429 Rate limit exceeded")
        else:
            # Second call succeeds
            return f"success with {provider}"
    
    result = router.execute_with_failover(
        func=mock_func,
        workflow_id="test-workflow",
        max_attempts=3
    )
    
    assert result["success"] is True
    assert "success with" in result["result"]
    assert result["failover_count"] == 1
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["success"] is False
    assert result["attempts"][1]["success"] is True


def test_execute_with_failover_all_providers_fail(router, reset_registry):
    """Test when all providers fail."""
    mock_func = Mock(side_effect=Exception("429 Rate limit"))
    
    result = router.execute_with_failover(
        func=mock_func,
        workflow_id="test-workflow",
        max_attempts=3
    )
    
    assert result["success"] is False
    assert "All providers failed" in result["error"] or "429" in result["error"]
    assert len(result["attempts"]) >= 2  # Should have tried multiple providers


def test_execute_with_failover_non_retryable_error(router, reset_registry):
    """Test that non-retryable errors don't trigger failover."""
    mock_func = Mock(side_effect=Exception("Invalid API key"))
    
    result = router.execute_with_failover(
        func=mock_func,
        workflow_id="test-workflow",
        max_attempts=3
    )
    
    assert result["success"] is False
    assert len(result["attempts"]) == 1  # Should not retry


def test_execute_with_failover_preferred_provider(router, reset_registry):
    """Test using preferred provider."""
    mock_func = Mock(return_value="success")
    
    result = router.execute_with_failover(
        func=mock_func,
        workflow_id="test-workflow",
        preferred_provider="openai",
        max_attempts=3
    )
    
    assert result["success"] is True
    assert result["provider"] == "openai"


def test_no_available_providers(router, reset_registry):
    """Test behavior when no providers are available."""
    # Mark all providers as degraded
    ProviderRegistry.mark_degraded("groq", 60)
    ProviderRegistry.mark_degraded("openai", 60)
    
    result = router.execute_with_failover(
        func=Mock(),
        workflow_id="test-workflow",
        max_attempts=3
    )
    
    assert result["success"] is False
    assert "No available providers" in result["error"]


def test_provider_registry_get_available_providers(reset_registry):
    """Test getting available (non-degraded) providers."""
    # Initially all providers available
    available = ProviderRegistry.get_available_providers()
    assert len(available) == 2
    
    # Mark one as degraded
    ProviderRegistry.mark_degraded("groq", 60)
    
    available = ProviderRegistry.get_available_providers()
    assert len(available) == 1
    assert available[0].name == "openai"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
