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
    
    llm = ChatGroq(model_name=settings.GROQ_MODEL, api_key=settings.GROQ_API_KEY)
    
    prompt = ChatPromptTemplate.from_template(
        "You are a planner agent for an AI system with LIMITED capabilities.\n"
        "IMPORTANT: This system can ONLY perform web research via DuckDuckGo. It CANNOT:\n"
        "- Visit websites or scrape data\n"
        "- Execute code or scripts\n"
        "- Send emails or make API calls\n"
        "- Access databases or paid services\n\n"
        "Task: {task}\n"
        "Research Data: {research_data}\n\n"
        "Based on the research findings, create a realistic action plan that:\n"
        "1. Summarizes what information WAS found through research\n"
        "2. Provides actionable next steps the USER can take manually\n"
        "3. Suggests tools or methods the user could use themselves\n\n"
        "Return a JSON object with a 'steps' key containing realistic manual steps. "
        "Each step should have 'id', 'description', 'estimated_time', 'dependencies', and 'complexity'.\n"
        "Focus on what the USER should do, not what the system will do automatically."
        "Ensure the output is valid JSON."
    )
    
    chain = prompt | llm | JsonOutputParser()
    try:
        response = chain.invoke({"task": task, "research_data": research_data})
    except Exception as e:
        response = {"error": str(e), "steps": []}
    
    return {"plan_data": response}
