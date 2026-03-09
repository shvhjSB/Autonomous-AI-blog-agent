"""
Router node — classifies the topic and decides if web research is needed.

Reads the user's topic and as-of date, then uses the LLM to produce a
``RouterDecision`` that determines the research mode and search queries.

Produces: status, mode, needs_research, queries, recency_days.
"""

from __future__ import annotations

import logging

from blog_agent.llm import invoke_structured
from blog_agent.prompts import ROUTER_PROMPT
from blog_agent.schemas import BlogState, RouterDecision

logger = logging.getLogger(__name__)

# Maps research mode → recency window (days)
_RECENCY_MAP: dict[str, int] = {
    "open_book": 7,
    "hybrid": 45,
    "closed_book": 3650,
}


def router_node(state: BlogState) -> dict:
    """Classify the topic and decide if research is required.

    Returns a partial state update with the router's decision fields.
    """
    # Truncate topic to prevent massive token usage on weird inputs
    safe_topic = str(state["topic"])[:500]
    logger.info("Routing topic: %s", safe_topic)

    try:
        decision = invoke_structured(
            system_prompt=ROUTER_PROMPT,
            user_content=f"Topic: {safe_topic}\nAs-of date: {state['as_of']}",
            schema=RouterDecision,
        )
    except Exception as exc:
        logger.error("Router LLM failed: %s. Falling back to closed_book.", exc)
        decision = RouterDecision(
            needs_research=False, mode="closed_book", reason="Fallback after error", queries=[]
        )

    recency_days = _RECENCY_MAP.get(decision.mode, 3650)

    logger.info(
        "Router decision: mode=%s, needs_research=%s, queries=%d",
        decision.mode,
        decision.needs_research,
        len(decision.queries),
    )

    return {
        "status": "routing",
        "needs_research": decision.needs_research,
        "mode": decision.mode,
        "queries": decision.queries[:6],  # Hard cap queries
        "recency_days": recency_days,
    }


def route_after_router(state: BlogState) -> str:
    """Conditional edge: go to 'researcher' or skip to 'planner'."""
    return "researcher" if state["needs_research"] else "planner"
