from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from duckduckgo_search import DDGS
import os
import time
from app.config import settings
from app.observability.tracing import get_tracer, trace_span, add_span_attributes
from app.observability.events import emit_workflow_event, EventType

tracer = get_tracer("agent.researcher")
import logging
logger = logging.getLogger(__name__)

async def research_node(state: dict):
    """
    Optimized Researcher agent:
    - Uses web search to gather information with minimal LLM calls.
    - Input key: "input" (the original query).
    - Output: a concise but comprehensive summary.
    - Uses simple heuristics for complexity detection instead of LLM calls.
    """
    original_input = state.get("input")
    run_id = state.get("run_id", "unknown_run")
    
    # Emit agent started event
    emit_workflow_event(
        run_id=run_id,
        event_type=EventType.WORKFLOW_AGENT_STARTED,
        agent_name="Researcher",
        progress=20,
        payload={"agent_id": "researcher"}
    )
    
    # Create agent.execute span
    with trace_span(
        tracer,
        "agent.execute",
        attributes={
            "agent.id": "researcher",
            "agent.role": "researcher",
            "agent.name": "Researcher",
        }
    ) as agent_span:
        # Initialize LLM
        try:
            logger.info(f"Initializing ChatGroq (run_id={run_id})...")
            llm = ChatGroq(model_name=settings.GROQ_MODEL, api_key=settings.GROQ_API_KEY, request_timeout=60)
            logger.info("ChatGroq initialized.")
        except Exception as e:
            return {
                "research_data": f"Failed to initialize LLM: {str(e)}",
                "query_complexity": "SIMPLE"
            }

        # 1. Simple Heuristic-Based Complexity Assessment (NO LLM CALL)
        # Check for keywords that indicate complexity
        complexity_keywords = [
            'find', 'list', 'companies', 'emails', 'current', 'latest', 
            'price', 'stock', 'news', 'compare', 'analysis', 'statistics',
            'data', 'research', 'investigate', 'multiple', 'several',
            'create', 'game', 'code', 'script', 'generate', 'write', 'implement'
        ]
        
        input_lower = original_input.lower()
        is_complex = any(keyword in input_lower for keyword in complexity_keywords)
        
        # Also check query length - longer queries tend to be more complex
        if len(original_input.split()) > 10:
            is_complex = True
        
        print(f"Query complexity (heuristic): {'COMPLEX' if is_complex else 'SIMPLE'}")
        add_span_attributes(agent_span, {"agent.query_complexity": "COMPLEX" if is_complex else "SIMPLE"})

        # 2. Single Web Search (NO QUERY GENERATION)
        # Use the original query directly instead of generating multiple queries
        all_search_results = ""
        search_successful = False
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            ddgs = DDGS()
            # Single search with more results (5 instead of 3x3=9)
            logger.info(f"Starting DuckDuckGo search for: {original_input}...")
            # Use run_in_executor for the blocking search call
            results = await loop.run_in_executor(None, lambda: ddgs.text(original_input, max_results=5))
            logger.info(f"DuckDuckGo search completed. Results found: {bool(results)}")
            
            if results:
                search_successful = True
                for i, result in enumerate(results, 1):
                    all_search_results += f"\n{i}. {result.get('title', 'No title')}\n"
                    all_search_results += f"   {result.get('body', 'No description')}\n"
                    all_search_results += f"   URL: {result.get('href', 'No URL')}\n"
            else:
                all_search_results = "No search results found."
                
        except Exception as e:
            logger.error(f"Search error for {run_id}: {e}")
            all_search_results = f"Search failed: {str(e)}"

        # 3. Single LLM Call for Synthesis (NO RELEVANCE CHECK)
        # Trust the search results and synthesize directly
        try:
            if not search_successful or not all_search_results.strip():
                # Fallback to internal knowledge
                print("Falling back to internal knowledge")
                fallback_prompt = ChatPromptTemplate.from_template(
                    "You are 'Anti-Gravity', a production-grade autonomous researcher.\n\n"
                    "User Query: {query}\n\n"
                    "IMPORTANT: Web search failed or returned no results.\n"
                    "Use your internal knowledge to provide the best possible answer.\n\n"
                    "Rules:\n"
                    "- Provide a direct, helpful answer based on your training data\n"
                    "- If you don't have current/specific data, acknowledge this briefly but still provide useful general information\n"
                    "- Format appropriately (markdown, bullets, numbered lists, etc.)\n"
                    "- NEVER say 'I cannot help' or leave the answer empty\n"
                    "- For recipes/how-tos: provide complete instructions\n"
                    "- For definitions: provide clear explanations\n"
                    "- For comparisons: use tables or structured lists\n\n"
                    "Provide your complete answer now:"
                )
                chain = fallback_prompt | llm
                
                # Create llm.call span for fallback
                llm_start = time.time()
                with trace_span(
                    tracer,
                    "llm.call",
                    attributes={
                        "llm.provider": "groq",
                        "llm.model": settings.GROQ_MODEL,
                        "llm.purpose": "fallback_synthesis",
                    }
                ) as llm_span:
                    logger.info("Invoking LLM for fallback synthesis...")
                    response = chain.invoke({"query": original_input})
                    logger.info("LLM fallback synthesis completed.")
                    llm_latency = (time.time() - llm_start) * 1000
                    add_span_attributes(llm_span, {"llm.latency_ms": llm_latency})
                    content = response.content
            
            else:
                # Use search results - single prompt for both simple and complex
                if is_complex:
                    # Complex queries: Show research process
                    prompt = ChatPromptTemplate.from_template(
                        "You are 'Anti-Gravity', a production-grade autonomous researcher.\n\n"
                        "Original Request: {original_input}\n"
                        "Search Results: {results}\n\n"
                        "This is a COMPLEX query requiring detailed research.\n\n"
                        "Provide your response in this format:\n"
                        "## Research Summary\n"
                        "[Concise overview of findings]\n\n"
                        "## Key Findings\n"
                        "[Detailed information organized by topic]\n\n"
                        "## Sources\n"
                        "[List of sources used]\n\n"
                        "CRITICAL: Filter out any irrelevant information. Only include findings that directly address the user's request.\n"
                        "If the user asked for specific data extraction, prioritize that in Key Findings."
                    )
                else:
                    # Simple queries: Direct answer without visible research sections
                    prompt = ChatPromptTemplate.from_template(
                        "You are 'Anti-Gravity', a production-grade autonomous researcher.\n\n"
                        "Original Request: {original_input}\n"
                        "Search Results: {results}\n\n"
                        "This is a SIMPLE informational query.\n\n"
                        "CRITICAL: Provide a direct, clear answer WITHOUT any research metadata.\n"
                        "- Do NOT include sections like 'Research Summary' or 'Sources'\n"
                        "- Do NOT mention search queries or research process\n"
                        "- Just provide the answer in the most natural, helpful format\n"
                        "- Use appropriate formatting (bullets, numbered lists, etc.) based on the question type\n"
                        "- Filter out any irrelevant information from search results\n\n"
                        "Examples:\n"
                        "- Recipe request → Ingredients + Steps\n"
                        "- Definition → Clear explanation\n"
                        "- How-to → Step-by-step instructions\n"
                        "- Comparison → Table or bullet comparison"
                    )
                
                chain = prompt | llm
                
                # Create llm.call span for synthesis
                llm_start = time.time()
                with trace_span(
                    tracer,
                    "llm.call",
                    attributes={
                        "llm.provider": "groq",
                        "llm.model": settings.GROQ_MODEL,
                        "llm.purpose": "research_synthesis",
                    }
                ) as llm_span:
                    logger.info("Invoking LLM for research synthesis...")
                    response = chain.invoke({
                        "original_input": original_input,
                        "results": all_search_results
                    })
                    logger.info("LLM research synthesis completed.")
                    llm_latency = (time.time() - llm_start) * 1000
                    add_span_attributes(llm_span, {"llm.latency_ms": llm_latency})
                    content = response.content
                
        except Exception as e:
            print(f"LLM error: {e}")
            content = f"I apologize, but I encountered an error processing your request. Please try again."
        
        # Emit agent completed event
        emit_workflow_event(
            run_id=run_id,
            event_type=EventType.WORKFLOW_AGENT_COMPLETED,
            agent_name="Researcher",
            progress=20,
            payload={"agent_id": "researcher", "success": True}
        )
        
        return {
            "research_data": content,
            "query_complexity": "COMPLEX" if is_complex else "SIMPLE"
        }

