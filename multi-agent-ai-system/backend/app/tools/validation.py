"""
Schema Validation Layer - Pre-execution validation of tool inputs.

Provides strict schema validation using Pydantic before tool execution.
"""

from typing import Dict, Any, Type
from pydantic import BaseModel, ValidationError
import logging

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """
    Raised when tool input fails schema validation.
    """
    def __init__(self, tool_identifier: str, errors: list):
        self.tool_identifier = tool_identifier
        self.errors = errors
        super().__init__(f"Schema validation failed for {tool_identifier}: {errors}")


def validate_input(
    tool_identifier: str,
    input_schema: Type[BaseModel],
    input_data: Dict[str, Any]
) -> BaseModel:
    """
    Validate tool input against Pydantic schema.
    
    This validation occurs BEFORE tool execution, outside of agent reasoning.
    No silent coercion or best-guess argument mapping is allowed.
    
    Args:
        tool_identifier: Tool identifier for error messages
        input_schema: Pydantic model class
        input_data: Input data to validate
    
    Returns:
        Validated Pydantic model instance
    
    Raises:
        SchemaValidationError: If validation fails
    """
    try:
        # Strict validation - no extra fields allowed
        validated = input_schema(**input_data)
        logger.debug(f"Schema validation passed for {tool_identifier}")
        return validated
    
    except ValidationError as e:
        # Extract validation errors
        errors = []
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            error_type = error["type"]
            errors.append({
                "field": field,
                "message": msg,
                "type": error_type
            })
        
        logger.error(f"Schema validation failed for {tool_identifier}: {errors}")
        raise SchemaValidationError(tool_identifier, errors)
    
    except Exception as e:
        # Unexpected error during validation
        logger.error(f"Unexpected validation error for {tool_identifier}: {e}")
        raise SchemaValidationError(tool_identifier, [{"error": str(e)}])


def format_validation_error(error: SchemaValidationError) -> str:
    """
    Format validation error for user-friendly display.
    
    Args:
        error: SchemaValidationError instance
    
    Returns:
        Formatted error message
    """
    lines = [f"Tool {error.tool_identifier} - Schema Validation Failed:"]
    
    for err in error.errors:
        if "field" in err:
            lines.append(f"  • Field '{err['field']}': {err['message']}")
        else:
            lines.append(f"  • {err.get('error', 'Unknown error')}")
    
    return "\n".join(lines)
