"""
Tool Registry - Central registry for versioned tools.

Provides registration, lookup, and version management for tools.
"""

from typing import Dict, List, Optional, Type, Callable
from pydantic import BaseModel
import logging

from .models import ToolVersion, ToolDefinition, DeprecationPolicy

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry for versioned tools.
    
    Responsibilities:
    - Register tools with semantic versions
    - Store Pydantic schemas for validation
    - Track deprecation status
    - Query available versions
    """
    
    def __init__(self):
        # Key: tool_identifier (name@version), Value: ToolDefinition
        self._tools: Dict[str, ToolDefinition] = {}
        
        # Key: tool_name, Value: List of versions
        self._versions_by_name: Dict[str, List[ToolVersion]] = {}
    
    def register(
        self,
        name: str,
        version: str,
        input_schema: Type[BaseModel],
        implementation: Callable,
        deprecated: bool = False,
        deprecation_policy: DeprecationPolicy = DeprecationPolicy.WARN,
        deprecation_message: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ToolDefinition:
        """
        Register a tool with the registry.
        
        Args:
            name: Tool name
            version: Version string (e.g., "1.2.3")
            input_schema: Pydantic model for input validation
            implementation: Tool implementation function
            deprecated: Whether this version is deprecated
            deprecation_policy: How to handle deprecated usage
            deprecation_message: Custom deprecation message
            description: Tool description
        
        Returns:
            ToolDefinition: The registered tool definition
        
        Raises:
            ValueError: If tool version already registered
        """
        # Parse version
        tool_version = ToolVersion.from_string(f"{name}@{version}")
        
        # Check if already registered
        if tool_version.identifier in self._tools:
            raise ValueError(f"Tool {tool_version.identifier} is already registered")
        
        # Create tool definition
        tool_def = ToolDefinition(
            name=name,
            version=tool_version,
            input_schema=input_schema,
            implementation=implementation,
            deprecated=deprecated,
            deprecation_policy=deprecation_policy,
            deprecation_message=deprecation_message,
            description=description,
        )
        
        # Register
        self._tools[tool_version.identifier] = tool_def
        
        # Track versions by name
        if name not in self._versions_by_name:
            self._versions_by_name[name] = []
        self._versions_by_name[name].append(tool_version)
        
        # Sort versions (newest first)
        self._versions_by_name[name].sort(
            key=lambda v: (v.major, v.minor, v.patch),
            reverse=True
        )
        
        logger.info(f"Registered tool: {tool_version.identifier}")
        if deprecated:
            logger.warning(f"Tool {tool_version.identifier} is marked as deprecated")
        
        return tool_def
    
    def get(self, tool_identifier: str) -> Optional[ToolDefinition]:
        """
        Get tool definition by identifier (name@version).
        
        Args:
            tool_identifier: Tool identifier (e.g., "weather_api@1.0.0")
        
        Returns:
            ToolDefinition if found, None otherwise
        """
        return self._tools.get(tool_identifier)
    
    def get_by_name_and_version(self, name: str, version: str) -> Optional[ToolDefinition]:
        """
        Get tool definition by name and version string.
        
        Args:
            name: Tool name
            version: Version string (e.g., "1.0.0")
        
        Returns:
            ToolDefinition if found, None otherwise
        """
        identifier = f"{name}@{version}"
        return self.get(identifier)
    
    def get_versions(self, tool_name: str) -> List[ToolVersion]:
        """
        Get all registered versions for a tool (sorted newest first).
        
        Args:
            tool_name: Tool name
        
        Returns:
            List of ToolVersion objects
        """
        return self._versions_by_name.get(tool_name, [])
    
    def get_latest_version(self, tool_name: str, include_deprecated: bool = False) -> Optional[ToolVersion]:
        """
        Get the latest version of a tool.
        
        Args:
            tool_name: Tool name
            include_deprecated: Whether to include deprecated versions
        
        Returns:
            Latest ToolVersion if found, None otherwise
        """
        versions = self.get_versions(tool_name)
        
        if not include_deprecated:
            # Filter out deprecated versions
            versions = [
                v for v in versions
                if not self.get(v.identifier).deprecated
            ]
        
        return versions[0] if versions else None
    
    def get_non_deprecated_versions(self, tool_name: str) -> List[ToolVersion]:
        """
        Get all non-deprecated versions for a tool.
        
        Args:
            tool_name: Tool name
        
        Returns:
            List of non-deprecated ToolVersion objects
        """
        versions = self.get_versions(tool_name)
        return [
            v for v in versions
            if not self.get(v.identifier).deprecated
        ]
    
    def list_all_tools(self) -> List[str]:
        """
        List all registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self._versions_by_name.keys())
    
    def list_all_versions(self) -> List[str]:
        """
        List all registered tool identifiers.
        
        Returns:
            List of tool identifiers (name@version)
        """
        return list(self._tools.keys())
    
    def deprecate(
        self,
        tool_identifier: str,
        policy: DeprecationPolicy = DeprecationPolicy.WARN,
        message: Optional[str] = None
    ) -> bool:
        """
        Mark a tool version as deprecated.
        
        Args:
            tool_identifier: Tool identifier (e.g., "weather_api@1.0.0")
            policy: Deprecation policy
            message: Custom deprecation message
        
        Returns:
            True if successful, False if tool not found
        """
        tool_def = self.get(tool_identifier)
        if not tool_def:
            logger.error(f"Cannot deprecate: Tool {tool_identifier} not found")
            return False
        
        tool_def.deprecated = True
        tool_def.deprecation_policy = policy
        if message:
            tool_def.deprecation_message = message
        
        logger.warning(f"Deprecated tool: {tool_identifier} (policy: {policy.value})")
        return True


# Global singleton registry
tool_registry = ToolRegistry()
