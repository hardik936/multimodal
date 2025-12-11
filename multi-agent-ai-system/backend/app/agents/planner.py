from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings

def planner_node(state: dict):
    """
    Planner agent:
    - Breaks complex tasks into clear, actionable steps.
    - Skips planning for simple informational queries.
    - Input key: "input" (task), "research_data", and "query_complexity".
    - Output: a JSON plan for complex queries, or null for simple queries.
    """
    task = state.get("input")
    research_data = state.get("research_data")
    query_complexity = state.get("query_complexity", "SIMPLE")
    
    # Skip planning for simple queries
    if query_complexity == "SIMPLE":
        print("Skipping planning for SIMPLE query")
        return {"plan_data": None}
    
    # For complex queries, generate a concise high-level plan
    llm = ChatGroq(model_name=settings.GROQ_MODEL, api_key=settings.GROQ_API_KEY)
    
    prompt = ChatPromptTemplate.from_template(
        "You are a planner agent for an autonomous AI research system.\n\n"
        "Task: {task}\n"
        "Research Findings: {research_data}\n\n"
        "Based on the research findings, create a concise high-level action plan.\n\n"
        "IMPORTANT:\n"
        "- This plan describes what the SYSTEM did/will do internally, NOT what the user should do\n"
        "- Focus on the research and synthesis process\n"
        "- Keep it brief and high-level (3-5 steps maximum)\n"
        "- Do NOT include manual user instructions\n"
        "- Do NOT tell users to 'open browser', 'search Google', etc.\n\n"
        "Return a JSON object with a 'steps' key containing the high-level steps.\n"
        "Each step should have 'id', 'description', 'estimated_time', 'dependencies', and 'complexity'.\n"
        "Ensure the output is valid JSON."
    )
    
    # Setup cost tracking
    from app.costs.langchain_callback import CostTrackingCallbackHandler
    workflow_id = state.get("active_workflow_id")
    agent_id = state.get("active_agent_id", "planner")
    
    callbacks = [CostTrackingCallbackHandler(workflow_id=workflow_id, agent_id=agent_id)]
    
    chain = prompt | llm | JsonOutputParser()
    try:
        response = chain.invoke({"task": task, "research_data": research_data}, config={"callbacks": callbacks})
    except Exception as e:
        print(f"Planning error: {e}")
        response = None
    
    return {"plan_data": response}

