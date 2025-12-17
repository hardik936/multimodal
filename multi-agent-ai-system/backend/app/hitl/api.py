from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.hitl.queue import ReviewQueueService
from app.hitl.decisions import DecisionService
from app.hitl.models import ReviewDecision, ReviewStatus
from app.auth import deps, models
from typing import Annotated

router = APIRouter()

# --- Schemas ---

class ReviewRequestResponse(BaseModel):
    id: str
    workflow_id: str
    run_id: str
    step_name: str
    status: str
    risk_level: str
    created_at: datetime
    expires_at: Optional[datetime]
    proposed_action: Optional[Dict[str, Any]]
    cost_estimate_usd: float

    class Config:
        orm_mode = True
        from_attributes = True

class DecisionPayload(BaseModel):
    reason: Optional[str] = "Decision made via Admin UI"
    actor: Optional[str] = "admin"

class DecisionResponse(BaseModel):
    status: str
    run_id: str

# --- Endpoints ---

@router.get("/reviews", response_model=List[ReviewRequestResponse])
def list_pending_reviews(
    workflow_id: Optional[str] = None, 
    db: Session = Depends(get_db),
    current_user: Annotated[models.User, Depends(deps.get_current_active_user)] = None
):
    """List all pending review requests."""
    with ReviewQueueService(db) as queue:
        return queue.list_pending_reviews(workflow_id)

@router.get("/reviews/{review_id}", response_model=ReviewRequestResponse)
def get_review_detail(
    review_id: str, 
    db: Session = Depends(get_db),
    current_user: Annotated[models.User, Depends(deps.get_current_active_user)] = None
):
    """Get details of a specific review request."""
    with ReviewQueueService(db) as queue:
        review = queue.get_review(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="Review request not found")
        return review

@router.post("/reviews/{review_id}/approve", response_model=DecisionResponse)
def approve_review(
    review_id: str, 
    payload: DecisionPayload, 
    db: Session = Depends(get_db),
    current_user: Annotated[models.User, Depends(deps.get_current_active_user)] = None
):
    """Approve a review request and resume workflow."""
    with DecisionService(db) as service:
        try:
            req = service.submit_decision(
                review_id=review_id,
                decision=ReviewDecision.APPROVE,
                actor=payload.actor,
                reason=payload.reason
            )
            
            # Trigger Resume
            # In a real app, this should probably be async or use the background task system.
            # We will enqueue the Huey task here.
            from app.tasks.huey_tasks import resume_workflow_task
            task = resume_workflow_task(req.run_id)
            
            return {"status": "approved", "run_id": req.run_id}
            
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
             raise HTTPException(status_code=500, detail=str(e))

@router.post("/reviews/{review_id}/reject", response_model=DecisionResponse)
def reject_review(
    review_id: str, 
    payload: DecisionPayload, 
    db: Session = Depends(get_db),
    current_user: Annotated[models.User, Depends(deps.get_current_active_user)] = None
):
    """Reject a review request."""
    with DecisionService(db) as service:
        try:
            req = service.submit_decision(
                review_id=review_id,
                decision=ReviewDecision.REJECT,
                actor=payload.actor,
                reason=payload.reason
            )
            
            # Ideally trigger logic to handle rejection (abort or replan)
            # For now, we also trigger resume logic which should detect rejection and finish/abort
            from app.tasks.huey_tasks import resume_workflow_task
            task = resume_workflow_task(req.run_id)

            return {"status": "rejected", "run_id": req.run_id}

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
             raise HTTPException(status_code=500, detail=str(e))
