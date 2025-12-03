from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional, List

from app.models.base import Base, UUIDMixin, TimestampMixin

from enum import Enum

class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class WorkflowRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_runs"

    workflow_id: Mapped[str] = mapped_column(String, ForeignKey("workflows.id"))
    status: Mapped[str] = mapped_column(String, default=RunStatus.PENDING)
    input_data: Mapped[dict] = mapped_column(JSON)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    workflow = relationship("Workflow", back_populates="runs")
    logs = relationship("Log", back_populates="run")
    messages = relationship("Message", back_populates="run")
