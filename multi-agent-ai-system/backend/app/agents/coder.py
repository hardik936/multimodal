from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings

def coder_node(state: dict):
    """
    Coder agent:
    - Writes production-ready code from a requirement.
    - Input keys: "requirement" (execution data) and "language".
    - Output: clean, well-documented code plus the full LLM response.
    """
    requirement = state.get("execution_data")
    language = state.get("language", "python")
    
    llm = ChatGroq(model_name=settings.GROQ_MODEL, api_key=settings.GROQ_API_KEY)
    
    prompt = ChatPromptTemplate.from_template(
        "You are a coder agent providing code templates and examples.\n"
        "IMPORTANT: This code will NOT be executed automatically. Provide it as a REFERENCE/TEMPLATE for the user.\n\n"
        "Requirement: {requirement}\n"
        "Language: {language}\n\n"
        "Provide:\n"
        "1. A code template the user can adapt and run themselves\n"
        "2. Clear comments explaining what each section does\n"
        "3. Installation instructions for any required libraries\n"
        "4. Usage examples\n\n"
        "Start your response with a clear disclaimer that this code must be run manually by the user."
    )
    
    chain = prompt | llm
    try:
        response = chain.invoke({"requirement": requirement, "language": language})
        content = response.content
    except Exception as e:
        content = f"Coding failed: {str(e)}"
    
    return {"code_data": content}
