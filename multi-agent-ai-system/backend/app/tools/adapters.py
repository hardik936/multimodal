"""
Compatibility Adapter Registry - Manages version-to-version adapters.

Provides registration and resolution of compatibility adapters for tool evolution.
"""

from typing import Dict, Optional, Callable, Any
import logging

from .models import ToolVersion, ToolAdapter

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """
    Registry for compatibility adapters between tool versions.
    
    Responsibilities:
    - Register N→N+1 adapters
    - Validate adapter constraints
    - Resolve adapter for version transitions
    - Apply transformations
    
    CONSTRAINTS:
    - Adapters must be pure, deterministic functions
    - Only single-hop transitions allowed (N→N+1)
    - No multi-hop adapter chaining
    """
    
    def __init__(self):
        # Key: "from_identifier→to_identifier", Value: ToolAdapter
        self._adapters: Dict[str, ToolAdapter] = {}
    
    def register(
        self,
        from_version: str,
        to_version: str,
        adapter_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        description: Optional[str] = None,
    ) -> ToolAdapter:
        """
        Register a compatibility adapter.
        
        Args:
            from_version: Source version identifier (e.g., "weather_api@1.0.0")
            to_version: Target version identifier (e.g., "weather_api@2.0.0")
            adapter_fn: Pure function that transforms input
            description: Adapter description
        
        Returns:
            ToolAdapter: The registered adapter
        
        Raises:
            ValueError: If adapter violates constraints (not N→N+1)
        """
        # Parse versions
        from_ver = ToolVersion.from_string(from_version)
        to_ver = ToolVersion.from_string(to_version)
        
        # Create adapter (validation happens in ToolAdapter model)
        adapter = ToolAdapter(
            from_version=from_ver,
            to_version=to_ver,
            adapter_fn=adapter_fn,
            description=description,
        )
        
        # Check if already registered
        if adapter.identifier in self._adapters:
            raise ValueError(f"Adapter {adapter.identifier} is already registered")
        
        # Register
        self._adapters[adapter.identifier] = adapter
        
        logger.info(f"Registered adapter: {adapter.identifier}")
        return adapter
    
    def get(self, from_version: str, to_version: str) -> Optional[ToolAdapter]:
        """
        Get adapter for version transition.
        
        Args:
            from_version: Source version identifier
            to_version: Target version identifier
        
        Returns:
            ToolAdapter if found, None otherwise
        """
        identifier = f"{from_version}→{to_version}"
        return self._adapters.get(identifier)
    
    def has_adapter(self, from_version: str, to_version: str) -> bool:
        """
        Check if adapter exists for version transition.
        
        Args:
            from_version: Source version identifier
            to_version: Target version identifier
        
        Returns:
            True if adapter exists, False otherwise
        """
        return self.get(from_version, to_version) is not None
    
    def apply(
        self,
        from_version: str,
        to_version: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply adapter transformation.
        
        Args:
            from_version: Source version identifier
            to_version: Target version identifier
            input_data: Input data in source schema
        
        Returns:
            Transformed data in target schema
        
        Raises:
            ValueError: If no adapter found
            Exception: If adapter function fails
        """
        adapter = self.get(from_version, to_version)
        
        if not adapter:
            raise ValueError(
                f"No adapter found for {from_version} → {to_version}"
            )
        
        try:
            transformed_data = adapter.adapter_fn(input_data)
            logger.debug(f"Applied adapter: {adapter.identifier}")
            return transformed_data
        except Exception as e:
            logger.error(f"Adapter {adapter.identifier} failed: {e}")
            raise
    
    def list_adapters_for_tool(self, tool_name: str) -> list[str]:
        """
        List all adapters for a specific tool.
        
        Args:
            tool_name: Tool name
        
        Returns:
            List of adapter identifiers
        """
        return [
            adapter_id
            for adapter_id in self._adapters.keys()
            if adapter_id.startswith(f"{tool_name}@")
        ]
    
    def list_all_adapters(self) -> list[str]:
        """
        List all registered adapters.
        
        Returns:
            List of adapter identifiers
        """
        return list(self._adapters.keys())


# Global singleton adapter registry
adapter_registry = AdapterRegistry()
