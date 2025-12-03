import time
import logging
import hashlib
import functools
from typing import Optional, Dict, Any, List

from groq import Groq
from langchain_groq import ChatGroq
from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Store timestamps of recent requests for rate limiting
_request_timestamps: List[float] = []

def rate_limit_groq(func):
    """
    Decorator that enforces a rate limit on Groq API calls.
    Respects settings.GROQ_RATE_LIMIT (default 70 req/min).
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global _request_timestamps
        
        # Get rate limit from settings, default to 70 if not set
        rate_limit = getattr(settings, "GROQ_RATE_LIMIT", 70)
        
        current_time = time.time()
        
        # Filter out timestamps older than 60 seconds
        _request_timestamps = [t for t in _request_timestamps if current_time - t < 60]
        
        if len(_request_timestamps) >= rate_limit:
            # Calculate sleep time
            oldest_timestamp = _request_timestamps[0]
            sleep_time = 60 - (current_time - oldest_timestamp)
            
            if sleep_time > 0:
                logger.warning(f"Groq rate limit reached ({rate_limit}/min). Sleeping for {sleep_time:.2f}s.")
                time.sleep(sleep_time)
                # Update current time after sleep
                current_time = time.time()
        
        # Record current request
        _request_timestamps.append(current_time)
        
        return func(*args, **kwargs)
    return wrapper

def get_groq_llm() -> ChatGroq:
    """
    Returns a configured ChatGroq instance.
    Raises ValueError if GROQ_API_KEY is not set.
    """
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in settings.")
        
    return ChatGroq(
        groq_api_key=settings.GROQ_API_KEY,
        model_name=settings.GROQ_MODEL,
        temperature=0.7,
        max_tokens=2000
    )

@rate_limit_groq
def call_groq_sync(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    **kwargs
) -> str:
    """
    Synchronous helper to call Groq Chat Completions API directly.
    """
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in settings.")
        
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        
        response = client.chat.completions.create(
            model=model or settings.GROQ_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error calling Groq API: {str(e)}")
        raise

def get_groq_stats() -> Dict[str, Any]:
    """
    Returns current rate limit statistics.
    """
    global _request_timestamps
    
    current_time = time.time()
    # Clean up old timestamps for accurate count
    _request_timestamps = [t for t in _request_timestamps if current_time - t < 60]
    
    rate_limit = getattr(settings, "GROQ_RATE_LIMIT", 70)
    requests_in_last_minute = len(_request_timestamps)
    remaining_requests = max(0, rate_limit - requests_in_last_minute)
    
    return {
        "requests_in_last_minute": requests_in_last_minute,
        "remaining_requests": remaining_requests,
        "rate_limit": rate_limit
    }

@functools.lru_cache(maxsize=100)
def _cached_groq_call(prompt_hash: str, prompt: str) -> str:
    """
    Internal cached helper.
    """
    return call_groq_sync(prompt)

def call_with_cache(prompt: str) -> str:
    """
    Public function to call Groq with LRU caching.
    """
    # Create stable hash of the prompt
    prompt_hash = hashlib.md5(prompt.encode("utf-8")).hexdigest()
    return _cached_groq_call(prompt_hash, prompt)
