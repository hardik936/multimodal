from typing import TypedDict, List, Annotated, Any
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.agents.researcher import research_node
from app.agents.planner import planner_node
from app.agents.executor import executor_node
from app.agents.coder import coder_node

class AgentState(TypedDict):
    input: str
    language: str
    mode: str
    research_data: str
    plan_data: Any # dict or list
    execution_data: str
    code_data: str
    messages: Annotated[List[BaseMessage], add_messages]

def should_continue_after_research(state: AgentState):
    if state.get("mode") == "research_only":
        return END
    return "planner"

def should_continue_after_plan(state: AgentState):
    if state.get("mode") == "plan_only":
        return END
    return "executor"

def create_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("researcher", research_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("coder", coder_node)
    
    workflow.set_entry_point("researcher")
    
    workflow.add_conditional_edges(
        "researcher",
        should_continue_after_research,
        {
            END: END,
            "planner": "planner"
        }
    )
    
    workflow.add_conditional_edges(
        "planner",
        should_continue_after_plan,
        {
            END: END,
            "executor": "executor"
        }
    )
    
    workflow.add_edge("executor", "coder")
    workflow.add_edge("coder", END)
    
    return workflow.compile()

graph = create_graph()
