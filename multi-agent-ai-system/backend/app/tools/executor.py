"""
Tool Executor - Public API for tool invocation with versioning support.

This is the SINGLE AUTHORITATIVE ENTRY POINT for all tool execution.
All tool calls must flow through execute_tool().
"""

from typing import Dict, Any, Optional
import time
import logging

from .models import ToolInvocationResult, DeprecationPolicy
from .registry import tool_registry
from .adapters import adapter_registry
from .validation import validate_input, SchemaValidationError, format_validation_error
from .tracking import usage_tracker
from app.observability.tracing import get_tracer, trace_span, add_span_attributes, set_span_error
from app.reliability.retry import retry_with_backoff
from app.reliability.circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException

logger = logging.getLogger(__name__)
tracer = get_tracer("tool.executor")


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    pass


def execute_tool(
    tool_name: str,
    version: str,
    arguments: Dict[str, Any],
    agent_id: str = "unknown"
) -> ToolInvocationResult:
    """
    PUBLIC API: Execute a tool with versioning and compatibility support.
    
    This function guarantees:
    1. Exactly-once schema validation
    2. Deterministic adapter application
    3. Atomic usage tracking
    4. Explicit version resolution
    
    Version Resolution Policy (DETERMINISTIC):
    1. If requested version exists → use it directly
    2. Else, if adapter exists → adapt to lowest compatible non-deprecated version
    3. Else → hard fail with clear error message
    
    Args:
        tool_name: Tool name
        version: Requested version (e.g., "1.0.0")
        arguments: Tool input arguments
        agent_id: Agent identifier for tracking
    
    Returns:
        ToolInvocationResult with execution metadata
    
    Raises:
        ToolExecutionError: If tool not found or execution fails
        SchemaValidationError: If input validation fails
    """
    start_time = time.time()
    requested_identifier = f"{tool_name}@{version}"
    warnings = []
    adapter_used = None
    
    # Create root tool.invoke span
    with trace_span(
        tracer,
        "tool.invoke",
        attributes={
            "tool.name": tool_name,
            "tool.requested_version": version,
            "agent.id": agent_id,
        }
    ) as tool_span:
        try:
            # STEP 1: Version Resolution (Explicit Policy)
            tool_def, executed_version = _resolve_version(
                tool_name, version, warnings
            )
            
            # Add executed version to span
            add_span_attributes(tool_span, {
                "tool.executed_version": executed_version.split("@")[1],
                "tool.deprecated": tool_def.deprecated,
            })
            
            # STEP 2: Check Deprecation Policy
            if tool_def.deprecated:
                deprecation_warning = (
                    tool_def.deprecation_message or
                    f"Tool {tool_def.identifier} is deprecated"
                )
                warnings.append(deprecation_warning)
                logger.warning(deprecation_warning)
                
                # Enforce deprecation policy
                if tool_def.deprecation_policy == DeprecationPolicy.ERROR:
                    raise ToolExecutionError(
                        f"Tool {tool_def.identifier} is deprecated and cannot be used. "
                        f"Policy: ERROR. {deprecation_warning}"
                    )
            
            # STEP 3: Apply Adapter (if needed)
            if executed_version != requested_identifier:
                # Create tool.adapter span
                with trace_span(
                    tracer,
                    "tool.adapter",
                    attributes={
                        "adapter.from_version": requested_identifier.split("@")[1],
                        "adapter.to_version": executed_version.split("@")[1],
                        "adapter.id": f"{requested_identifier}→{executed_version}",
                    }
                ) as adapter_span:
                    try:
                        arguments = adapter_registry.apply(
                            requested_identifier,
                            executed_version,
                            arguments
                        )
                        adapter_used = f"{requested_identifier}→{executed_version}"
                        warnings.append(f"Applied adapter: {adapter_used}")
                        logger.info(f"Applied adapter: {adapter_used}")
                        add_span_attributes(adapter_span, {"adapter.applied": True})
                    except Exception as e:
                        add_span_attributes(adapter_span, {"adapter.applied": False})
                        set_span_error(adapter_span, e)
                        raise ToolExecutionError(f"Adapter application failed: {e}")
            
            # Add adapter info to tool span
            add_span_attributes(tool_span, {
                "tool.adapter_used": adapter_used is not None,
            })
            
            # STEP 4: Schema Validation (Pre-execution, exactly once)
            with trace_span(
                tracer,
                "tool.validate",
                attributes={"tool.name": tool_name}
            ) as validation_span:
                try:
                    validated_input = validate_input(
                        tool_def.identifier,
                        tool_def.input_schema,
                        arguments
                    )
                    add_span_attributes(validation_span, {"validation.status": "ok"})
                except SchemaValidationError as e:
                    # Mark validation span as failed
                    add_span_attributes(validation_span, {
                        "validation.status": "failed",
                        "validation.error_type": "schema_error",
                    })
                    set_span_error(validation_span, e)
                    
                    # Re-raise with formatted message
                    error_msg = format_validation_error(e)
                    logger.error(error_msg)
                    raise
            
            # STEP 5: Execute Tool
            try:
                # Convert Pydantic model to dict for function call
                input_dict = validated_input.model_dump()
                
                # Get circuit breaker for this specific tool
                # We use the resolved identifier to isolate versions if needed
                # e.g. "web_search@1.0.0"
                cb_name = f"tool:{executed_version}"
                circuit_breaker = get_circuit_breaker(cb_name, failure_threshold=5, recovery_timeout=30)
                
                # Define the execution logic to be wrapped
                def _run_tool():
                    return tool_def.implementation(**input_dict)
                
                # Define retry wrapper
                # We only retry on RuntimeErrors or specific transient issues, 
                # NOT on SchemaValidation (which is already caught above) 
                # or deterministic Logic errors if possible.
                # For now, we retry on general Exceptions excluding specific ones if we had them.
                @retry_with_backoff(max_attempts=3, initial_delay=0.1, retry_on=[Exception])
                def _run_with_retry():
                    return circuit_breaker.call(_run_tool)

                # Execute with reliability patterns
                result = _run_with_retry()
                
                success = True
                error = None
                add_span_attributes(tool_span, {"tool.status": "success", "circuit_breaker.id": cb_name})

            except CircuitBreakerOpenException as e:
                logger.warning(f"Circuit {cb_name} OPEN. Failing tool execution.")
                result = None
                success = False
                error = f"Circuit Breaker OPEN: {str(e)}"
                add_span_attributes(tool_span, {
                    "tool.status": "circuit_open", 
                    "circuit_breaker.state": "OPEN",
                    "circuit_breaker.id": cb_name
                })
                # We do NOT raise here to allow for graceful degradation if the caller handles success=False
                # But the current contract raises exceptions or returns ToolInvocationResult. 
                # The code below returns ToolInvocationResult even on failure (but `result` is None)
                # UNLESS an exception raised.
                # The existing code swallowed exceptions in the `except Exception` block below 
                # and returned result=None, success=False. Use that pattern.
                pass 

            except Exception as e:
                logger.error(f"Tool execution failed for {tool_def.identifier}: {e}")
                result = None
                success = False
                error = str(e)
                add_span_attributes(tool_span, {"tool.status": "runtime_error"})
                set_span_error(tool_span, e)
            
            # STEP 6: Usage Tracking (Atomic)
            execution_time_ms = (time.time() - start_time) * 1000
            usage_tracker.record_usage(
                tool_name=tool_name,
                version=executed_version.split("@")[1],  # Extract version part
                agent_id=agent_id,
                warnings=warnings if warnings else None
            )
            
            # Add execution time to span
            add_span_attributes(tool_span, {"tool.execution_time_ms": execution_time_ms})
            
            # STEP 7: Return Result
            return ToolInvocationResult(
                success=success,
                result=result,
                error=error,
                tool_name=tool_name,
                requested_version=version,
                executed_version=executed_version.split("@")[1],
                adapter_used=adapter_used,
                warnings=warnings,
                execution_time_ms=execution_time_ms
            )
    
        except SchemaValidationError:
            # Re-raise validation errors as-is
            add_span_attributes(tool_span, {"tool.status": "validation_error"})
            raise
        
        except ToolExecutionError:
            # Re-raise execution errors as-is
            add_span_attributes(tool_span, {"tool.status": "execution_error"})
            raise
        
        except Exception as e:
            # Catch-all for unexpected errors
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Unexpected error executing {requested_identifier}: {e}")
            add_span_attributes(tool_span, {"tool.status": "unexpected_error"})
            set_span_error(tool_span, e)
            raise ToolExecutionError(f"Unexpected error: {e}")


