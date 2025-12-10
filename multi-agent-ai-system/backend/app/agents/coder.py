from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings

def coder_node(state: dict):
    """
    Coder agent:
    - Writes production-ready code ONLY when explicitly requested.
    - Skips code generation for informational queries.
    - Input keys: "input", "execution_data", and "language".
    - Output: clean, well-documented code (or null if not requested).
    """
    original_input = state.get("input", "")
    execution_data = state.get("execution_data")
    language = state.get("language", "python")
    query_complexity = state.get("query_complexity", "SIMPLE")
    
    # Check if code was explicitly requested
    code_keywords = ["code", "script", "program", "function", "write", "create", "implement", "build"]
    code_requested = any(keyword in original_input.lower() for keyword in code_keywords)
    
    # Skip code generation for simple informational queries
    if query_complexity == "SIMPLE" and not code_requested:
        print("Skipping code generation for SIMPLE query without code request")
        return {"code_data": None}
    
    # If code wasn't explicitly requested for complex queries, also skip
    if not code_requested:
        print("Skipping code generation - not explicitly requested")
        return {"code_data": None}
    
    # Generate code when explicitly requested
    llm = ChatGroq(model_name=settings.GROQ_MODEL, api_key=settings.GROQ_API_KEY)
    
    prompt = ChatPromptTemplate.from_template(
        "You are a code generation agent.\n\n"
        "User Request: {input}\n"
        "Context: {execution_data}\n"
        "Language: {language}\n\n"
        "Generate clean, production-ready code that fulfills the user's request.\n\n"
        "Include:\n"
        "1. Complete, executable code\n"
        "2. Clear comments explaining key sections\n"
        "3. Installation instructions for required libraries\n"
        "4. Usage examples\n\n"
        "Format the code properly with syntax highlighting."
    )
    
    chain = prompt | llm
    try:
        response = chain.invoke({
            "input": original_input,
            "execution_data": execution_data or "No additional context",
            "language": language
        })
        content = response.content
    except Exception as e:
        print(f"Code generation error: {e}")
        content = None
    
    return {"code_data": content}

