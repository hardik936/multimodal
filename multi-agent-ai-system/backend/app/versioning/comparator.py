import difflib
import json
from datetime import datetime
from app.database import SessionLocal
from app.versioning.models import ComparisonResult

def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate normalized similarity score (0.0 to 1.0) using SequenceMatcher.
    Student-friendly alternative to embeddings.
    """
    if not text1 and not text2:
        return 1.0
    if not text1 or not text2:
        return 0.0
    return difflib.SequenceMatcher(None, text1, text2).ratio()

def compare_outputs(baseline_output: dict, candidate_output: dict) -> dict:
    """
    Compare two workflow outputs and return a divergence score.
    """
    score = 0.0
    details = {}
    
    # Simple strategy: Compare specific known keys or full JSON dump
    # We'll flatten to string for a rough similarity check first
    baseline_str = json.dumps(baseline_output, sort_keys=True, default=str)
    candidate_str = json.dumps(candidate_output, sort_keys=True, default=str)
    
    score = calculate_similarity(baseline_str, candidate_str)
    
    details["json_similarity"] = score
    details["baseline_keys"] = list(baseline_output.keys())
    details["candidate_keys"] = list(candidate_output.keys())
    
    return {
        "score": score,
        "details": details
    }

def record_comparison(workflow_id: str, baseline_run_id: str, candidate_run_id: str, 
                      baseline_snapshot_id: str, candidate_snapshot_id: str,
                      baseline_output: dict, candidate_output: dict):
    
    comparison = compare_outputs(baseline_output, candidate_output)
    
    db = SessionLocal()
    try:
        result = ComparisonResult(
            workflow_id=workflow_id,
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
            baseline_snapshot_id=baseline_snapshot_id,
            candidate_snapshot_id=candidate_snapshot_id,
            score=comparison["score"],
            details=json.dumps(comparison["details"]),
            timestamp=datetime.utcnow()
        )
        db.add(result)
        db.commit()
        return result
    except Exception as e:
        print(f"Failed to record comparison: {e}")
    finally:
        db.close()
