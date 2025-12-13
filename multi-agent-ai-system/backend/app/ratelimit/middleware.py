"""
Rate Limiting Middleware

High-level middleware that orchestrates rate limiting, quota checking,
provider routing, and observability for LLM calls.
"""

import time
import logging
import functools
from typing import Optional, Dict, Any, Callable

from app.observability.tracing import get_tracer, trace_span, add_span_attributes
from .config import load_rate_limit_config
from .limiter import get_rate_limiter
from .quota import get_quota_manager, QuotaExceededError
from .router import get_provider_router
from .metrics import (
    record_llm_request,
    record_rate_limited,
    record_failover,
    record_quota_exceeded,
    update_provider_tokens,
    update_quota_remaining,
    record_request_latency,
)

logger = logging.getLogger(__name__)
tracer = get_tracer("ratelimit.middleware")


class RateLimitMiddleware:
    """
    Middleware for rate limiting and quota management.
    
    Orchestrates:
    1. Rate limiting (token bucket)
    2. Quota checking
    3. Provider routing and failover
    4. Observability (tracing and metrics)
    """
    
    def __init__(self):
        """Initialize middleware with global instances."""
        self.config = load_rate_limit_config()
        self.limiter = get_rate_limiter()
        self.quota_manager = get_quota_manager()
        self.router = get_provider_router()
    
    def execute(
        self,
        func: Callable,
        workflow_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        provider_name: Optional[str] = None,
        tokens_estimate: int = 1,
        **kwargs
    ) -> Any:
        """
        Execute an LLM call with rate limiting and quota management.
        
        Args:
            func: Function to execute (should accept provider_name as first arg)
            workflow_id: Workflow identifier
            tenant_id: Tenant identifier
            provider_name: Preferred provider (optional)
            tokens_estimate: Estimated tokens for this request
            **kwargs: Additional arguments to pass to func
            
        Returns:
            Result from func
            
        Raises:
            QuotaExceededError: If quota exceeded in hard mode
            Exception: Any exception from the underlying function
        """
        start_time = time.time()
        
        with trace_span(tracer, "ratelimit.execute") as span:
            try:
                # Add initial span attributes
                if span:
                    add_span_attributes(span, {
                        "llm.workflow_id": workflow_id or "unknown",
                        "llm.tenant_id": tenant_id or "unknown",
                        "llm.tokens_estimate": tokens_estimate,
                        "llm.preferred_provider": provider_name or "auto",
                    })
                
                # Step 1: Check quota
                if span:
                    add_span_attributes(span, {"llm.quota_check": "started"})
                
                try:
                    quota_allowed = self.quota_manager.check_and_reserve(
                        workflow_id=workflow_id,
                        tenant_id=tenant_id,
                        tokens=tokens_estimate
                    )
                    
                    if span:
                        quota_status = self.quota_manager.get_quota_status(workflow_id, tenant_id)
                        add_span_attributes(span, {
                            "llm.quota.allowed": quota_allowed,
                            "llm.quota.remaining": quota_status.get("tokens_remaining", 0),
                            "llm.quota.used": quota_status.get("tokens_used", 0),
                        })
                        
                        # Update metrics
                        if quota_status.get("tokens_remaining") is not None:
                            update_quota_remaining(
                                workflow_id or "default",
                                quota_status["tokens_remaining"]
                            )
                
                except QuotaExceededError as e:
                    # Hard mode: quota exceeded
                    record_quota_exceeded(workflow_id, tenant_id)
                    
                    if span:
                        add_span_attributes(span, {
                            "llm.quota.exceeded": True,
                            "llm.quota.enforcement": "hard",
                        })
                    
                    raise
                
                # Step 2: Select provider
                selected_provider = self.router.select_provider(
                    workflow_id=workflow_id,
                    tenant_id=tenant_id,
                    preferred_provider=provider_name
                )
                
                if not selected_provider:
                    raise RuntimeError("No available providers")
                
                if span:
                    add_span_attributes(span, {
                        "llm.selected_provider": selected_provider,
                    })
                
                # Step 3: Execute with rate limiting and failover
                result = self._execute_with_rate_limit_and_failover(
                    func=func,
                    provider_name=selected_provider,
                    workflow_id=workflow_id,
                    tenant_id=tenant_id,
                    tokens_estimate=tokens_estimate,
                    span=span,
                    **kwargs
                )
                
                # Step 4: Record success metrics
                latency_ms = (time.time() - start_time) * 1000
                record_request_latency(selected_provider, latency_ms)
                
                if span:
                    add_span_attributes(span, {
                        "llm.success": True,
                        "llm.latency_ms": latency_ms,
                    })
                
                return result
            
            except Exception as e:
                if span:
                    add_span_attributes(span, {
                        "llm.success": False,
                        "llm.error": str(e),
                    })
                raise
    
    def _execute_with_rate_limit_and_failover(
        self,
        func: Callable,
        provider_name: str,
        workflow_id: Optional[str],
        tenant_id: Optional[str],
        tokens_estimate: int,
        span: Any,
        **kwargs
    ) -> Any:
        """Execute with rate limiting and automatic failover."""
        
        def execute_with_provider(provider: str) -> Any:
            """Execute function with a specific provider."""
            
            # Rate limiting
            wait_start = time.time()
            acquired = self.limiter.acquire(
                provider_name=provider,
                tokens=tokens_estimate,
                timeout=5.0  # Wait up to 5 seconds
            )
            wait_time_ms = (time.time() - wait_start) * 1000
            
            if not acquired:
                # Rate limit timeout
                record_rate_limited(provider)
                
                if span:
                    add_span_attributes(span, {
                        "llm.rate_limited": True,
                        "llm.rate_limit_provider": provider,
                    })
                
                raise RuntimeError(f"Rate limit timeout for provider {provider}")
            
            # Update metrics
            record_llm_request(provider, workflow_id)
            
            # Update provider token gauge
            limiter_status = self.limiter.get_status(provider)
            update_provider_tokens(provider, limiter_status.get("available_tokens", 0))
            
            if span:
                add_span_attributes(span, {
                    "llm.ratelimit_acquired": True,
                    "llm.ratelimit_provider": provider,
                    "llm.ratelimit_wait_ms": wait_time_ms,
                    "llm.ratelimit_available_tokens": limiter_status.get("available_tokens", 0),
                })
            
            # Execute the actual function
            try:
                return func(provider, **kwargs)
            except Exception as e:
                # Release tokens on error
                self.limiter.release(provider, tokens_estimate)
                raise
        
        # Use router's failover mechanism
        result = self.router.execute_with_failover(
            func=execute_with_provider,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            preferred_provider=provider_name,
            max_attempts=3
        )
        
        if not result["success"]:
            # All providers failed
            if span:
                add_span_attributes(span, {
                    "llm.all_providers_failed": True,
                    "llm.failover_attempts": len(result.get("attempts", [])),
                })
            
            raise RuntimeError(f"All providers failed: {result.get('error')}")
        
        # Record failover metrics
        if result.get("failover_count", 0) > 0:
            attempts = result.get("attempts", [])
            for i in range(len(attempts) - 1):
                if not attempts[i]["success"] and attempts[i + 1]["success"]:
                    record_failover(
                        attempts[i]["provider"],
                        attempts[i + 1]["provider"]
                    )
        
        if span:
            add_span_attributes(span, {
                "llm.routed_to": result["provider"],
                "llm.failover_attempts": result.get("failover_count", 0),
            })
        
        return result["result"]


# Global middleware instance
_middleware: Optional[RateLimitMiddleware] = None


def get_middleware() -> RateLimitMiddleware:
    """Get the global middleware instance."""
    global _middleware
    
    if _middleware is None:
        _middleware = RateLimitMiddleware()
    
    return _middleware


def rate_limit_middleware(func: Callable) -> Callable:
    """
    Decorator to apply rate limiting middleware to a function.
    
    The decorated function should accept provider_name as the first argument.
    
    Usage:
        @rate_limit_middleware
        def call_llm(provider_name, prompt, **kwargs):
            # Implementation
            pass
        
        # Call with metadata
        result = call_llm(
            prompt="Hello",
            workflow_id="wf-123",
            tokens_estimate=100
        )
    """
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Extract middleware parameters from kwargs
        workflow_id = kwargs.pop("workflow_id", None)
        tenant_id = kwargs.pop("tenant_id", None)
        provider_name = kwargs.pop("provider_name", None)
        tokens_estimate = kwargs.pop("tokens_estimate", 1)
        
        # Get middleware
        middleware = get_middleware()
        
        # Execute with middleware
        return middleware.execute(
            func=func,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            provider_name=provider_name,
            tokens_estimate=tokens_estimate,
            **kwargs
        )
    
    return wrapper
