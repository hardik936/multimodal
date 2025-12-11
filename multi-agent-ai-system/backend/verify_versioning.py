import logging
import asyncio
import shutil
import os
from app.database import init_db
from app.versioning.deployer import deploy_version, rollback_version
from app.versioning.registry import get_active_deployment, get_shadow_deployment
from app.versioning.comparator import record_comparison
from app.versioning.monitor import check_divergence

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_versioning")

def verify_versioning():
    init_db()
    
    workflow_id = "verify-workflow-1"
    
    # Clean up storage for test
    if os.path.exists(f"storage/snapshots/{workflow_id}"):
        shutil.rmtree(f"storage/snapshots/{workflow_id}")

    logger.info("--- 1. Deploy V1 (Active) ---")
    deploy_version(workflow_id, "v1", artifacts={"prompt": "Prompt V1"}, is_shadow=False)
    
    active = get_active_deployment(workflow_id)
    if active and active.snapshot.version_tag == "v1":
        logger.info("PASS: V1 is active")
    else:
        logger.error("FAIL: V1 not active")
        return

    logger.info("--- 2. Deploy V2 (Shadow) ---")
    deploy_version(workflow_id, "v2", artifacts={"prompt": "Prompt V2"}, is_shadow=True, sample_rate=1.0)
    
    shadow = get_shadow_deployment(workflow_id)
    if shadow and shadow.snapshot.version_tag == "v2" and shadow.is_shadow:
        logger.info("PASS: V2 is shadow")
    else:
        logger.error("FAIL: V2 not shadow")
        return

    logger.info("--- 3. Simulate Divergence ---")
    # Simulate run comparisons (usually done by worker)
    # Good run
    record_comparison(workflow_id, "run1", "shadow-run1", "snap1", "snap2", {"k": "v"}, {"k": "v"})
    # Bad run
    record_comparison(workflow_id, "run2", "shadow-run2", "snap1", "snap2", {"k": "v"}, {"k": "different"})
    
    check_divergence(workflow_id)
    logger.info("PASS: Divergence check ran (check logs for output)")

    logger.info("--- 4. Manual Rollback ---")
    # Rollback to V1 snapshot (just to test API, even though V1 is active, we re-deploy it)
    rollback_version(workflow_id, active.snapshot_id, reason="Testing rollback")
    
    current = get_active_deployment(workflow_id)
    if current.snapshot_id == active.snapshot_id and current.role == "active":
        logger.info("PASS: Rollback successful")
    else:
        logger.error("FAIL: Rollback failed")

if __name__ == "__main__":
    verify_versioning()
