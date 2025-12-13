"""
Example: Calculator Tool with Minor Version Updates

Demonstrates:
- Minor version evolution (backward-compatible)
- Optional parameter additions
- Adapter for backward compatibility
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

from app.tools import tool_registry, adapter_registry


# ============================================================================
# VERSION 1.0.0 (ORIGINAL)
# ============================================================================

class CalculatorInputV1(BaseModel):
    """Input schema for calculator@1.0.0"""
    operation: str = Field(..., description="Operation: 'add', 'subtract', 'multiply', 'divide'")
    a: float = Field(..., description="First number")
    b: float = Field(..., description="Second number")


def calculator_v1_impl(operation: str, a: float, b: float) -> Dict[str, Any]:
    """Implementation for calculator@1.0.0"""
    operations = {
        "add": a + b,
        "subtract": a - b,
        "multiply": a * b,
        "divide": a / b if b != 0 else None
    }
    
    result = operations.get(operation)
    
    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result,
        "error": "Division by zero" if result is None and operation == "divide" else None
    }


# Register v1.0.0
tool_registry.register(
    name="calculator",
    version="1.0.0",
    input_schema=CalculatorInputV1,
    implementation=calculator_v1_impl,
    deprecated=False,
    description="Basic calculator with four operations"
)


# ============================================================================
# VERSION 1.1.0 (BACKWARD-COMPATIBLE ENHANCEMENT)
# ============================================================================

class CalculatorInputV1_1(BaseModel):
    """Input schema for calculator@1.1.0"""
    operation: str = Field(..., description="Operation: 'add', 'subtract', 'multiply', 'divide', 'power', 'modulo'")
    a: float = Field(..., description="First number")
    b: float = Field(..., description="Second number")
    precision: Optional[int] = Field(default=None, description="Decimal precision for result")


def calculator_v1_1_impl(operation: str, a: float, b: float, precision: Optional[int] = None) -> Dict[str, Any]:
    """
    Implementation for calculator@1.1.0
    
    ENHANCEMENTS:
    - Added 'power' and 'modulo' operations
    - Added optional precision parameter
    """
    operations = {
        "add": a + b,
        "subtract": a - b,
        "multiply": a * b,
        "divide": a / b if b != 0 else None,
        "power": a ** b,
        "modulo": a % b if b != 0 else None
    }
    
    result = operations.get(operation)
    
    # Apply precision if specified
    if result is not None and precision is not None:
        result = round(result, precision)
    
    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result,
        "precision": precision,
        "error": "Division by zero" if result is None and operation in ["divide", "modulo"] else None
    }


# Register v1.1.0
tool_registry.register(
    name="calculator",
    version="1.1.0",
    input_schema=CalculatorInputV1_1,
    implementation=calculator_v1_1_impl,
    deprecated=False,
    description="Enhanced calculator with power, modulo, and precision control"
)


# ============================================================================
# COMPATIBILITY ADAPTER: 1.0.0 → 1.1.0
# ============================================================================

def adapt_calculator_v1_to_v1_1(input_v1: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adapter from v1.0.0 to v1.1.0
    
    Since v1.1.0 is backward-compatible, we just pass through the input
    and add default value for new optional parameter.
    """
    return {
        **input_v1,
        "precision": None  # Default for new optional parameter
    }


# Register adapter
adapter_registry.register(
    from_version="calculator@1.0.0",
    to_version="calculator@1.1.0",
    adapter_fn=adapt_calculator_v1_to_v1_1,
    description="Pass-through adapter for backward-compatible v1.1.0 enhancement"
)


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    from app.tools import execute_tool
    
    print("=" * 60)
    print("Calculator Tool - Minor Version Evolution Demo")
    print("=" * 60)
    
    # Example 1: Call v1.1.0 with new features
    print("\n1. Calling calculator@1.1.0 with power operation:")
    result = execute_tool(
        tool_name="calculator",
        version="1.1.0",
        arguments={"operation": "power", "a": 2, "b": 8, "precision": 2},
        agent_id="demo_agent"
    )
    print(f"   Result: {result.result}")
    
    # Example 2: Call v1.0.0 (will use adapter to v1.1.0)
    print("\n2. Calling calculator@1.0.0 (adapter to v1.1.0):")
    result = execute_tool(
        tool_name="calculator",
        version="1.0.0",
        arguments={"operation": "multiply", "a": 7, "b": 6},
        agent_id="demo_agent"
    )
    print(f"   Executed Version: {result.executed_version}")
    print(f"   Adapter Used: {result.adapter_used}")
    print(f"   Result: {result.result}")
