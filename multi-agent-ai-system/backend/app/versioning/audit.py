import logging
from app.database import SessionLocal
from app.versioning.models import AuditLog

logger = logging.getLogger(__name__)

def record_audit_log(workflow_id: str, action: str, details: str = None, actor: str = "system", snapshot_id: str = None, deployment_id: int = None):
    """
    Record an immutable audit log entry.
    """
    try:
        db = SessionLocal()
        entry = AuditLog(
            workflow_id=workflow_id,
            action=action,
            details=details,
            actor=actor,
            snapshot_id=snapshot_id,
            deployment_id=deployment_id
        )
        db.add(entry)
        db.commit()
        db.close()
        logger.info(f"AUDIT [{action}] {workflow_id}: {details}")
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
