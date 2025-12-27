from sqlalchemy import Column, String, LargeBinary, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.models.base import Base, TimestampMixin

class Checkpoint(Base, TimestampMixin):
    """
    Stores LangGraph checkpoints.
    Uniquely identified by (thread_id, checkpoint_id).
    """
    __tablename__ = "checkpoints"

    thread_id: Mapped[str] = mapped_column(String, primary_key=True)
    checkpoint_id: Mapped[str] = mapped_column(String, primary_key=True)
    parent_checkpoint_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    type_: Mapped[str] = mapped_column("type", String, default="json")
    checkpoint: Mapped[bytes] = mapped_column(LargeBinary)
    metadata_: Mapped[bytes] = mapped_column("metadata", LargeBinary)

    # Optional: index for cleanup
    # __table_args__ = (
    #     Index("idx_checkpoints_thread_id", "thread_id"),
    # )

class CheckpointWrite(Base, TimestampMixin):
    """
    Stores pending writes for a checkpoint.
    """
    __tablename__ = "checkpoint_writes"

    thread_id: Mapped[str] = mapped_column(String, primary_key=True)
    checkpoint_id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, primary_key=True)
    idx: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    channel: Mapped[str] = mapped_column(String)
    type_: Mapped[Optional[str]] = mapped_column("type", String, nullable=True)
    value: Mapped[bytes] = mapped_column(LargeBinary)

class CheckpointBlob(Base):
    """
    Stores large blobs decoupled from writes/checkpoints to duplicate data.
    """
    __tablename__ = "checkpoint_blobs"

    thread_id: Mapped[str] = mapped_column(String, primary_key=True)
    checkpoint_id: Mapped[str] = mapped_column(String, primary_key=True)
    key: Mapped[str] = mapped_column(String, primary_key=True)
    
    value: Mapped[bytes] = mapped_column(LargeBinary)
