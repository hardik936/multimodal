from datetime import datetime
from typing import Optional, Any
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base

class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[str] = mapped_column(String, index=True)
    candidate_version: Mapped[str] = mapped_column(String) # The version being tested
    deployed_version: Mapped[Optional[str]] = mapped_column(String, nullable=True) # The active baseline (if comparing)
    
    start_ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_ts: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    aggregated_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    total_cost_usd: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True) # avoiding reserved word

    results = relationship("EvaluationResult", back_populates="run", cascade="all, delete-orphan")

class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("evaluation_runs.id"))
    case_id: Mapped[str] = mapped_column(String)
    
    score: Mapped[float] = mapped_column(Float)
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # latency, cost, etc.
    trace_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    run = relationship("EvaluationRun", back_populates="results")
