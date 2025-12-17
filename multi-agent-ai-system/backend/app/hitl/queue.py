from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
import uuid

from app.database import SessionLocal
from app.hitl.models import ReviewRequest, ReviewStatus
from app.hitl.gates import ApprovalGate

class ReviewQueueService:
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
        self._close_on_exit = db is None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._close_on_exit:
            self.db.close()

    def create_review_request(
        self,
        workflow_id: str,
        run_id: str,
        thread_id: str,
        step_name: str,
        gate: ApprovalGate,
        snapshot_id: str = None,
        proposed_action: Dict[str, Any] = None,
        cost_estimate: float = 0.0
    ) -> ReviewRequest:
        
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=gate.timeout_seconds)
        
        request = ReviewRequest(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            run_id=run_id,
            thread_id=thread_id,
            checkpoint_id=snapshot_id,
            agent_id=step_name, # Usually the node name
            step_name=step_name,
            status=ReviewStatus.PENDING,
            risk_level=gate.risk_level,
            proposed_action=proposed_action,
            cost_estimate_usd=cost_estimate,
            expires_at=expires_at
        )
        
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def get_review(self, review_id: str) -> Optional[ReviewRequest]:
        return self.db.query(ReviewRequest).filter(ReviewRequest.id == review_id).first()

    def list_pending_reviews(self, workflow_id: str = None) -> List[ReviewRequest]:
        query = self.db.query(ReviewRequest).filter(ReviewRequest.status == ReviewStatus.PENDING)
        if workflow_id:
            query = query.filter(ReviewRequest.workflow_id == workflow_id)
        return query.order_by(ReviewRequest.created_at.desc()).all()

    def mark_expired(self):
        # Background cleanup to mark expired requests
        now = datetime.now(timezone.utc)
        expired = self.db.query(ReviewRequest).filter(
            ReviewRequest.status == ReviewStatus.PENDING,
            ReviewRequest.expires_at < now
        ).all()
        
        for req in expired:
            req.status = ReviewStatus.EXPIRED
        
        self.db.commit()
        return len(expired)
