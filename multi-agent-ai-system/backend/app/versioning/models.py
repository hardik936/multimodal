from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base

class Snapshot(Base):
    __tablename__ = "versioning_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(String, unique=True, index=True, nullable=False) # UUID
    workflow_id = Column(String, index=True, nullable=False)
    version_tag = Column(String, nullable=False) # v1, v2, etc.
    
    git_commit = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Path to the zip file containing artifacts
    storage_path = Column(String, nullable=False)
    
    # Metadata snapshot (JSON) - could include tool versions list, model spec
    metadata_json = Column(Text, nullable=True)
    
    deployments = relationship("Deployment", back_populates="snapshot")


class Deployment(Base):
    __tablename__ = "versioning_deployments"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(String, index=True, nullable=False)
    
    # Link to the snapshot being deployed
    snapshot_id = Column(String, ForeignKey("versioning_snapshots.snapshot_id"), nullable=False)
    snapshot = relationship("Snapshot", back_populates="deployments")
    
    # Deployment configuration
    environment = Column(String, default="production") # production, staging
    role = Column(String, default="active") # active, shadow, candidate
    
    # Shadow mode config
    is_shadow = Column(Boolean, default=False)
    sample_rate = Column(Float, default=0.0)
    
    deployed_at = Column(DateTime, default=datetime.utcnow)
    deployed_by = Column(String, nullable=True)
    
    active = Column(Boolean, default=True)


class ComparisonResult(Base):
    __tablename__ = "versioning_comparisons"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(String, index=True, nullable=False)
    
    baseline_run_id = Column(String, nullable=True) # Run ID of the active version
    candidate_run_id = Column(String, nullable=True) # Run ID of the shadow version
    
    baseline_snapshot_id = Column(String, nullable=False)
    candidate_snapshot_id = Column(String, nullable=False)
    
    score = Column(Float, nullable=False) # 0.0 to 1.0 (1.0 = identical)
    metric = Column(String, default="json_diff") 
    
    details = Column(Text, nullable=True) # JSON details of difference
    timestamp = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "versioning_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    workflow_id = Column(String, index=True, nullable=False)
    action = Column(String, nullable=False) # DEPLOY, ROLLBACK, SNAPSHOT
    
    actor = Column(String, nullable=True) # User or System
    details = Column(Text, nullable=True)
    
    # Links
    snapshot_id = Column(String, nullable=True)
    deployment_id = Column(Integer, nullable=True)
