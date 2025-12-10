from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum

class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class AgentConfig(BaseModel):
    """Configuration for a single agent"""
    name: str
    type: str  # researcher, planner, executor, coder
    temperature: float = 0.7
    max_tokens: int = 2000

class WorkflowCreate(BaseModel):
    """Create new workflow"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    graph_definition: Dict[str, Any] = Field(
        ..., 
        description="LangGraph workflow definition"
    )
    agents_config: Dict[str, AgentConfig] = Field(
        ..., 
        description="Agent configurations keyed by agent name"
    )
    is_public: bool = False

class WorkflowUpdate(BaseModel):
    """Update existing workflow"""
    name: Optional[str] = None
    description: Optional[str] = None
    graph_definition: Optional[Dict[str, Any]] = None
    agents_config: Optional[Dict[str, AgentConfig]] = None
    status: Optional[WorkflowStatus] = None
    is_public: Optional[bool] = None

class WorkflowResponse(BaseModel):
    """Workflow response"""
    id: str
    user_id: str
    name: str
    description: Optional[str]
    status: WorkflowStatus
    is_public: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class WorkflowDetailResponse(WorkflowResponse):
    """Detailed workflow response with config"""
    graph_definition: Dict[str, Any]
    agents_config: Dict[str, AgentConfig]
    run_count: int = 0

class MultiAgentRunRequest(BaseModel):
    """Request for running multi-agent workflow"""
    input: str
    language: str = "python"
    mode: str = "full"
