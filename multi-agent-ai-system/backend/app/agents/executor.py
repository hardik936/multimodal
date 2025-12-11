from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings

def executor_node(state: dict):
    """
    Executor agent:
    - Provides brief technical notes for complex queries.
    - Skips execution for simple informational queries.
    - Input keys: "plan_data" and "query_complexity".
    - Output: brief technical notes (or null for simple queries).
    """
    plan_data = state.get("plan_data")
    query_complexity = state.get("query_complexity", "SIMPLE")
    
    # Skip execution for simple queries
    if query_complexity == "SIMPLE":
        print("Skipping execution for SIMPLE query")
        return {"execution_data": None}
    
    # For complex queries, provide brief technical notes
    llm = ChatGroq(model_name=settings.GROQ_MODEL, api_key=settings.GROQ_API_KEY)
    
    prompt = ChatPromptTemplate.from_template(
        "You are an executor agent documenting what was done internally.\n\n"
        "Plan: {plan_data}\n\n"
        "Provide a BRIEF technical note (2-3 sentences maximum) describing:\n"
        "- What research/analysis was performed\n"
        "- What data sources were consulted\n"
        "- Any synthesis or processing that occurred\n\n"
        "CRITICAL RULES:\n"
        "- This is an INTERNAL technical note, NOT user instructions\n"
        "- Do NOT tell users to 'open browser', 'search Google', 'visit websites', etc.\n"
        "- Do NOT provide step-by-step manual execution guides\n"
        "- Keep it to 2-3 sentences maximum\n"
        "- Focus on what the SYSTEM did, not what the user should do\n\n"
        "Example: 'Performed web search across 3 queries, analyzed 9 sources, and synthesized findings into structured summary.'"
    )
    
    # Setup cost tracking
    from app.costs.langchain_callback import CostTrackingCallbackHandler
    workflow_id = state.get("active_workflow_id")
    agent_id = state.get("active_agent_id", "executor")
    
    callbacks = [CostTrackingCallbackHandler(workflow_id=workflow_id, agent_id=agent_id)]
    
    chain = prompt | llm
    try:
        response = chain.invoke({"plan_data": plan_data}, config={"callbacks": callbacks})
        content = response.content
    except Exception as e:
        print(f"Execution documentation error: {e}")
        content = None
    
    return {"execution_data": content}

