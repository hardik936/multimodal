"""
Tool Versioning and Compatibility Management System

This package provides production-grade tool versioning infrastructure to prevent
silent tool failures and enable safe tool evolution without redeploying agents.
"""

from .models import (
    ToolVersion,
    ToolDefinition,
    ToolAdapter,
    DeprecationPolicy,
    ToolInvocationResult,
)
from .registry import tool_registry
from .adapters import adapter_registry
from .tracking import usage_tracker
from .executor import execute_tool

__all__ = [
    "ToolVersion",
    "ToolDefinition",
    "ToolAdapter",
    "DeprecationPolicy",
    "ToolInvocationResult",
    "tool_registry",
    "adapter_registry",
    "usage_tracker",
    "execute_tool",
]
