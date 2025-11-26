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
    
    llm = ChatGroq(model_name="llama3-70b-8192", api_key=settings.GROQ_API_KEY)
    
    prompt = ChatPromptTemplate.from_template(
        "You are a coder agent. Write production-ready code based on the following requirement.\n"
        "Requirement: {requirement}\n"
        "Language: {language}\n\n"
        "Output clean, well-documented code."
    )
    
    chain = prompt | llm
    try:
        response = chain.invoke({"requirement": requirement, "language": language})
        content = response.content
    except Exception as e:
        content = f"Coding failed: {str(e)}"
    
    return {"code_data": content}
