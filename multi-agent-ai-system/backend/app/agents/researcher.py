from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from duckduckgo_search import DDGS
import os
from app.config import settings

def research_node(state: dict):
    """
    Researcher agent:
    - Uses web search to gather information.
    - Input key: "input" (the original query).
    - Output: a concise but comprehensive summary plus a list of sources.
    """
    original_input = state.get("input")
    
    # Initialize LLM
    try:
        llm = ChatGroq(model_name=settings.GROQ_MODEL, api_key=settings.GROQ_API_KEY)
    except Exception as e:
        return {"research_data": f"Failed to initialize LLM: {str(e)}"}

    # 1. Generate Search Queries
    search_queries = [original_input]
    try:
        query_prompt = ChatPromptTemplate.from_template(
            "You are a research expert. Generate 3 distinct, effective web search queries to find comprehensive information for the following user request: {input}\n"
            "Return ONLY the 3 queries, separated by newlines. Do not include numbering or quotes."
        )
        query_chain = query_prompt | llm
        response = query_chain.invoke({"input": original_input})
        # Split by newline and clean up
        generated_queries = [q.strip().strip('"').strip() for q in response.content.split('\n') if q.strip()]
        if generated_queries:
            search_queries = generated_queries
        print(f"Generated search queries: {search_queries}")
    except Exception as e:
        print(f"Query generation error: {e}")
        # Fallback to original input
        search_queries = [original_input]

    # 2. Search using DuckDuckGo (Multiple Queries)
    all_search_results = ""
    try:
        ddgs = DDGS()
        for query in search_queries:
            all_search_results += f"\n--- Results for query: '{query}' ---\n"
            try:
                results = ddgs.text(query, max_results=5) # Reduced to 5 per query to avoid overload
                if not results:
                    all_search_results += "No results found.\n"
                    continue
                    
                for i, result in enumerate(results, 1):
                    all_search_results += f"\n{i}. {result.get('title', 'No title')}\n"
                    all_search_results += f"   {result.get('body', 'No description')}\n"
                    all_search_results += f"   URL: {result.get('href', 'No URL')}\n"
            except Exception as inner_e:
                print(f"Error searching for '{query}': {inner_e}")
                all_search_results += f"Error searching for '{query}': {str(inner_e)}\n"
        
        if not all_search_results.strip():
            all_search_results = "No search results found for any queries."
            
    except Exception as e:
        print(f"Search error: {e}")
        all_search_results = f"Search failed: {str(e)}"

    # 3. Summarize using LLM
    try:
        prompt = ChatPromptTemplate.from_template(
            "You are a researcher. Research the following topic based on the search results.\n"
            "Original Request: {original_input}\n"
            "Search Queries Used: {search_queries}\n"
            "Search Results: {results}\n\n"
            "Provide a concise but comprehensive summary plus a list of sources. "
            "If the user asked for specific data (like emails or companies), try to extract as much of that specific data as possible from the results."
        )
        
        chain = prompt | llm
        response = chain.invoke({
            "original_input": original_input, 
            "search_queries": str(search_queries),
            "results": all_search_results
        })
        content = response.content
    except Exception as e:
        print(f"LLM error: {e}")
        content = f"Research summary failed: {str(e)}"
    
    return {"research_data": content}
