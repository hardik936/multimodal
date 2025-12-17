from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.database import get_db
from app.models.workflow import Workflow, WorkflowStatus
from app.schemas.workflow import (
    WorkflowCreate, 
    WorkflowUpdate, 
    WorkflowResponse,
    WorkflowDetailResponse,
    MultiAgentRunRequest
)
from app.agents.graph import graph
from app.auth import deps, models
from typing import Annotated

router = APIRouter()

@router.post("/multi-agent/run")
async def run_multi_agent_workflow(
    request: MultiAgentRunRequest,
    current_user: Annotated[models.User, Depends(deps.get_current_active_user)]
):
    """Run the multi-agent workflow"""
    # Determine workflow name from mode
    # If mode is "invoice_ocr", we use that. Otherwise default to "default".
    workflow_name = "default"
    if request.mode == "invoice_ocr":
        workflow_name = "invoice_ocr"
        
    initial_state = {
        "input": request.input,
        "language": request.language,
        "mode": request.mode,
        "messages": [],
        "document_text": request.input # Default mappings
    }
    
    # Check if input is JSON with file_path (from frontend upload)
    import json
    try:
        if request.input.strip().startswith("{") and "file_path" in request.input:
            data = json.loads(request.input)
            if "file_path" in data:
                initial_state["file_path"] = data["file_path"]
                # If text is provided in the JSON, use it, otherwise use what we have
                if "text" in data:
                    initial_state["document_text"] = data["text"]
                    
    except json.JSONDecodeError:
        pass # Not JSON, treat as plain text
    
    # Create appropriate graph
    current_graph = graph
    if workflow_name != "default":
        from app.agents.graph import create_graph
        current_graph = create_graph(workflow_name=workflow_name)
        
    result = current_graph.invoke(initial_state)
    return result

@router.post(
    "",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_workflow(
    workflow: WorkflowCreate,
    db: Session = Depends(get_db),
    current_user: Annotated[models.User, Depends(deps.get_current_active_user)] = None,
):
    """Create a new workflow"""
    user_id = current_user.id if current_user else "demo-user"
    
    db_workflow = Workflow(
        id=str(uuid.uuid4()),
        name=workflow.name,
        description=workflow.description,
        graph_definition=workflow.graph_definition,
        agents_config={
            k: v.model_dump() 
            for k, v in workflow.agents_config.items()
        },
        user_id=user_id,
        is_public=workflow.is_public,
    )
    
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    
    return db_workflow

@router.get("", response_model=List[WorkflowResponse])
async def list_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[WorkflowStatus] = None,
    db: Session = Depends(get_db),
    current_user: Annotated[models.User, Depends(deps.get_current_active_user)] = None,
):
    """List all workflows"""
    query = db.query(Workflow)
    
    if status:
        query = query.filter(Workflow.status == status)
    
    workflows = query.offset(skip).limit(limit).all()
    return workflows

@router.get("/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: Annotated[models.User, Depends(deps.get_current_active_user)] = None,
):
    """Get workflow by ID"""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id
    ).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found"
        )
    
    # Add run count
    response = WorkflowDetailResponse.model_validate(workflow)
    response.run_count = len(workflow.runs)
    
    return response

@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    workflow_update: WorkflowUpdate,
    db: Session = Depends(get_db),
    current_user: Annotated[models.User, Depends(deps.get_current_active_user)] = None,
):
    """Update workflow"""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id
    ).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found"
        )
    
    # Update fields
    update_data = workflow_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "agents_config" and value:
            # Convert AgentConfig objects to dicts
            value = {k: v.model_dump() for k, v in value.items()}
        setattr(workflow, field, value)
    
    db.commit()
    db.refresh(workflow)
    
    return workflow

@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: Annotated[models.User, Depends(deps.get_current_active_user)] = None,
):
    """Delete workflow"""
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id
    ).first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found"
        )
    
    db.delete(workflow)
    db.commit()
    
    return None
