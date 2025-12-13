import re
import json
from typing import Any, Dict, Union, List

def exact_match(expected: Any, actual: Any) -> float:
    """Returns 1.0 if expected == actual, else 0.0"""
    # Normalize strings for better UX? No, "exact" should be strict.
    return 1.0 if expected == actual else 0.0

def contains_match(expected: str, actual: str) -> float:
    """Returns 1.0 if expected substring is in actual string."""
    if not isinstance(actual, str) or not isinstance(expected, str):
        return 0.0
    return 1.0 if expected in actual else 0.0

def regex_match(pattern: str, actual: str) -> float:
    """Returns 1.0 if pattern is found in actual."""
    if not isinstance(actual, str):
        return 0.0
    try:
        if re.search(pattern, actual, re.MULTILINE):
            return 1.0
    except re.error:
        pass
    return 0.0

def json_key_match(expected: Dict[str, Any], actual: Union[str, Dict[str, Any]]) -> float:
    """
    Returns 1.0 if all keys/values in expected are found in actual.
    Actual can be a dict or a JSON string.
    """
    actual_dict = actual
    
    if isinstance(actual, str):
        try:
            actual_dict = json.loads(actual)
        except json.JSONDecodeError:
            return 0.0
            
    if not isinstance(actual_dict, dict):
        return 0.0
        
    for key, val in expected.items():
        if key not in actual_dict:
            return 0.0
        
        # Simple equality check for values
        # This could be recursive in valid future iterations strings
        if actual_dict[key] != val:
            # Try type coercion for numbers/strings mismatch
            if str(actual_dict[key]) != str(val):
                return 0.0
                
    return 1.0

def semantic_match(expected: str, actual: str, threshold: float = 0.85) -> float:
    """
    Student-friendly heuristic: Normalized Token Overlap (Jaccard Similarity).
    Returns score between 0.0 and 1.0. 
    Acceptance logic matches if score >= threshold, but we return the raw score.
    """
    if not isinstance(expected, str) or not isinstance(actual, str):
        return 0.0
        
    def _tokens(text):
        # Lowercase and remove punctuation simplisticly
        text = re.sub(r'[^\w\s]', '', text.lower())
        return set(text.split())
        
    set_a = _tokens(expected)
    set_b = _tokens(actual)
    
    if not set_a:
        return 1.0 if not set_b else 0.0
        
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    
    if union == 0:
        return 0.0
        
    score = intersection / union
    return score

MATCHERS = {
    "exact": exact_match,
    "contains": contains_match,
    "regex": regex_match,
    "json_key": json_key_match,
    "semantic": semantic_match
}

def run_matcher(matcher_name: str, expected: Any, actual: Any) -> float:
    matcher_func = MATCHERS.get(matcher_name, exact_match)
    return matcher_func(expected, actual)
