# Workflow Versioning & State-Aware Rollback

This feature enables safe upgrades of workflows by tracking versions, snapshots, and supporting shadow deployments.

## Architecture

1.  **Registry**: Tracks active and shadow deployments (`backend/app/versioning/registry.py`).
2.  **Snapshots**: Stores zipped artifacts (code/prompts) and state checkpoints (`backend/app/versioning/snapshot.py`).
3.  **Deployer**: Manages the deployment lifecycle (`backend/app/versioning/deployer.py`).
4.  **Shadow Mode**: Runs candidate versions in parallel with production traffic (implemented in `backend/app/queue/worker.py`).
5.  **Comparator**: Detects divergence between active and shadow runs (`backend/app/versioning/comparator.py`).

## Usage

### 1. Deploying a Version

Use the `deployer` module to deploy a version.

```python
from app.versioning.deployer import deploy_version

# Deploy v1 as ACTIVE
deploy_version("my-workflow", "v1", artifacts={"prompt": "Hello"}, is_shadow=False)

# Deploy v2 as SHADOW (50% sample rate)
deploy_version("my-workflow", "v2", artifacts={"prompt": "Hello new"}, is_shadow=True, sample_rate=0.5)
```

### 2. Manual Rollback

If divergence is detected or issues found:

```python
from app.versioning.deployer import rollback_version

rollback_version("my-workflow", "snapshot-uuid-of-v1", reason="v2 too divergent")
```

### 3. Monitoring Divergence

The system automatically checks for divergence after shadow runs. Check logs or the `versioning_comparisons` table.

## Configuration

-   `SNAPSHOT_STORAGE_PATH`: Directory for snapshot zips (default: `storage/snapshots`).
-   `DIVERGENCE_THRESHOLD`: Score below which a run is considered divergent (default: 0.85).
-   `AUTO_ROLLBACK`: Enable/Disable automatic rollback (default: False).
