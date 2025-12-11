from typing import List, Optional
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from app.database import SessionLocal
from app.versioning.models import Deployment, Snapshot

def get_active_deployment(workflow_id: str) -> Optional[Deployment]:
    """
    Get the currently active deployment for a workflow.
    """
    db = SessionLocal()
    try:
        return db.query(Deployment).options(joinedload(Deployment.snapshot)).filter(
            Deployment.workflow_id == workflow_id,
            Deployment.active == True,
            Deployment.role == "active"
        ).first()
    finally:
        db.close()

def get_shadow_deployment(workflow_id: str) -> Optional[Deployment]:
    """
    Get the active shadow deployment for a workflow.
    """
    db = SessionLocal()
    try:
        return db.query(Deployment).options(joinedload(Deployment.snapshot)).filter(
            Deployment.workflow_id == workflow_id,
            Deployment.active == True,
            Deployment.role == "shadow"
        ).first()
    finally:
        db.close()

def list_deployments(workflow_id: str, limit: int = 10) -> List[Deployment]:
    db = SessionLocal()
    try:
        return db.query(Deployment).filter(
            Deployment.workflow_id == workflow_id
        ).order_by(desc(Deployment.deployed_at)).limit(limit).all()
    finally:
        db.close()

def register_deployment(workflow_id: str, snapshot_id: str, role: str = "active", is_shadow: bool = False, sample_rate: float = 0.0) -> Deployment:
    db = SessionLocal()
    try:
        # If active, deactivate previous active
        if role == "active":
            db.query(Deployment).filter(
                Deployment.workflow_id == workflow_id,
                Deployment.role == "active"
            ).update({"active": False})
        
        # If shadow, deactivate previous shadow
        if role == "shadow":
            db.query(Deployment).filter(
                Deployment.workflow_id == workflow_id,
                Deployment.role == "shadow"
            ).update({"active": False})

        new_deployment = Deployment(
            workflow_id=workflow_id,
            snapshot_id=snapshot_id,
            role=role,
            is_shadow=is_shadow,
            sample_rate=sample_rate,
            active=True
        )
        db.add(new_deployment)
        db.commit()
        db.refresh(new_deployment)
        return new_deployment
    finally:
        db.close()
