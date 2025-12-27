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
    
    # Initialize Sandbox
    from app.execution.docker_runner import DockerSandbox
    sandbox = DockerSandbox() 
    
    # Helper to clean code
    def extract_code(text):
        if "```" in text:
            # Extract content between first and last ``` block
            import re
            match = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
            if match:
                return match.group(1).strip()
        return text

    chain = prompt | llm
    content = None
    
    try:
        # 1. Generate Initial Code
        response = chain.invoke({
            "input": original_input,
            "execution_data": execution_data or "No additional context",
            "language": language
        })
        content = response.content
        
        # 2. Verify Execution (Self-Correction Loop)
        # Only verify if language is Python and we have code
        if language.lower() in ["python", "python3"] and content and sandbox.client:
            print("🚀 Verifying generated code in sandbox...")
            attempts = 2
            for attempt in range(attempts):
                code_to_run = extract_code(content)
                
                result = sandbox.execute_code(language, code_to_run)
                
                if result.exit_code == 0:
                    print(f"✅ Code verification successful (Attempt {attempt+1})")
                    # Append verification note
                    content += f"\n\n<!-- Verification: Code ran successfully in {result.duration_ms:.2f}ms -->"
                    break
                else:
                    print(f"❌ Code verification failed (Attempt {attempt+1}): {result.stderr}")
                    
                    # Self-Correction Prompt
                    correction_prompt = ChatPromptTemplate.from_template(
                        "You generated code that failed to run.\n\n"
                        "Original Code:\n```python\n{code}\n```\n\n"
                        "Error Output:\n{error}\n\n"
                        "Please FIX the code to resolve the error. Return ONLY the fixed code with comments."
                    )
                    
                    fix_chain = correction_prompt | llm
                    fix_response = fix_chain.invoke({
                        "code": code_to_run,
                        "error": result.stderr
                    })
                    content = fix_response.content # Update content with fixed version
                    # Loop continues to verify the fixed code
            if attempts > 0 and result.exit_code != 0:
                 content += f"\n\n<!-- Warning: Code failed verification after {attempts} attempts. Error: {result.stderr[:200]}... -->"

    except Exception as e:
        print(f"Code generation error: {e}")
        content = None
    
    return {"code_data": content}

