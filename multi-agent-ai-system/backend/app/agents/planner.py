from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings

def planner_node(state: dict):
    """
    Planner agent:
    - Breaks the task into clear, actionable steps.
    - Input key: "input" (task) and "research_data".
    - Output: a JSON plan containing steps, estimated times, dependencies, and complexity.
    """
    task = state.get("input")
    research_data = state.get("research_data")
    
    llm = ChatGroq(model_name="llama3-70b-8192", api_key=settings.GROQ_API_KEY)
    
    prompt = ChatPromptTemplate.from_template(
        "You are a planner agent. Break down the following task into clear, actionable steps.\n"
        "Task: {task}\n"
        "Research Data: {research_data}\n\n"
        "Return a JSON object with a 'steps' key, which is a list of steps. "
        "Each step should have 'id', 'description', 'estimated_time', 'dependencies', and 'complexity'."
        "Ensure the output is valid JSON."
    )
    
    chain = prompt | llm | JsonOutputParser()
    try:
        response = chain.invoke({"task": task, "research_data": research_data})
    except Exception as e:
        response = {"error": str(e), "steps": []}
    
    return {"plan_data": response}
