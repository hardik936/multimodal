import os
import json
import zipfile
import uuid
from datetime import datetime
from app.database import SessionLocal
from app.versioning.models import Snapshot
from app.versioning.audit import record_audit_log

SNAPSHOT_STORAGE_PATH = "storage/snapshots"

def create_snapshot(workflow_id: str, version_tag: str, artifacts: dict = None, state_checkpoint: dict = None) -> Snapshot:
    """
    Create a snapshot of the workflow version and state.
    """
    snapshot_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    
    # Ensure storage directory exists
    store_dir = os.path.join(SNAPSHOT_STORAGE_PATH, workflow_id, version_tag)
    os.makedirs(store_dir, exist_ok=True)
    
    zip_filename = f"{timestamp}_{snapshot_id}.zip"
    zip_path = os.path.join(store_dir, zip_filename)
    
    # Create the zip file
    with zipfile.ZipFile(zip_path, 'w') as zf:
        # Save metadata
        metadata = {
            "snapshot_id": snapshot_id,
            "workflow_id": workflow_id,
            "version_tag": version_tag,
            "timestamp": timestamp,
            "artifacts_meta": list(artifacts.keys()) if artifacts else []
        }
        zf.writestr("metadata.json", json.dumps(metadata, indent=2))
        
        # Save artifacts (prompts, code snippets passed as dict)
        if artifacts:
            for name, content in artifacts.items():
                zf.writestr(f"artifacts/{name}", str(content))
                
        # Save state checkpoint
        if state_checkpoint:
            zf.writestr("state_checkpoint.json", json.dumps(state_checkpoint, default=str, indent=2))
            
    # Record in DB
    db = SessionLocal()
    try:
        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            workflow_id=workflow_id,
            version_tag=version_tag,
            storage_path=zip_path,
            metadata_json=json.dumps(metadata)
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        
        record_audit_log(workflow_id, "SNAPSHOT", f"Created snapshot {version_tag}", snapshot_id=snapshot_id)
        
        return snapshot
    finally:
        db.close()

def get_snapshot(snapshot_id: str) -> Snapshot:
    db = SessionLocal()
    try:
        return db.query(Snapshot).filter(Snapshot.snapshot_id == snapshot_id).first()
    finally:
        db.close()
