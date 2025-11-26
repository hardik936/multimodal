from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings

def executor_node(state: dict):
    """
    Executor agent:
    - Expands a given instruction into an execution report.
    - Input key: "instruction" (derived from plan).
    - Output: step-by-step execution details, expected outcomes, potential issues and mitigations, and verification steps.
    """
    plan_data = state.get("plan_data")
    
    llm = ChatGroq(model_name="llama3-70b-8192", api_key=settings.GROQ_API_KEY)
    
    prompt = ChatPromptTemplate.from_template(
        "You are an executor agent. Expand the following plan into a detailed execution report.\n"
        "Plan: {plan_data}\n\n"
        "Provide step-by-step execution details, expected outcomes, potential issues and mitigations, and verification steps."
    )
    
    chain = prompt | llm
    try:
        response = chain.invoke({"plan_data": plan_data})
        content = response.content
    except Exception as e:
        content = f"Execution planning failed: {str(e)}"
    
    return {"execution_data": content}
