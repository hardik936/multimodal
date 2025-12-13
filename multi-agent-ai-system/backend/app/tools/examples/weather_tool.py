"""
Example: Weather API Tool with Version Evolution

Demonstrates:
- Breaking change (v1 → v2): Schema change
- Compatibility adapter
- Deprecation with policy enforcement
"""

from pydantic import BaseModel, Field
from typing import Dict, Any

from app.tools import tool_registry, adapter_registry, DeprecationPolicy


# ============================================================================
# VERSION 1.0.0 (DEPRECATED)
# ============================================================================

class WeatherInputV1(BaseModel):
    """Input schema for weather_api@1.0.0"""
    city: str = Field(..., description="City name")
    country: str = Field(..., description="Country code (e.g., 'US')")


def weather_api_v1_impl(city: str, country: str) -> Dict[str, Any]:
    """
    Implementation for weather_api@1.0.0
    
    NOTE: This is a mock implementation for demonstration.
    In production, this would call a real weather API.
    """
    return {
        "temperature": 72,
        "condition": "Sunny",
        "location": f"{city}, {country}",
        "humidity": 65,
        "wind_speed": 10
    }


# Register v1.0.0 (deprecated with WARN policy)
tool_registry.register(
    name="weather_api",
    version="1.0.0",
    input_schema=WeatherInputV1,
    implementation=weather_api_v1_impl,
    deprecated=True,
    deprecation_policy=DeprecationPolicy.WARN,
    deprecation_message="weather_api@1.0.0 is deprecated. Please upgrade to 2.0.0 which uses a unified location field.",
    description="Get weather information for a city (v1 - deprecated)"
)


# ============================================================================
# VERSION 2.0.0 (CURRENT)
# ============================================================================

class WeatherInputV2(BaseModel):
    """Input schema for weather_api@2.0.0"""
    location: str = Field(..., description="Location in 'City, Country' format")
    units: str = Field(default="celsius", description="Temperature units: 'celsius' or 'fahrenheit'")


def weather_api_v2_impl(location: str, units: str = "celsius") -> Dict[str, Any]:
    """
    Implementation for weather_api@2.0.0
    
    BREAKING CHANGE: Combined city/country into single location field.
    Added units parameter for temperature.
    """
    # Mock implementation
    temp = 72 if units == "fahrenheit" else 22
    
    return {
        "temperature": temp,
        "units": units,
        "condition": "Sunny",
        "location": location,
        "humidity": 65,
        "wind_speed": 10,
        "forecast": ["Sunny", "Partly Cloudy", "Rainy"]
    }


# Register v2.0.0 (current version)
tool_registry.register(
    name="weather_api",
    version="2.0.0",
    input_schema=WeatherInputV2,
    implementation=weather_api_v2_impl,
    deprecated=False,
    description="Get weather information for a location (v2 - current)"
)


# ============================================================================
# COMPATIBILITY ADAPTER: 1.0.0 → 2.0.0
# ============================================================================

def adapt_weather_v1_to_v2(input_v1: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure, deterministic adapter from v1 to v2 schema.
    
    Transformation:
    - Combine city + country into location
    - Add default units parameter
    """
    return {
        "location": f"{input_v1['city']}, {input_v1['country']}",
        "units": "celsius"  # Default value
    }


# Register adapter
adapter_registry.register(
    from_version="weather_api@1.0.0",
    to_version="weather_api@2.0.0",
    adapter_fn=adapt_weather_v1_to_v2,
    description="Adapt v1 city/country fields to v2 unified location field"
)


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    from app.tools import execute_tool
    
    print("=" * 60)
    print("Weather API Tool - Version Evolution Demo")
    print("=" * 60)
    
    # Example 1: Call v2 directly (current version)
    print("\n1. Calling weather_api@2.0.0 (current version):")
    result = execute_tool(
        tool_name="weather_api",
        version="2.0.0",
        arguments={"location": "San Francisco, US", "units": "fahrenheit"},
        agent_id="demo_agent"
    )
    print(f"   Success: {result.success}")
    print(f"   Result: {result.result}")
    print(f"   Warnings: {result.warnings}")
    
    # Example 2: Call v1 (deprecated, will use adapter)
    print("\n2. Calling weather_api@1.0.0 (deprecated, adapter applied):")
    result = execute_tool(
        tool_name="weather_api",
        version="1.0.0",
        arguments={"city": "New York", "country": "US"},
        agent_id="demo_agent"
    )
    print(f"   Success: {result.success}")
    print(f"   Executed Version: {result.executed_version}")
    print(f"   Adapter Used: {result.adapter_used}")
    print(f"   Result: {result.result}")
    print(f"   Warnings: {result.warnings}")
    
    # Example 3: Schema validation failure
    print("\n3. Schema validation failure (missing required field):")
    try:
        result = execute_tool(
            tool_name="weather_api",
            version="2.0.0",
            arguments={"units": "celsius"},  # Missing 'location'
            agent_id="demo_agent"
        )
    except Exception as e:
        print(f"   Error: {e}")
