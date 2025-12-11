"""
Tracing wrapper for finalizer, planner, executor, and coder agents.

This module wraps the existing agent functions with distributed tracing.
"""

import time
import logging
from typing import Callable, Dict, Any
from app.observability.tracing import get_tracer, trace_span, add_span_attributes, set_span_error
from app.reliability.checkpoint import save_checkpoint

# Import original agent functions
from app.agents import planner as planner_module
from app.agents import executor as executor_module
from app.agents import coder as coder_module
from app.agents import finalizer as finalizer_module

logger = logging.getLogger(__name__)

# Create tracers
planner_tracer = get_tracer("agent.planner")
executor_tracer = get_tracer("agent.executor")
coder_tracer = get_tracer("agent.coder")
finalizer_tracer = get_tracer("agent.finalizer")


def _execute_with_reliability(
    tracer, 
    agent_id: str, 
    agent_name: str, 
    node_func: Callable[[Dict], Dict], 
    state: Dict
) -> Dict:
    """
    Helper to execute an agent node with tracing, checkpointing, and error handling.
    """
    workflow_id = state.get("workflow_id", "unknown_workflow")
    
    # 1. Checkpoint before execution
    try:
        # We save a lightweight snapshot - just the agent ID for now or full state if serializable.
        # State might contain non-serializable objects (like messages with local objects), 
        # so we rely on checkpoint utility's best effort or filter it.
        # For now, pass full state and let checkpoint utility handle/serialize what it can.
        save_checkpoint(workflow_id, agent_id, state)
    except Exception as e:
        logger.warning(f"Failed to save checkpoint for {agent_id}: {e}")

    # 2. Execution with Tracing and Error Handling
    with trace_span(
        tracer,
        "agent.execute",
        attributes={
            "agent.id": agent_id,
            "agent.role": agent_id,
            "agent.name": agent_name,
            "agent.query_complexity": state.get("query_complexity", "UNKNOWN"),
            "workflow.id": workflow_id
        }
    ) as agent_span:
        try:
            # Inject context into state so inner functions can pick it up
            # Note: Agents must pass this down to LLM calls if not using a global context contextvar.
            # Since our agents take `state` as input, this is a clean way to pass metadata.
            # We'll augment the state dict passed to the node function.
            state_with_context = state.copy()
            state_with_context["active_workflow_id"] = workflow_id
            state_with_context["active_agent_id"] = agent_id
            
            result = node_func(state_with_context)
            add_span_attributes(agent_span, {"agent.status": "success"})
            return result
            
        except Exception as e:
            logger.error(f"Agent {agent_name} ({agent_id}) failed: {e}")
            set_span_error(agent_span, e)
            add_span_attributes(agent_span, {"agent.status": "failed"})
            
            # 3. Graceful Degradation / Fallback logic
            # If the agent fails, we can either re-raise or return a partial state so next steps can handle it.
            # For now, we propagate the error up to the graph runner unless a specific fallback is requested.
            # User request: "Route to a 'human_required' outcome flag"
            
            # Simple fallback for critical agents to avoid crashing the whole graph immediately if possible,
            # but ideally, graph flows should handle this. 
            # We'll re-raise so the graph or outer runner catches it, OR we return a dummy result if that's safer.
            # Given "prevent cascading failures", maybe returning a status update is better.
            
            # Let's try to return a failure indicator in the state update if the graph supports it.
            # But the node outputs a dict merged into state.
            # We'll fail hard for now as per "allow workflow designers to specify... fallback".
            # Without explicit configuration passed in, strict failure is safer than silent corruption.
            raise e


def traced_planner_node(state: dict):
    """Planner node with tracing and reliability."""
    return _execute_with_reliability(
        planner_tracer, "planner", "Planner", planner_module.planner_node, state
    )


def traced_executor_node(state: dict):
    """Executor node with tracing and reliability."""
    return _execute_with_reliability(
        executor_tracer, "executor", "Executor", executor_module.executor_node, state
    )


def traced_coder_node(state: dict):
    """Coder node with tracing and reliability."""
    return _execute_with_reliability(
        coder_tracer, "coder", "Coder", coder_module.coder_node, state
    )


def traced_finalizer_node(state: dict):
    """Finalizer node with tracing and reliability."""
    return _execute_with_reliability(
        finalizer_tracer, "finalizer", "Finalizer", finalizer_module.finalizer_node, state
    )
