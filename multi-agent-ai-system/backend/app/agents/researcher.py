from langchain_community.tools import DuckDuckGoSearchRun
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
import os
from app.config import settings

def research_node(state: dict):
    """
    Researcher agent:
    - Uses web search to gather information.
    - Input key: "input" (the original query).
    - Output: a concise but comprehensive summary plus a list of sources.
    """
    query = state.get("input")
    
    # 1. Search
    try:
        from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
        wrapper = DuckDuckGoSearchAPIWrapper()
        search_results = wrapper.run(query)
    except Exception as e:
        print(f"Search error: {e}")
        search_results = f"Search failed: {str(e)}"

    # 2. Summarize
    try:
        llm = ChatGroq(model_name="llama3-70b-8192", api_key=settings.GROQ_API_KEY)
        
        prompt = ChatPromptTemplate.from_template(
            "You are a researcher. Research the following topic based on the search results.\n"
            "Topic: {query}\n"
            "Search Results: {results}\n\n"
            "Provide a concise but comprehensive summary plus a list of sources."
        )
        
        chain = prompt | llm
        response = chain.invoke({"query": query, "results": search_results})
        content = response.content
    except Exception as e:
        print(f"LLM error: {e}")
        content = f"Research summary failed: {str(e)}"
    
    return {"research_data": content}
