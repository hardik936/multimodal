"""
Unit tests for quota management system.

Tests quota tracking, enforcement modes, and window rotation.
"""

import pytest
from datetime import datetime, timedelta
from app.ratelimit.config import RateLimitConfig
from app.ratelimit.quota import QuotaManager, QuotaExceededError, UsageQuota
from app.database import SessionLocal


@pytest.fixture
def config():
    """Create test configuration."""
    return RateLimitConfig(
        enabled=True,
        quota_window_days=1,  # Daily window for testing
        default_daily_quota_tokens=100,
        quota_enforcement="soft",
    )


@pytest.fixture
def quota_manager(config):
    """Create quota manager instance."""
    return QuotaManager(config)


@pytest.fixture
def cleanup_db():
    """Clean up test data after each test."""
    yield
    # Clean up quota records
    db = SessionLocal()
    try:
        db.query(UsageQuota).delete()
        db.commit()
    finally:
        db.close()


def test_quota_manager_initialization(quota_manager, config):
    """Test that quota manager initializes correctly."""
    assert quota_manager.config == config


def test_check_and_reserve_first_request(quota_manager, cleanup_db):
    """Test first request creates quota record and reserves tokens."""
    result = quota_manager.check_and_reserve(
        workflow_id="test-workflow",
        tenant_id="test-tenant",
        tokens=10
    )
    
    assert result is True
    
    # Check status
    status = quota_manager.get_quota_status(
        workflow_id="test-workflow",
        tenant_id="test-tenant"
    )
    
    assert status["tokens_used"] == 10
    assert status["tokens_remaining"] == 90
    assert status["tokens_limit"] == 100


def test_check_and_reserve_multiple_requests(quota_manager, cleanup_db):
    """Test multiple requests accumulate token usage."""
    workflow_id = "test-workflow"
    
    # Make multiple requests
    for i in range(5):
        result = quota_manager.check_and_reserve(
            workflow_id=workflow_id,
            tokens=10
        )
        assert result is True
    
    # Check total usage
    status = quota_manager.get_quota_status(workflow_id=workflow_id)
    assert status["tokens_used"] == 50
    assert status["tokens_remaining"] == 50


def test_soft_mode_allows_over_quota(quota_manager, cleanup_db):
    """Test soft mode logs warning but allows requests over quota."""
    workflow_id = "test-workflow"
    
    # Use up quota
    quota_manager.check_and_reserve(workflow_id=workflow_id, tokens=100)
    
    # Exceed quota in soft mode (should succeed with warning)
    result = quota_manager.check_and_reserve(workflow_id=workflow_id, tokens=50)
    assert result is True
    
    # Check status shows over quota
    status = quota_manager.get_quota_status(workflow_id=workflow_id)
    assert status["tokens_used"] == 150
    assert status["tokens_remaining"] == -50


def test_hard_mode_rejects_over_quota():
    """Test hard mode rejects requests that exceed quota."""
    config = RateLimitConfig(
        enabled=True,
        quota_window_days=1,
        default_daily_quota_tokens=100,
        quota_enforcement="hard",
    )
    quota_manager = QuotaManager(config)
    workflow_id = "test-workflow-hard"
    
    try:
        # Use up quota
        quota_manager.check_and_reserve(workflow_id=workflow_id, tokens=100)
        
        # Try to exceed quota (should raise exception)
        with pytest.raises(QuotaExceededError) as exc_info:
            quota_manager.check_and_reserve(workflow_id=workflow_id, tokens=50)
        
        # Check exception details
        assert "Quota exceeded" in str(exc_info.value)
        assert exc_info.value.quota_info["workflow_id"] == workflow_id
        assert exc_info.value.quota_info["tokens_used"] == 100
        
    finally:
        # Cleanup
        db = SessionLocal()
        try:
            db.query(UsageQuota).filter(UsageQuota.workflow_id == workflow_id).delete()
            db.commit()
        finally:
            db.close()


