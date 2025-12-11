import logging
from sqlalchemy import func
from app.database import SessionLocal
from app.versioning.models import ComparisonResult, Deployment
from app.versioning.deployer import rollback_version
from app.versioning.audit import record_audit_log

logger = logging.getLogger(__name__)

# Config
DIVERGENCE_THRESHOLD = 0.85
DIVERGENCE_WINDOW = 50
AUTO_ROLLBACK = False # Default safety

def check_divergence(workflow_id: str):
    """
    Check recent comparisons for divergence.
    Trigger alert or rollback if threshold exceeded.
    """
    db = SessionLocal()
    try:
        # Get recent N comparisons
        recent_comparisons = db.query(ComparisonResult).filter(
            ComparisonResult.workflow_id == workflow_id
        ).order_by(ComparisonResult.timestamp.desc()).limit(DIVERGENCE_WINDOW).all()
        
        if not recent_comparisons:
            return
            
        # Calculate stats
        total = len(recent_comparisons)
        if total < 5: # maintain minimum sample size
            return
            
        failing_samples = [c for c in recent_comparisons if c.score < DIVERGENCE_THRESHOLD]
        failure_rate = len(failing_samples) / total
        avg_score = sum(c.score for c in recent_comparisons) / total
        
        logger.info(f"Divergence Check {workflow_id}: Avg Score={avg_score:.2f}, Failure Rate={failure_rate:.1%}")
        
        if failure_rate > 0.20: # >20% samples failing
            msg = f"Divergence detected! {len(failing_samples)}/{total} samples below threshold {DIVERGENCE_THRESHOLD}."
            logger.warning(msg)
            
            record_audit_log(workflow_id, "ALERT", msg, actor="monitor")
            
            if AUTO_ROLLBACK:
                # Find previous stable active? 
                # For now, just logging attempt, as rollback requires knowing WHAT to rollback to.
                # In v1, we stop at alerting.
                logger.error("Auto-rollback triggers would fire here (feature disabled by default).")
                
    finally:
        db.close()
