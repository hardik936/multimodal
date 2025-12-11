from typing import Dict, Any, Optional

# Simple static pricing table
# USD per 1M tokens
# Values are examples, adjust based on actual Groq/Provider pricing
MODEL_PRICING = {
    # Approx prices for Mixtral on Groq (often free/beta, but adding values for simulation)
    "groq/mixtral-8x7b-32768": {
        "prompt": 0.27,      # $0.27 per M
        "completion": 0.27,  # $0.27 per M
    },
    "groq/llama3-70b-8192": {
        "prompt": 0.59,
        "completion": 0.79,
    },
    "groq/llama3-8b-8192": {
        "prompt": 0.05,
        "completion": 0.10,
    },
     # Fallback generic
    "default": {
        "prompt": 0.10,
        "completion": 0.10,
    }
}

def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int, provider: str = "groq") -> float:
    """
    Calculate cost in USD based on model pricing.
    """
    key = f"{provider}/{model}"
    pricing = MODEL_PRICING.get(key)
    
    if not pricing:
        # Try to find a partial match or default
        pricing = MODEL_PRICING.get("default")
    
    if not pricing:
        return 0.0
        
    cost_prompt = (prompt_tokens / 1_000_000) * pricing["prompt"]
    cost_completion = (completion_tokens / 1_000_000) * pricing["completion"]
    
    return round(cost_prompt + cost_completion, 8)
