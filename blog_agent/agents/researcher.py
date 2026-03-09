"""
Researcher node — runs web searches and synthesises evidence.

Executes Tavily web searches for each query from the router, then uses
the LLM to synthesise raw results into structured EvidenceItem objects.

Produces: status, evidence.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List, Optional
from urllib.parse import urlparse

from blog_agent.llm import invoke_structured
from blog_agent.prompts import RESEARCH_PROMPT
from blog_agent.schemas import BlogState, EvidenceItem, EvidencePack
from blog_agent.tools.search import tavily_search

logger = logging.getLogger(__name__)


def _iso_to_date(s: Optional[str]) -> Optional[date]:
    """Best-effort parse of ISO date string."""
    if not s:
        return None

    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def researcher_node(state: BlogState) -> dict:
    """Run Tavily searches and synthesize results into structured evidence."""

    queries = (state.get("queries") or [])[:10]

    logger.info("Researching %d queries.", len(queries))

    raw: List[dict] = []

    # -----------------------------------------------------
    # Run Tavily searches
    # -----------------------------------------------------

    for q in queries:
        try:
            results = tavily_search(q, max_results=8)

            for r in results:
                raw.append(
                    {
                        "title": r.get("title"),
                        "url": r.get("url"),
                        "content": (r.get("content") or r.get("snippet") or "")[:500],
                        "published_at": r.get("published_date"),
                        "source": r.get("source"),
                    }
                )

        except Exception as exc:
            logger.error("Tavily search failed for query %r: %s", q, exc)

    if not raw:
        logger.warning("No search results returned — continuing without evidence.")
        return {"status": "researching", "evidence": []}

    logger.info("Collected %d raw search results.", len(raw))

    # -----------------------------------------------------
    # Limit token size for LLM
    # -----------------------------------------------------

    raw_str = str(raw)[:12000]

    # -----------------------------------------------------
    # Synthesize evidence with LLM
    # -----------------------------------------------------

    try:
        pack = invoke_structured(
            system_prompt=RESEARCH_PROMPT,
            user_content=(
                f"As-of date: {state['as_of']}\n"
                f"Recency days: {state['recency_days']}\n\n"
                f"Raw results:\n{raw_str}"
            ),
            schema=EvidencePack,
        )

    except Exception as exc:
        logger.error("Research LLM parsing failed: %s", exc)
        return {"status": "researching", "evidence": []}

    # -----------------------------------------------------
    # Deduplicate by domain
    # -----------------------------------------------------

    dedup = {}

    for item in pack.evidence:
        try:
            domain = urlparse(item.url).netloc
            if domain not in dedup:
                dedup[domain] = item
        except Exception:
            continue

    evidence = list(dedup.values())

    # -----------------------------------------------------
    # Recency filter (keep items without date)
    # -----------------------------------------------------

    if state.get("mode") == "open_book":

        as_of = date.fromisoformat(state["as_of"])
        cutoff = as_of - timedelta(days=int(state["recency_days"]))

        filtered = []

        for e in evidence:

            d = _iso_to_date(e.published_at)

            # Keep if:
            # - no date available
            # - OR date is recent
            if d is None or d >= cutoff:
                filtered.append(e)

        evidence = filtered

    logger.info("Synthesised %d evidence items.", len(evidence))

    return {
        "status": "researching",
        "evidence": evidence,
    }