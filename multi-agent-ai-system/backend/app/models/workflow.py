from sqlalchemy import Column, String, Boolean, DateTime, JSON, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
import enum

from app.models.base import Base, UUIDMixin, TimestampMixin

class WorkflowStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class Workflow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflows"

    # UUIDMixin provides id
    # TimestampMixin provides created_at, updated_at

    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String, nullable=True)
    graph_definition: Mapped[dict] = mapped_column(JSON)
    agents_config: Mapped[dict] = mapped_column(JSON)
    user_id: Mapped[str] = mapped_column(String, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[WorkflowStatus] = mapped_column(Enum(WorkflowStatus), default=WorkflowStatus.DRAFT)

    runs = relationship("WorkflowRun", back_populates="workflow")
