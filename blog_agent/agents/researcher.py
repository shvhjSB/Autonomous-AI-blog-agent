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
from blog_agent.schemas import BlogState, EvidencePack
from blog_agent.tools.search import tavily_search

logger = logging.getLogger(__name__)

# Below this many sources an open_book post cannot say anything concrete, so
# the recency filter tops up rather than returning an empty set.
_MIN_EVIDENCE = 3


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

    # Tavily only dates results on the "news" topic, but that topic also
    # returns far fewer hits — searching it alone starves open_book posts. So
    # for open_book we query both and merge: "news" supplies fresh dated items,
    # "general" supplies coverage.
    topics = ["news", "general"] if state.get("mode") == "open_book" else ["general"]

    seen_urls: set[str] = set()

    for q in queries:
        for topic in topics:
            try:
                results = tavily_search(q, max_results=8, topic=topic)
            except Exception as exc:
                logger.error("Tavily search failed for query %r: %s", q, exc)
                continue

            for r in results:
                url = r.get("url") or ""
                # The two topics overlap; keep the first sighting of each URL.
                if url and url in seen_urls:
                    continue
                seen_urls.add(url)

                raw.append(
                    {
                        "title": r.get("title"),
                        "url": url,
                        "content": (r.get("content") or r.get("snippet") or "")[:500],
                        "published_at": r.get("published_date"),
                        "source": r.get("source"),
                    }
                )

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
            # Extraction, not composition — light model is plenty.
            tier="light",
        )

    except Exception as exc:
        logger.error("Research LLM parsing failed: %s", exc)
        return {"status": "researching", "evidence": []}

    # -----------------------------------------------------
    # Backfill dates/sources the LLM dropped
    # -----------------------------------------------------
    # The synthesiser frequently omits published_at even when the raw result
    # carried one. Recover it from the raw results so the recency filter below
    # operates on real data rather than an all-null column.

    by_url = {r["url"]: r for r in raw if r.get("url")}

    for item in pack.evidence:
        source_row = by_url.get(item.url)
        if not source_row:
            continue
        if not item.published_at and source_row.get("published_at"):
            item.published_at = str(source_row["published_at"])[:10]
        if not item.source and source_row.get("source"):
            item.source = source_row["source"]

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

    if state.get("mode") == "open_book" and evidence:

        as_of = date.fromisoformat(state["as_of"])
        cutoff = as_of - timedelta(days=int(state["recency_days"]))

        fresh, stale = [], []

        for e in evidence:
            d = _iso_to_date(e.published_at)
            # Undated items are treated as fresh — a missing date is not
            # evidence of age, and most of the web omits one.
            (fresh if (d is None or d >= cutoff) else stale).append(e)

        if len(fresh) >= _MIN_EVIDENCE or not stale:
            evidence = fresh
        else:
            # Hard-filtering to a 7-day window routinely leaves nothing, and an
            # open_book post with no evidence degenerates into page after page
            # of "Not found in provided sources". Prefer fresh, then top up
            # with the most recent stale items rather than starving the writers.
            stale.sort(key=lambda e: _iso_to_date(e.published_at) or date.min,
                       reverse=True)
            topped_up = fresh + stale[: _MIN_EVIDENCE - len(fresh)]
            logger.warning(
                "Only %d item(s) inside the %d-day window; topping up to %d "
                "with the most recent older sources.",
                len(fresh), int(state["recency_days"]), len(topped_up),
            )
            evidence = topped_up

    logger.info("Synthesised %d evidence items.", len(evidence))

    return {
        "status": "researching",
        "evidence": evidence,
    }