def test_quota_status_for_new_workflow(quota_manager, cleanup_db):
    """Test getting status for workflow with no usage."""
    status = quota_manager.get_quota_status(workflow_id="new-workflow")
    
    assert status["enabled"] is True
    assert status["tokens_used"] == 0
    assert status["tokens_remaining"] == 100
    assert status["tokens_limit"] == 100


def test_separate_quotas_per_workflow(quota_manager, cleanup_db):
    """Test that different workflows have separate quotas."""
    # Use tokens for workflow 1
    quota_manager.check_and_reserve(workflow_id="workflow-1", tokens=50)
    
    # Use tokens for workflow 2
    quota_manager.check_and_reserve(workflow_id="workflow-2", tokens=30)
    
    # Check separate usage
    status1 = quota_manager.get_quota_status(workflow_id="workflow-1")
    status2 = quota_manager.get_quota_status(workflow_id="workflow-2")
    
    assert status1["tokens_used"] == 50
    assert status2["tokens_used"] == 30


def test_separate_quotas_per_tenant(quota_manager, cleanup_db):
    """Test that different tenants have separate quotas."""
    # Use tokens for tenant 1
    quota_manager.check_and_reserve(tenant_id="tenant-1", tokens=40)
    
    # Use tokens for tenant 2
    quota_manager.check_and_reserve(tenant_id="tenant-2", tokens=60)
    
    # Check separate usage
    status1 = quota_manager.get_quota_status(tenant_id="tenant-1")
    status2 = quota_manager.get_quota_status(tenant_id="tenant-2")
    
    assert status1["tokens_used"] == 40
    assert status2["tokens_used"] == 60


def test_record_usage(quota_manager, cleanup_db):
    """Test recording actual usage."""
    workflow_id = "test-workflow"
    
    # Reserve tokens
    quota_manager.check_and_reserve(workflow_id=workflow_id, tokens=50)
    
    # Record actual usage (this is typically called after the LLM call)
    quota_manager.record_usage(workflow_id=workflow_id, tokens=50)
    
    # Status should still show 50 tokens used
    status = quota_manager.get_quota_status(workflow_id=workflow_id)
    assert status["tokens_used"] == 50


def test_disabled_quota_manager():
    """Test that disabled quota manager always allows requests."""
    config = RateLimitConfig(enabled=False)
    quota_manager = QuotaManager(config)
    
    # Should always succeed
    for i in range(10):
        result = quota_manager.check_and_reserve(
            workflow_id="test",
            tokens=1000
        )
        assert result is True
    
    # Status should show disabled
    status = quota_manager.get_quota_status(workflow_id="test")
    assert status["enabled"] is False


def test_quota_window_info(quota_manager, cleanup_db):
    """Test that quota status includes window information."""
    workflow_id = "test-workflow"
    
    quota_manager.check_and_reserve(workflow_id=workflow_id, tokens=10)
    status = quota_manager.get_quota_status(workflow_id=workflow_id)
    
    assert "window_start" in status
    assert "window_end" in status
    assert "reset_at" in status
    
    # Parse dates
    window_start = datetime.fromisoformat(status["window_start"])
    window_end = datetime.fromisoformat(status["window_end"])
    
    # Window should be approximately 1 day
    window_duration = window_end - window_start
    assert timedelta(hours=23) <= window_duration <= timedelta(hours=25)


def test_concurrent_quota_updates(quota_manager, cleanup_db):
    """Test thread-safe quota updates."""
    import threading
    
    workflow_id = "concurrent-test"
    success_count = [0]
    lock = threading.Lock()
    
    def reserve_tokens():
        try:
            result = quota_manager.check_and_reserve(
                workflow_id=workflow_id,
                tokens=10
            )
            if result:
                with lock:
                    success_count[0] += 1
        except Exception:
            pass
    
    # Start 20 threads
    threads = []
    for i in range(20):
        t = threading.Thread(target=reserve_tokens)
        threads.append(t)
        t.start()
    
    # Wait for all threads
    for t in threads:
        t.join()
    
    # All should succeed (soft mode)
    assert success_count[0] == 20
    
    # Check total usage
    status = quota_manager.get_quota_status(workflow_id=workflow_id)
    assert status["tokens_used"] == 200  # 20 * 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