def _resolve_version(tool_name: str, version: str, warnings: list) -> tuple:
    """
    Resolve tool version using explicit policy.
    
    Policy:
    1. If requested version exists → use it directly
    2. Else, if adapter exists → adapt to lowest compatible non-deprecated version
    3. Else → hard fail
    
    Args:
        tool_name: Tool name
        version: Requested version
        warnings: List to append warnings to
    
    Returns:
        Tuple of (ToolDefinition, executed_version_identifier)
    
    Raises:
        ToolExecutionError: If version cannot be resolved
    """
    requested_identifier = f"{tool_name}@{version}"
    
    # POLICY STEP 1: Check if requested version exists
    tool_def = tool_registry.get(requested_identifier)
    if tool_def:
        logger.debug(f"Using requested version: {requested_identifier}")
        return tool_def, requested_identifier
    
    # POLICY STEP 2: Check for adapter to compatible version
    # Get all non-deprecated versions
    non_deprecated_versions = tool_registry.get_non_deprecated_versions(tool_name)
    
    if not non_deprecated_versions:
        raise ToolExecutionError(
            f"Tool {tool_name} not found. No versions registered."
        )
    
    # Try to find adapter to lowest compatible version
    # Sort versions (lowest first for "lowest compatible" policy)
    non_deprecated_versions.sort(key=lambda v: (v.major, v.minor, v.patch))
    
    for target_version in non_deprecated_versions:
        target_identifier = target_version.identifier
        
        # Check if adapter exists
        if adapter_registry.has_adapter(requested_identifier, target_identifier):
            tool_def = tool_registry.get(target_identifier)
            warning = (
                f"Requested version {requested_identifier} not found. "
                f"Using adapter to {target_identifier}"
            )
            warnings.append(warning)
            logger.warning(warning)
            return tool_def, target_identifier
    
    # POLICY STEP 3: Hard fail - no version or adapter found
    available_versions = [v.version_string for v in tool_registry.get_versions(tool_name)]
    raise ToolExecutionError(
        f"Tool version {requested_identifier} not found and no compatible adapter exists. "
        f"Available versions: {', '.join(available_versions)}"
    )
