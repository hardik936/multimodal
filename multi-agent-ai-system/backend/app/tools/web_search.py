"""
Web search tool using DuckDuckGo.
Provides text search and news search functionality.
"""
import logging
from typing import List, Dict
from duckduckgo_search import DDGS

# Configure logging
logger = logging.getLogger(__name__)


def search_web(
    query: str,
    max_results: int = 5,
    region: str = "wt-wt",
    safesearch: str = "moderate"
) -> List[Dict[str, str]]:
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)
        region: Region code for search (default: "wt-wt" for worldwide)
        safesearch: Safe search setting - "on", "moderate", or "off" (default: "moderate")
    
    Returns:
        List of dicts with keys: "title", "url", "snippet"
    """
    try:
        logger.info(f"Searching web for: {query} (max_results={max_results}, region={region})")
        
        with DDGS() as ddgs:
            results = list(ddgs.text(
                keywords=query,
                region=region,
                safesearch=safesearch,
                max_results=max_results
            ))
        
        # Transform results to match expected format
        formatted_results = [
            {
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "snippet": result.get("body", "")
            }
            for result in results
        ]
        
        logger.info(f"Found {len(formatted_results)} web search results")
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error during web search: {str(e)}")
        return []


def search_news(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search news using DuckDuckGo.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        List of dicts with keys: "title", "url", "snippet", "date", "source"
    """
    try:
        logger.info(f"Searching news for: {query} (max_results={max_results})")
        
        with DDGS() as ddgs:
            results = list(ddgs.news(
                keywords=query,
                max_results=max_results
            ))
        
        # Transform results to match expected format
        formatted_results = [
            {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("body", ""),
                "date": result.get("date", ""),
                "source": result.get("source", "")
            }
            for result in results
        ]
        
        logger.info(f"Found {len(formatted_results)} news results")
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error during news search: {str(e)}")
        return []
