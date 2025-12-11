import time
import functools
import asyncio
import logging
import random
from typing import Type, List, Optional, Callable, Any

from app.observability.tracing import get_tracer, trace_span, add_span_attributes, set_span_error

logger = logging.getLogger(__name__)
tracer = get_tracer("reliability.retry")

def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0,
    retry_on: Optional[List[Type[Exception]]] = None,
    jitter: bool = True
):
    """
    Decorator for exponential backoff retry logic.
    
    Args:
        max_attempts: Maximum number of authentication attempts.
        initial_delay: Initial delay in seconds.
        max_delay: Maximum delay in seconds.
        backoff_factor: Multiplier for the delay.
        retry_on: List of exception types to retry on. If None, retries on all Exceptions.
        jitter: Whether to add random jitter to the delay.
    """
    if retry_on is None:
        retry_on = [Exception]
    
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                span_name = f"{func.__name__}.attempt.{attempt}"
                
                # We do not want to create a new span for every attempt if it's too noisy,
                # but the requirement says "All retries must be visible in tracing".
                # A good pattern is to add attributes to the parent span, or use events.
                # Here we'll try to execute and catch errors.
                
                try:
                    return func(*args, **kwargs)
                except tuple(retry_on) as e:
                    last_exception = e
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {str(e)}"
                    )
                    
                    if attempt == max_attempts:
                        raise e
                    
                    # Calculate delay
                    current_delay = delay
                    if jitter:
                        current_delay *= (0.5 + random.random())
                    
                    # Cap at max_delay
                    current_delay = min(current_delay, max_delay)
                    
                    time.sleep(current_delay)
                    
                    # Increase delay for next iteration
                    delay *= backoff_factor
            
            # Should not be reached if exceptions are raised cleanly
            if last_exception:
                raise last_exception
            return None

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except tuple(retry_on) as e:
                    last_exception = e
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {str(e)}"
                    )
                    
                    if attempt == max_attempts:
                        raise e
                    
                    # Calculate delay
                    current_delay = delay
                    if jitter:
                        current_delay *= (0.5 + random.random())
                    
                    # Cap at max_delay
                    current_delay = min(current_delay, max_delay)
                    
                    await asyncio.sleep(current_delay)
                    
                    # Increase delay for next iteration
                    delay *= backoff_factor
            
            if last_exception:
                raise last_exception
            return None

        return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper
    return decorator
