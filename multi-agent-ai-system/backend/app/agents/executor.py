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
    
    llm = ChatGroq(model_name=settings.GROQ_MODEL, api_key=settings.GROQ_API_KEY)
    
    prompt = ChatPromptTemplate.from_template(
        "You are an executor agent providing guidance for manual execution.\n"
        "IMPORTANT: You CANNOT execute tasks automatically. You can only provide detailed guidance.\n\n"
        "Plan: {plan_data}\n\n"
        "Provide a detailed execution guide that explains:\n"
        "1. How the USER can manually perform each step\n"
        "2. What tools or resources they should use\n"
        "3. Expected outcomes and how to verify success\n"
        "4. Potential challenges and how to overcome them\n\n"
        "Be clear that these are MANUAL steps the user must perform themselves."
    )
    
    chain = prompt | llm
    try:
        response = chain.invoke({"plan_data": plan_data})
        content = response.content
    except Exception as e:
        content = f"Execution planning failed: {str(e)}"
    
    return {"execution_data": content}
