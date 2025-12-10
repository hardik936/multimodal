from typing import TypedDict, List, Annotated, Any
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.agents.researcher import research_node
from app.agents.traced_agents import (
    traced_planner_node as planner_node,
    traced_executor_node as executor_node,
    traced_coder_node as coder_node,
    traced_finalizer_node as finalizer_node,
)

class AgentState(TypedDict):
    input: str
    language: str
    mode: str
    query_complexity: str  # NEW: "SIMPLE" or "COMPLEX"
    research_data: str
    plan_data: Any # dict or list or None
    execution_data: str
    code_data: str
    final_output: str  # NEW: Always populated by finalizer
    messages: Annotated[List[BaseMessage], add_messages]

def should_continue_after_research(state: AgentState):
    """
    For SIMPLE queries: go directly to finalizer (skip planner/executor/coder)
    For COMPLEX queries: go to planner for full pipeline
    """
    query_complexity = state.get("query_complexity", "SIMPLE")
    
    # Also respect mode for backward compatibility
    if state.get("mode") == "research_only":
        return "finalizer"
    
    # Skip planner/executor/coder for simple queries
    if query_complexity == "SIMPLE":
        print("Skipping planner/executor/coder for SIMPLE query")
        return "finalizer"
    
    return "planner"

def should_continue_after_plan(state: AgentState):
    if state.get("mode") == "plan_only":
        return "finalizer"
    return "executor"

def create_graph():
    workflow = StateGraph(AgentState)
    
    # Add all nodes including the new finalizer
    workflow.add_node("researcher", research_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("finalizer", finalizer_node)
    
    workflow.set_entry_point("researcher")
    
    workflow.add_conditional_edges(
        "researcher",
        should_continue_after_research,
        {
            "finalizer": "finalizer",
            "planner": "planner"
        }
    )
    
    workflow.add_conditional_edges(
        "planner",
        should_continue_after_plan,
        {
            "finalizer": "finalizer",
            "executor": "executor"
        }
    )
    
    workflow.add_edge("executor", "coder")
    workflow.add_edge("coder", "finalizer")  # Always go to finalizer
    workflow.add_edge("finalizer", END)  # Finalizer is the last step before END
    
    return workflow.compile()

graph = create_graph()

# Alias for compatibility with huey_tasks
def create_multi_agent_workflow(config: dict = None):
    # In the future, config can be used to customize the graph
    return create_graph()

