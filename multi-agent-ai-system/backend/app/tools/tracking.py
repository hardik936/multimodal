"""
Tool Usage Tracking - Track and analyze tool usage patterns.

Provides tracking of tool calls per agent for impact analysis and deprecation planning.
"""

from typing import Dict, List, Optional
from datetime import datetime
import logging

from .models import ToolUsageRecord

logger = logging.getLogger(__name__)


class UsageTracker:
    """
    Tracks tool usage for analytics and impact analysis.
    
    Responsibilities:
    - Track per-agent tool usage
    - Record call counts and timestamps
    - Log warnings
    - Provide queryable usage data
    """
    
    def __init__(self):
        # Key: "agent_id:tool_identifier", Value: ToolUsageRecord
        self._usage: Dict[str, ToolUsageRecord] = {}
    
    def record_usage(
        self,
        tool_name: str,
        version: str,
        agent_id: str,
        warnings: Optional[List[str]] = None
    ):
        """
        Record a tool usage event.
        
        Args:
            tool_name: Tool name
            version: Version used
            agent_id: Agent identifier
            warnings: List of warnings generated
        """
        key = f"{agent_id}:{tool_name}@{version}"
        
        if key in self._usage:
            # Update existing record
            record = self._usage[key]
            record.call_count += 1
            record.last_used = datetime.utcnow()
            if warnings:
                record.warnings.extend(warnings)
        else:
            # Create new record
            record = ToolUsageRecord(
                tool_name=tool_name,
                version=version,
                agent_id=agent_id,
                call_count=1,
                last_used=datetime.utcnow(),
                warnings=warnings or []
            )
            self._usage[key] = record
        
        logger.debug(f"Recorded usage: {key} (count: {record.call_count})")
    
    def get_usage(self, agent_id: str, tool_name: str, version: str) -> Optional[ToolUsageRecord]:
        """
        Get usage record for specific agent and tool version.
        
        Args:
            agent_id: Agent identifier
            tool_name: Tool name
            version: Tool version
        
        Returns:
            ToolUsageRecord if found, None otherwise
        """
        key = f"{agent_id}:{tool_name}@{version}"
        return self._usage.get(key)
    
    def get_usage_by_agent(self, agent_id: str) -> List[ToolUsageRecord]:
        """
        Get all usage records for an agent.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            List of ToolUsageRecord objects
        """
        return [
            record for key, record in self._usage.items()
            if key.startswith(f"{agent_id}:")
        ]
    
    def get_usage_by_tool(self, tool_name: str) -> List[ToolUsageRecord]:
        """
        Get all usage records for a tool (all versions).
        
        Args:
            tool_name: Tool name
        
        Returns:
            List of ToolUsageRecord objects
        """
        return [
            record for record in self._usage.values()
            if record.tool_name == tool_name
        ]
    
    def get_usage_by_version(self, tool_name: str, version: str) -> List[ToolUsageRecord]:
        """
        Get all usage records for a specific tool version.
        
        Args:
            tool_name: Tool name
            version: Tool version
        
        Returns:
            List of ToolUsageRecord objects
        """
        return [
            record for record in self._usage.values()
            if record.tool_name == tool_name and record.version == version
        ]
    
    def get_deprecated_tool_usage(self) -> List[ToolUsageRecord]:
        """
        Get all usage records that have deprecation warnings.
        
        Returns:
            List of ToolUsageRecord objects with warnings
        """
        return [
            record for record in self._usage.values()
            if record.warnings
        ]
    
    def get_total_calls(self, tool_name: str, version: Optional[str] = None) -> int:
        """
        Get total call count for a tool or tool version.
        
        Args:
            tool_name: Tool name
            version: Optional version filter
        
        Returns:
            Total call count
        """
        if version:
            records = self.get_usage_by_version(tool_name, version)
        else:
            records = self.get_usage_by_tool(tool_name)
        
        return sum(record.call_count for record in records)
    
    def get_agent_count(self, tool_name: str, version: Optional[str] = None) -> int:
        """
        Get number of unique agents using a tool or tool version.
        
        Args:
            tool_name: Tool name
            version: Optional version filter
        
        Returns:
            Number of unique agents
        """
        if version:
            records = self.get_usage_by_version(tool_name, version)
        else:
            records = self.get_usage_by_tool(tool_name)
        
        return len(set(record.agent_id for record in records))


# Global singleton usage tracker
usage_tracker = UsageTracker()
