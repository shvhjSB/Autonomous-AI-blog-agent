from langchain_tavily import TavilySearch
from typing import List
import logging

from blog_agent.config import get_settings

logger = logging.getLogger(__name__)

def tavily_search(query: str, max_results: int = 5) -> List[dict]:
    """Run a Tavily web search and return normalized result dicts."""
    settings = get_settings()

    if not settings.tavily_api_key:
        logger.warning("TAVILY_API_KEY not set — skipping web search.")
        return []

    try:
        tool = TavilySearch(
            max_results=max_results,
            tavily_api_key=settings.tavily_api_key,
        )

        response = tool.invoke({"query": query})

        # Tavily may return a list of results or a dict with "results" key
        if isinstance(response, list):
            results = response
        elif isinstance(response, dict):
            results = response.get("results", [])
        else:
            results = []

        normalized = []
        for r in results:
            normalized.append(
                {
                    "url": r.get("url"),
                    "title": r.get("title"),
                    "content": r.get("content") or r.get("snippet") or "",
                }
            )

        return normalized

    except Exception as exc:
        logger.exception("Tavily search failed for query %r: %s", query, exc)
        return []