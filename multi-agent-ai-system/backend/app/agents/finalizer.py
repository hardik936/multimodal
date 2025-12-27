from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
import time
from app.config import settings
from app.observability.tracing import get_tracer, trace_span, add_span_attributes

tracer = get_tracer("agent.finalizer")

def finalizer_node(state: dict):
    """
    Finalizer agent:
    - Ensures final_output is ALWAYS populated (never null/empty).
    - Synthesizes clean, user-facing answer from all agent outputs.
    - Applies final quality checks and fallback logic.
    """
    query_complexity = state.get("query_complexity", "SIMPLE")
    original_input = state.get("input", "")
    research = state.get("research_data", "")
    plan = state.get("plan_data")
    execution = state.get("execution_data")
    code = state.get("code_data")
    
    # Initialize LLM for fallback synthesis
    import logging
    logger = logging.getLogger(__name__)
    try:
        logger.info("Initializing Finalizer LLM...")
        llm = ChatGroq(model_name=settings.GROQ_MODEL, api_key=settings.GROQ_API_KEY, request_timeout=60)
        logger.info("Finalizer LLM initialized.")
    except Exception as e:
        print(f"Finalizer LLM initialization failed: {e}")
        llm = None
    
    final_output = ""
    
    # Strategy 1: For SIMPLE queries, use research output directly (NO LLM SYNTHESIS)
    if query_complexity == "SIMPLE":
        if research and research.strip():
            # Use research data directly without additional synthesis
            final_output = research
            print("Using research data directly for SIMPLE query (no synthesis)")
        else:
            # Fallback: Generate answer from internal knowledge
            final_output = generate_fallback_answer(original_input, llm)
    
    # Strategy 2: For COMPLEX queries, synthesize from all available data
    else:
        # Try to synthesize from available outputs
        if research or plan or execution or code:
            final_output = synthesize_complex_output(
                original_input, research, plan, execution, code, llm
            )
        else:
            # Fallback: Generate answer from internal knowledge
            final_output = generate_fallback_answer(original_input, llm)
    
    # Final validation: Ensure we have SOMETHING
    if not final_output or final_output.strip() == "":
        final_output = f"I apologize, but I encountered an issue processing your request: '{original_input}'. Please try rephrasing your question or provide more details."
    
    return {"final_output": final_output}


def synthesize_complex_output(original_input: str, research: str, plan: any, execution: str, code: str, llm) -> str:
    """
    Synthesizes final_output from multiple agent outputs for complex queries.
    """
    if not llm:
        # Without LLM, just concatenate available outputs
        parts = []
        if research:
            parts.append(research)
        if code:
            parts.append(f"\n\n## Code\n\n```\n{code}\n```")
        return "\n\n".join(parts) if parts else ""
    
    try:
        # Build context from all available outputs
        context_parts = []
        if research:
            context_parts.append(f"Research Findings:\n{research}")
        if plan:
            context_parts.append(f"Plan:\n{str(plan)}")
        if execution:
            context_parts.append(f"Execution Notes:\n{execution}")
        if code:
            context_parts.append(f"Generated Code:\n{code}")
        
        context = "\n\n".join(context_parts)
        
        prompt = ChatPromptTemplate.from_template(
            "You are 'Anti-Gravity', a production-grade autonomous agent.\n\n"
            "User Request: {input}\n\n"
            "Available Information:\n{context}\n\n"
            "CRITICAL: Synthesize a complete, standalone answer for the user.\n"
            "- Combine all relevant information into a clear, cohesive response\n"
            "- If code was generated, include it with usage instructions\n"
            "- If research was done, incorporate key findings\n"
            "- Format appropriately (use markdown, bullets, code blocks, etc.)\n"
            "- The user should NOT need to read the research/plan/execution fields\n"
            "- This final_output should be fully self-contained\n\n"
            "Provide the complete answer now:"
        )
        
        chain = prompt | llm
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Invoking Finalizer LLM for complex synthesis...")
        response = chain.invoke({"input": original_input, "context": context})
        logger.info("Finalizer LLM complex synthesis completed.")
        return response.content
        
    except Exception as e:
        print(f"Synthesis error: {e}")
        # Fallback to research if available
        return research if research else ""


def generate_fallback_answer(original_input: str, llm) -> str:
    """
    Generates an answer using the LLM's internal knowledge when search/research fails.
    """
    if not llm:
        return f"I apologize, but I couldn't process your request: '{original_input}'"
    
    try:
        prompt = ChatPromptTemplate.from_template(
            "You are 'Anti-Gravity', a production-grade autonomous agent.\n\n"
            "The user asked: {input}\n\n"
            "CRITICAL: Web search failed or returned no useful results.\n"
            "Use your internal knowledge to provide the best possible answer.\n\n"
            "Rules:\n"
            "- Provide a direct, helpful answer based on your training data\n"
            "- If you don't have current/specific data, acknowledge this briefly\n"
            "- Still provide useful general information\n"
            "- Format appropriately (markdown, bullets, etc.)\n"
            "- NEVER say 'I cannot help' or leave the answer empty\n\n"
            "Provide your answer now:"
        )
        
        chain = prompt | llm
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Invoking Finalizer LLM for fallback...")
        response = chain.invoke({"input": original_input})
        logger.info("Finalizer LLM fallback completed.")
        return response.content
        
    except Exception as e:
        print(f"Fallback generation error: {e}")
        return f"I encountered an error while processing your request: '{original_input}'. Please try again."
