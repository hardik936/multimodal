"""
Quota Management System

Tracks and enforces per-workflow and per-tenant token quotas
with configurable enforcement modes (soft/hard).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.orm import Session

from app.models.base import Base
from app.database import SessionLocal

logger = logging.getLogger(__name__)


class UsageQuota(Base):
    """SQLAlchemy model for quota tracking."""
    
    __tablename__ = "usage_quota"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(String, nullable=True, index=True)
    tenant_id = Column(String, nullable=True, index=True)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    tokens_limit = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_quota_workflow_window', 'workflow_id', 'window_start'),
        Index('idx_quota_tenant_window', 'tenant_id', 'window_start'),
    )


class QuotaExceededError(Exception):
    """Raised when quota is exceeded in hard enforcement mode."""
    
    def __init__(self, message: str, quota_info: Dict[str, Any]):
        super().__init__(message)
        self.quota_info = quota_info


class QuotaManager:
    """
    Manages token quotas for workflows and tenants.
    
    Supports:
    - Rolling time windows (daily/monthly)
    - Soft mode (log warning, allow call)
    - Hard mode (reject call with QuotaExceededError)
    """
    
    def __init__(self, config):
        """
        Initialize quota manager.
        
        Args:
            config: RateLimitConfig instance
        """
        self.config = config
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Ensure the usage_quota table exists."""
        try:
            from app.database import engine
            UsageQuota.__table__.create(engine, checkfirst=True)
            logger.info("UsageQuota table initialized")
        except Exception as e:
            logger.warning(f"Could not create UsageQuota table: {e}")
    
    def _get_current_window(self) -> Tuple[datetime, datetime]:
        """
        Get current quota window based on configuration.
        
        Returns:
            Tuple of (window_start, window_end)
        """
        now = datetime.utcnow()
        
        # For simplicity, use rolling window from start of current period
        # Daily window: start of today to end of today
        # Monthly window: start of month to end of month
        
        if self.config.quota_window_days == 1:
            # Daily window
            window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            window_end = window_start + timedelta(days=1)
        elif self.config.quota_window_days == 30:
            # Monthly window (approximate)
            window_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Next month
            if window_start.month == 12:
                window_end = window_start.replace(year=window_start.year + 1, month=1)
            else:
                window_end = window_start.replace(month=window_start.month + 1)
        else:
            # Custom rolling window
            window_start = now - timedelta(days=self.config.quota_window_days)
            window_end = now
        
        return window_start, window_end
    
    def _get_or_create_quota(
        self,
        db: Session,
        workflow_id: Optional[str],
        tenant_id: Optional[str]
    ) -> UsageQuota:
        """
        Get or create quota record for current window.
        
        Args:
            db: Database session
            workflow_id: Workflow identifier (optional)
            tenant_id: Tenant identifier (optional)
            
        Returns:
            UsageQuota instance
        """
        window_start, window_end = self._get_current_window()
        
        # Try to find existing quota for this window
        query = db.query(UsageQuota).filter(
            UsageQuota.window_start == window_start,
            UsageQuota.window_end == window_end
        )
        
        if workflow_id:
            query = query.filter(UsageQuota.workflow_id == workflow_id)
        else:
            query = query.filter(UsageQuota.workflow_id.is_(None))
        
        if tenant_id:
            query = query.filter(UsageQuota.tenant_id == tenant_id)
        else:
            query = query.filter(UsageQuota.tenant_id.is_(None))
        
        quota = query.first()
        
        if not quota:
            # Create new quota record
            quota = UsageQuota(
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                window_start=window_start,
                window_end=window_end,
                tokens_used=0,
                tokens_limit=self.config.default_daily_quota_tokens
            )
            db.add(quota)
            db.commit()
            db.refresh(quota)
        
        return quota
    
    def check_and_reserve(
        self,
        workflow_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        tokens: int = 1
    ) -> bool:
        """
        Check if quota allows the request and reserve tokens.
        
        Args:
            workflow_id: Workflow identifier
            tenant_id: Tenant identifier
            tokens: Number of tokens to reserve
            
        Returns:
            True if quota allows, False if exceeded (soft mode)
            
        Raises:
            QuotaExceededError: If quota exceeded in hard mode
        """
        if not self.config.enabled:
            return True
        
        db = SessionLocal()
        try:
            quota = self._get_or_create_quota(db, workflow_id, tenant_id)
            
            # Check if adding tokens would exceed limit
            would_exceed = (quota.tokens_used + tokens) > quota.tokens_limit
            
            if would_exceed:
                quota_info = {
                    "workflow_id": workflow_id,
                    "tenant_id": tenant_id,
                    "tokens_used": quota.tokens_used,
                    "tokens_limit": quota.tokens_limit,
                    "tokens_requested": tokens,
                    "window_start": quota.window_start.isoformat(),
                    "window_end": quota.window_end.isoformat(),
                }
                
                if self.config.quota_enforcement == "hard":
                    raise QuotaExceededError(
                        f"Quota exceeded: {quota.tokens_used + tokens}/{quota.tokens_limit} tokens",
                        quota_info
                    )
                else:
                    # Soft mode: log warning but allow
                    logger.warning(
                        f"Quota soft limit exceeded for workflow={workflow_id}, tenant={tenant_id}: "
                        f"{quota.tokens_used + tokens}/{quota.tokens_limit} tokens"
                    )
            
            # Reserve tokens (optimistic reservation)
            quota.tokens_used += tokens
            quota.updated_at = datetime.utcnow()
            db.commit()
            
            return True
        
        except QuotaExceededError:
            raise
        except Exception as e:
            logger.error(f"Error checking quota: {e}")
            db.rollback()
            # On error, allow the call (fail open)
            return True
        finally:
            db.close()
    
    def record_usage(
        self,
        workflow_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        tokens: int = 1
    ) -> None:
        """
        Record actual token usage (for post-call adjustment).
        
        This can be used to adjust the reservation if actual usage differs
        from the estimate.
        
        Args:
            workflow_id: Workflow identifier
            tenant_id: Tenant identifier
            tokens: Actual number of tokens used
        """
        if not self.config.enabled:
            return
        
        db = SessionLocal()
        try:
            quota = self._get_or_create_quota(db, workflow_id, tenant_id)
            
            # This is typically called after check_and_reserve,
            # so we might need to adjust if estimate was wrong
            # For now, we just ensure the value is recorded
            # (check_and_reserve already incremented it)
            
            quota.updated_at = datetime.utcnow()
            db.commit()
            
        except Exception as e:
            logger.error(f"Error recording usage: {e}")
            db.rollback()
        finally:
            db.close()
    
    def get_quota_status(
        self,
        workflow_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get current quota status.
        
        Args:
            workflow_id: Workflow identifier
            tenant_id: Tenant identifier
            
        Returns:
            Dict with quota status information
        """
        if not self.config.enabled:
            return {
                "enabled": False,
                "tokens_used": 0,
                "tokens_remaining": float('inf'),
                "tokens_limit": 0,
                "window_start": None,
                "window_end": None,
                "reset_at": None,
            }
        
        db = SessionLocal()
        try:
            quota = self._get_or_create_quota(db, workflow_id, tenant_id)
            
            return {
                "enabled": True,
                "tokens_used": quota.tokens_used,
                "tokens_remaining": max(0, quota.tokens_limit - quota.tokens_used),
                "tokens_limit": quota.tokens_limit,
                "window_start": quota.window_start.isoformat(),
                "window_end": quota.window_end.isoformat(),
                "reset_at": quota.window_end.isoformat(),
                "enforcement_mode": self.config.quota_enforcement,
            }
        
        except Exception as e:
            logger.error(f"Error getting quota status: {e}")
            return {
                "enabled": True,
                "error": str(e),
            }
        finally:
            db.close()


# Global quota manager instance
_quota_manager: Optional[QuotaManager] = None


def get_quota_manager() -> QuotaManager:
    """
    Get the global quota manager instance.
    
    Returns:
        QuotaManager instance
    """
    global _quota_manager
    
    if _quota_manager is None:
        from .config import load_rate_limit_config
        config = load_rate_limit_config()
        _quota_manager = QuotaManager(config)
    
    return _quota_manager
