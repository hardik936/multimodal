from typing import Optional
from app.versioning.registry import register_deployment, get_active_deployment
from app.versioning.snapshot import create_snapshot, get_snapshot
from app.versioning.audit import record_audit_log

def deploy_version(workflow_id: str, version_tag: str, artifacts: dict = None, 
                   is_shadow: bool = False, sample_rate: float = 0.05, 
                   actor: str = "system",
                   evalset_path: Optional[str] = None,
                   require_eval_pass: bool = True) -> dict:
    """
    Deploy a new version of a workflow.
    
    1. Create a snapshot of the artifacts.
    2. Register the deployment (Active or Shadow).
    3. Audit log the action.
    """
    
    # 1. Create Snapshot (if not deploying an existing one - simplified here to always snapshot new)
    # In a real system, we might look up existing snapshot by tag.
    snapshot = create_snapshot(workflow_id, version_tag, artifacts)
    
    # [NEW] Pre-deployment Evaluation
    eval_run_id = None
    eval_passed = True
    if evalset_path:
        import asyncio
        from app.eval.runner import run_evalset
        from app.eval.store import EvaluationRun
        from app.database import SessionLocal
        
        # Run eval
        # Note: In production we might run this on a separate worker, but here we block
        try:
            print(f"Running pre-deployment checks: {evalset_path}")
            eval_run_id = asyncio.run(run_evalset(evalset_path, workflow_version=version_tag))
            
            # Check result
            db = SessionLocal()
            eval_run = db.query(EvaluationRun).get(eval_run_id)
            eval_score = eval_run.aggregated_score
            eval_passed = eval_run.passed
            db.close()
            
            if require_eval_pass and not eval_passed:
                record_audit_log(
                    workflow_id=workflow_id,
                    action="DEPLOY_REJECTED",
                    details=f"Deployment of {version_tag} rejected. Eval score: {eval_score:.2f}",
                    actor=actor,
                    snapshot_id=snapshot.snapshot_id
                )
                return {
                    "status": "rejected",
                    "reason": f"Evaluation failed. Score: {eval_score:.2f}",
                    "eval_run_id": eval_run_id
                }
                
        except Exception as e:
            if require_eval_pass:
                raise e
    
    role = "shadow" if is_shadow else "active"
    
    # 2. Register Deployment
    deployment = register_deployment(
        workflow_id=workflow_id,
        snapshot_id=snapshot.snapshot_id,
        role=role,
        is_shadow=is_shadow,
        sample_rate=sample_rate
    )
    
    # 3. Audit
    record_audit_log(
        workflow_id=workflow_id, 
        action="DEPLOY", 
        details=f"Deployed {version_tag} as {role} (sample_rate={sample_rate})",
        actor=actor,
        snapshot_id=snapshot.snapshot_id,
        deployment_id=deployment.id
    )
    
    return {
        "deployment_id": deployment.id,
        "snapshot_id": snapshot.snapshot_id,
        "role": role,
        "status": "success",
        "eval_run_id": eval_run_id
    }

def rollback_version(workflow_id: str, target_snapshot_id: str, reason: str, actor: str = "system"):
    """
    Manual rollback to a specific snapshot.
    """
    # Verify snapshot exists
    snapshot = get_snapshot(target_snapshot_id)
    if not snapshot:
        raise ValueError(f"Snapshot {target_snapshot_id} not found")
        
    # Register as new active deployment
    deployment = register_deployment(
        workflow_id=workflow_id,
        snapshot_id=target_snapshot_id,
        role="active",
        is_shadow=False
    )
    
    record_audit_log(
        workflow_id=workflow_id,
        action="ROLLBACK",
        details=f"Rolled back to {snapshot.version_tag} ({target_snapshot_id}). Reason: {reason}",
        actor=actor,
        snapshot_id=target_snapshot_id,
        deployment_id=deployment.id
    )
    
    return deployment
