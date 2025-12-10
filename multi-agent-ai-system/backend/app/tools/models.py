"""
Core data models for tool versioning and compatibility management.
"""

from typing import Callable, Dict, Any, Optional, Type, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum


class ToolVersion(BaseModel):
    """
    Semantic version identity for tools.
    Format: tool_name@MAJOR.MINOR.PATCH
    """
    name: str = Field(..., description="Tool name")
    major: int = Field(..., ge=0, description="Major version (breaking changes)")
    minor: int = Field(..., ge=0, description="Minor version (backward-compatible features)")
    patch: int = Field(..., ge=0, description="Patch version (backward-compatible fixes)")
    
    @property
    def version_string(self) -> str:
        """Returns version as 'MAJOR.MINOR.PATCH'"""
        return f"{self.major}.{self.minor}.{self.patch}"
    
    @property
    def identifier(self) -> str:
        """Returns full identifier as 'name@MAJOR.MINOR.PATCH'"""
        return f"{self.name}@{self.version_string}"
    
    def __str__(self) -> str:
        return self.identifier
    
    def __hash__(self) -> int:
        return hash(self.identifier)
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, ToolVersion):
            return False
        return (
            self.name == other.name and
            self.major == other.major and
            self.minor == other.minor and
            self.patch == other.patch
        )
    
    @classmethod
    def from_string(cls, version_str: str) -> "ToolVersion":
        """
        Parse version string like 'tool_name@1.2.3'
        """
        if "@" not in version_str:
            raise ValueError(f"Invalid version string: {version_str}. Expected format: 'name@MAJOR.MINOR.PATCH'")
        
        name, version = version_str.split("@", 1)
        parts = version.split(".")
        
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {version}. Expected 'MAJOR.MINOR.PATCH'")
        
        try:
            major, minor, patch = map(int, parts)
        except ValueError:
            raise ValueError(f"Version components must be integers: {version}")
        
        return cls(name=name, major=major, minor=minor, patch=patch)


class DeprecationPolicy(str, Enum):
    """
    Policy for handling deprecated tool versions.
    """
    WARN = "warn"  # Log warning, allow execution (default)
    ERROR = "error"  # Hard fail with deprecation message


class ToolDefinition(BaseModel):
    """
    Complete tool definition with versioning and schema.
    """
    name: str = Field(..., description="Tool name")
    version: ToolVersion = Field(..., description="Semantic version")
    input_schema: Type[BaseModel] = Field(..., description="Pydantic model for input validation")
    implementation: Callable = Field(..., description="Tool implementation function")
    deprecated: bool = Field(default=False, description="Whether this version is deprecated")
    deprecation_policy: DeprecationPolicy = Field(
        default=DeprecationPolicy.WARN,
        description="How to handle deprecated tool usage"
    )
    deprecation_message: Optional[str] = Field(
        default=None,
        description="Custom message to show when deprecated tool is used"
    )
    description: Optional[str] = Field(default=None, description="Tool description")
    
    class Config:
        arbitrary_types_allowed = True
    
    @property
    def identifier(self) -> str:
        """Returns full identifier as 'name@MAJOR.MINOR.PATCH'"""
        return self.version.identifier


class ToolAdapter(BaseModel):
    """
    Compatibility adapter for transforming between tool versions.
    
    CONSTRAINTS:
    - Adapters are pure, deterministic functions
    - Only N → N+1 version transitions allowed (single-hop)
    - No multi-hop adapter chaining
    """
    from_version: ToolVersion = Field(..., description="Source version")
    to_version: ToolVersion = Field(..., description="Target version")
    adapter_fn: Callable[[Dict[str, Any]], Dict[str, Any]] = Field(
        ...,
        description="Pure function that transforms input from source to target schema"
    )
    description: Optional[str] = Field(default=None, description="Adapter description")
    
    class Config:
        arbitrary_types_allowed = True
    
    @field_validator("to_version")
    @classmethod
    def validate_single_hop(cls, to_version: ToolVersion, info) -> ToolVersion:
        """
        Validate that adapter only supports N → N+1 transitions.
        """
        from_version = info.data.get("from_version")
        if not from_version:
            return to_version
        
        # Must be same tool
        if from_version.name != to_version.name:
            raise ValueError(
                f"Adapter must be for same tool. Got {from_version.name} → {to_version.name}"
            )
        
        # Only allow single-hop major version transitions
        if to_version.major == from_version.major + 1:
            # Major version bump is allowed
            return to_version
        elif to_version.major == from_version.major:
            # Minor/patch version changes within same major version are allowed
            if to_version.minor > from_version.minor or to_version.patch > from_version.patch:
                return to_version
        
        raise ValueError(
            f"Adapters only support N → N+1 transitions. "
            f"Got {from_version.version_string} → {to_version.version_string}"
        )
    
    @property
    def identifier(self) -> str:
        """Returns adapter identifier as 'name@v1→v2'"""
        return f"{self.from_version.identifier}→{self.to_version.identifier}"


class ToolInvocationResult(BaseModel):
    """
    Result of tool execution with metadata.
    """
    success: bool = Field(..., description="Whether execution succeeded")
    result: Optional[Any] = Field(default=None, description="Tool execution result")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    
    # Metadata
    tool_name: str = Field(..., description="Tool name")
    requested_version: str = Field(..., description="Version requested by agent")
    executed_version: str = Field(..., description="Actual version executed")
    adapter_used: Optional[str] = Field(default=None, description="Adapter applied, if any")
    warnings: List[str] = Field(default_factory=list, description="Warnings generated")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Execution timestamp")
    
    class Config:
        arbitrary_types_allowed = True


class ToolUsageRecord(BaseModel):
    """
    Record of tool usage for tracking and analytics.
    """
    tool_name: str
    version: str
    agent_id: str
    call_count: int = 1
    last_used: datetime = Field(default_factory=datetime.utcnow)
    warnings: List[str] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
