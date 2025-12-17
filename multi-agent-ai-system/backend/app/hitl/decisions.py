from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid

from app.database import SessionLocal
from app.hitl.models import ReviewRequest, ReviewDecisionRecord, ReviewDecision, ReviewStatus

class DecisionService:
    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()
        self._close_on_exit = db is None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._close_on_exit:
            self.db.close()

    def submit_decision(
        self,
        review_id: str,
        decision: ReviewDecision,
        actor: str,
        reason: str = None,
        metadata: dict = None
    ) -> ReviewRequest:
        
        request = self.db.query(ReviewRequest).filter(ReviewRequest.id == review_id).first()
        if not request:
            raise ValueError(f"Review request {review_id} not found")
        
        if request.status != ReviewStatus.PENDING:
            raise ValueError(f"Review request {review_id} is already {request.status}")

        # Create decision record
        decision_record = ReviewDecisionRecord(
            id=str(uuid.uuid4()),
            review_request_id=review_id,
            decision=decision,
            actor=actor,
            reason=reason,
            metadata_json=metadata or {}
        )
        self.db.add(decision_record)
        
        # Update request status
        if decision == ReviewDecision.APPROVE:
            request.status = ReviewStatus.APPROVED
        elif decision == ReviewDecision.REJECT:
            request.status = ReviewStatus.REJECTED
        # Request changes logic could be mapped to REJECTED or a new state
        
        request.decision_at = datetime.now(timezone.utc)
        request.decision_by = actor
        request.decision_reason = reason
        
        self.db.commit()
        self.db.refresh(request)
        
        # NOTE: The actual workflow resumption will be triggered by the caller (CLI/API)
        # calling the executor service, as we need to spin up the graph again.
        
        return request
