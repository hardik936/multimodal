from datetime import datetime
from sqlalchemy import String, Text, JSON, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from .base import Base, UUIDMixin


class Message(Base, UUIDMixin):
    """Message model representing a message in a workflow run conversation."""
    
    __tablename__ = "messages"
    
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    msg_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="CURRENT_TIMESTAMP"
    )
    
    # Relationships
    run: Mapped["WorkflowRun"] = relationship(
        "WorkflowRun",
        back_populates="messages"
    )
    
    __table_args__ = (
        Index("ix_messages_run_created", "run_id", "created_at"),
        Index("ix_messages_role", "role"),
    )
    
    def __repr__(self) -> str:
        return f"<Message(id={self.id}, run_id={self.run_id}, role={self.role})>"
