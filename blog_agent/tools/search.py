from langchain_tavily import TavilySearch
from typing import List
from urllib.parse import urlparse
import logging

from blog_agent.config import get_settings

logger = logging.getLogger(__name__)


def _domain(url: str) -> str:
    """Best-effort extraction of the bare domain from a URL."""
    try:
        netloc = urlparse(url or "").netloc
    except Exception:
        return ""
    return netloc[4:] if netloc.startswith("www.") else netloc


def tavily_search(
    query: str,
    max_results: int = 5,
    topic: str = "general",
) -> List[dict]:
    """Run a Tavily web search and return normalized result dicts.

    Args:
        query: The search query.
        max_results: Maximum results to request.
        topic: ``"general"`` or ``"news"``. Tavily only populates
            ``published_date`` for the ``"news"`` topic, so recency-sensitive
            callers should pass ``"news"``.
    """
    settings = get_settings()

    if not settings.tavily_api_key:
        logger.warning("TAVILY_API_KEY not set — skipping web search.")
        return []

    try:
        try:
            tool = TavilySearch(
                max_results=max_results,
                topic=topic,
                tavily_api_key=settings.tavily_api_key,
            )
        except TypeError:
            # Older langchain-tavily builds may not accept `topic`.
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
            url = r.get("url") or ""
            normalized.append(
                {
                    "url": url,
                    "title": r.get("title"),
                    "content": r.get("content") or r.get("snippet") or "",
                    # Tavily exposes the publication date as "published_date";
                    # keep it so the researcher's recency filter has something
                    # to work with.
                    "published_date": r.get("published_date")
                    or r.get("published_at"),
                    "source": r.get("source") or _domain(url),
                }
            )

        return normalized

    except Exception as exc:
        logger.exception("Tavily search failed for query %r: %s", query, exc)
        return []