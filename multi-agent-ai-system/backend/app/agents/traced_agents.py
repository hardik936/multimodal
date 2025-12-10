"""
Tracing wrapper for finalizer, planner, executor, and coder agents.

This module wraps the existing agent functions with distributed tracing.
"""

import time
from app.observability.tracing import get_tracer, trace_span, add_span_attributes

# Import original agent functions
from app.agents import planner as planner_module
from app.agents import executor as executor_module
from app.agents import coder as coder_module
from app.agents import finalizer as finalizer_module

# Create tracers
planner_tracer = get_tracer("agent.planner")
executor_tracer = get_tracer("agent.executor")
coder_tracer = get_tracer("agent.coder")
finalizer_tracer = get_tracer("agent.finalizer")


def traced_planner_node(state: dict):
    """Planner node with tracing."""
    with trace_span(
        planner_tracer,
        "agent.execute",
        attributes={
            "agent.id": "planner",
            "agent.role": "planner",
            "agent.name": "Planner",
            "agent.query_complexity": state.get("query_complexity", "UNKNOWN"),
        }
    ) as agent_span:
        # Call original planner
        result = planner_module.planner_node(state)
        return result


def traced_executor_node(state: dict):
    """Executor node with tracing."""
    with trace_span(
        executor_tracer,
        "agent.execute",
        attributes={
            "agent.id": "executor",
            "agent.role": "executor",
            "agent.name": "Executor",
            "agent.query_complexity": state.get("query_complexity", "UNKNOWN"),
        }
    ) as agent_span:
        # Call original executor
        result = executor_module.executor_node(state)
        return result


def traced_coder_node(state: dict):
    """Coder node with tracing."""
    with trace_span(
        coder_tracer,
        "agent.execute",
        attributes={
            "agent.id": "coder",
            "agent.role": "coder",
            "agent.name": "Coder",
            "agent.query_complexity": state.get("query_complexity", "UNKNOWN"),
        }
    ) as agent_span:
        # Call original coder
        result = coder_module.coder_node(state)
        return result


def traced_finalizer_node(state: dict):
    """Finalizer node with tracing."""
    with trace_span(
        finalizer_tracer,
        "agent.execute",
        attributes={
            "agent.id": "finalizer",
            "agent.role": "finalizer",
            "agent.name": "Finalizer",
            "agent.query_complexity": state.get("query_complexity", "UNKNOWN"),
        }
    ) as agent_span:
        # Call original finalizer
        result = finalizer_module.finalizer_node(state)
        return result
