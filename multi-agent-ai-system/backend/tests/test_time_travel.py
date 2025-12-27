import pytest
import sqlite3
import os
import uuid
import json
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models.base import Base
import app.models as models
from app.models.run import WorkflowRun, RunStatus
from app.main import app
from app.routers import history
import app.tasks.huey_tasks as huey_tasks_sys # Explicit import aliased to avoid shadowing 'app'


# Setup in-memory DB for testing main logic
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# Checkpoints DB file
TEST_CHECKPOINTS_DB = "checkpoints.db"

@pytest.fixture(scope="function", autouse=True)
def setup_databases():
    # Main DB
    Base.metadata.create_all(bind=engine)
    
    # Checkpoints DB
    # We remove it if it exists to start fresh
    if os.path.exists(TEST_CHECKPOINTS_DB):
        os.remove(TEST_CHECKPOINTS_DB)
        
    # Initialize Checkpoints DB Schema
    conn = sqlite3.connect(TEST_CHECKPOINTS_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT,
            checkpoint_id TEXT,
            parent_checkpoint_id TEXT,
            checkpoint BLOB,
            metadata BLOB,
            PRIMARY KEY (thread_id, checkpoint_id)
        )
    """)
    conn.commit()
    conn.close()
    
    yield
    
    # Teardown
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(TEST_CHECKPOINTS_DB):
        try:
            os.remove(TEST_CHECKPOINTS_DB)
        except PermissionError:
            pass

@pytest.fixture
def auth_headers():
    # Create and login user
    email = "test_tt@example.com"
    password = "password123"
    
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "TT User"},
    )
    
    res = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": password},
    )
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

from app.models.workflow import Workflow

# ... (imports)

def create_workflow(db, workflow_id="wf_1"):
    wf = Workflow(
        id=workflow_id,
        name="Test Workflow",
        description="A test workflow",
        graph_definition={},
        agents_config={},
        user_id="user_123", # No FK constraint usually
        is_public=False
    )
    db.add(wf)
    db.commit()
    return wf

def test_list_history(auth_headers):
    # 1. Create a run in Main DB
    db = TestingSessionLocal()
    workflow_id = "wf_1"
    create_workflow(db, workflow_id) # create parent first
    
    run_id = str(uuid.uuid4())
    run = WorkflowRun(
        id=run_id,
        workflow_id=workflow_id,
        status="completed",
        started_at=datetime.now(timezone.utc),
        input_data={}
    )
    db.add(run)
    db.commit()
    db.close()
    
    # 2. Insert Checkpoints in SQLite
    conn = sqlite3.connect(TEST_CHECKPOINTS_DB)
    cursor = conn.cursor()
    
    # Checkpoint 1
    cp1_id = "cp_1"
    cursor.execute(
        "INSERT INTO checkpoints (thread_id, checkpoint_id, parent_checkpoint_id, checkpoint, metadata) VALUES (?, ?, ?, ?, ?)",
        (run_id, cp1_id, None, b"state1", b'{"step": "step1"}')
    )
    # Checkpoint 2
    cp2_id = "cp_2"
    cursor.execute(
        "INSERT INTO checkpoints (thread_id, checkpoint_id, parent_checkpoint_id, checkpoint, metadata) VALUES (?, ?, ?, ?, ?)",
        (run_id, cp2_id, cp1_id, b"state2", b'{"step": "step2"}')
    )
    conn.commit()
    conn.close()
    
    # 3. Call API
    response = client.get(f"/api/v1/runs/{run_id}/history", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Verify order (latest first usually, or by insertion. Code sorts by checkpoint_id DESC)
    assert data[0]["id"] == cp2_id
    assert data[1]["id"] == cp1_id
    
    # Verify metadata is correctly parsed
    assert data[0]["metadata"] == {"step": "step2"}
    assert data[1]["metadata"] == {"step": "step1"} 

def test_fork_run(auth_headers):
    # 1. Create original run
    db = TestingSessionLocal()
    workflow_id = "wf_fork"
    create_workflow(db, workflow_id)
    
    orig_run_id = str(uuid.uuid4())
    run = WorkflowRun(
        id=orig_run_id,
        workflow_id=workflow_id,
        status="failed",
        started_at=datetime.now(timezone.utc),
        input_data={}
    )
    db.add(run)
    db.commit()
    db.close()
    
    # 2. Insert Checkpoint
    conn = sqlite3.connect(TEST_CHECKPOINTS_DB)
    cursor = conn.cursor()
    cp_id = "chk_fork_point"
    cursor.execute(
        "INSERT INTO checkpoints (thread_id, checkpoint_id, parent_checkpoint_id, checkpoint, metadata) VALUES (?, ?, ?, ?, ?)",
        (orig_run_id, cp_id, None, b"binary_state", b"binary_meta")
    )
    conn.commit()
    conn.close()
    
    # 3. Mock resume_workflow_task
    with patch("app.tasks.huey_tasks.resume_workflow_task") as mock_resume:
        # 4. Call Fork API
        response = client.post(
            f"/api/v1/runs/{orig_run_id}/fork",
            json={"checkpoint_id": cp_id},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        res_data = response.json()
        new_run_id = res_data["new_run_id"]
        assert new_run_id != orig_run_id
        assert res_data["original_run_id"] == orig_run_id
        
        # 5. Verify New Run in DB
        db = TestingSessionLocal()
        new_run = db.query(WorkflowRun).filter(WorkflowRun.id == new_run_id).first()
        assert new_run is not None
        assert new_run.workflow_id == workflow_id
        assert new_run.status == "pending"
        db.close()
        
        # 6. Verify Checkpoint copied
        conn = sqlite3.connect(TEST_CHECKPOINTS_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM checkpoints WHERE thread_id = ?", (new_run_id,))
        rows = cursor.fetchall()
        assert len(rows) == 1
        # Should have same checkpoint_id
        assert rows[0][1] == cp_id
        conn.close()
        
        # 7. Verify Resume Task Triggered
        mock_resume.assert_called_once_with(new_run_id)

