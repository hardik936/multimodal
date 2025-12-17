from sqlalchemy import String, DateTime, JSON, Enum, Text, ForeignKey, Float
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional, Dict, Any, List
import enum
import uuid

from app.models.base import Base, UUIDMixin, TimestampMixin

class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class ReviewDecision(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"

class ReviewRequest(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "review_requests"

    # Core Identifiers
    workflow_id: Mapped[str] = mapped_column(String, index=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    agent_id: Mapped[str] = mapped_column(String) # e.g., "executor" or "planner"
    step_name: Mapped[str] = mapped_column(String)
    
    # State Management
    thread_id: Mapped[str] = mapped_column(String, index=True) # For LangGraph checkpointing
    checkpoint_id: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Specific checkpoint version
    
    # Review Details
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.PENDING, index=True)
    proposed_action: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True) # What is being reviewed (e.g., plan, code)
    cost_estimate_usd: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(String, default="medium") # low, medium, high
    
    # Timing
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # One-to-Many relationship with decisions (though typically one final decision)
    decisions: Mapped[List["ReviewDecisionRecord"]] = relationship(back_populates="request")

class ReviewDecisionRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "review_decisions"
    
    review_request_id: Mapped[str] = mapped_column(String, ForeignKey("review_requests.id"), index=True)
    decision: Mapped[ReviewDecision] = mapped_column(Enum(ReviewDecision))
    actor: Mapped[str] = mapped_column(String)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    request: Mapped["ReviewRequest"] = relationship(back_populates="decisions")
