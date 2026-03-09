"""
Planner node — creates a structured blog outline (Plan).

Uses the LLM to produce a ``Plan`` with 5–9 sections, then provides a
fan-out function that dispatches one ``Send`` per task for parallel
section writing.

Produces: status, plan.
"""

from __future__ import annotations

import logging

from langgraph.types import Send

from blog_agent.llm import invoke_structured
from blog_agent.prompts import PLANNER_PROMPT
from blog_agent.schemas import BlogState, Plan

logger = logging.getLogger(__name__)


def planner_node(state: BlogState) -> dict:
    """Generate a structured blog plan from the topic and evidence.

    Returns a partial state update with the ``Plan`` and status.
    """
    mode = state.get("mode", "closed_book")
    evidence = state.get("evidence", [])

    logger.info("Planning blog for topic=%r, mode=%s, evidence=%d items.",
                state["topic"], mode, len(evidence))

    # Token optimization: extract only minimal evidence fields for the planner
    trimmed_evidence = [
        {"url": e.url, "snippet": e.snippet} 
        for e in evidence if e.snippet
    ][:10]

    try:
        plan = invoke_structured(
            system_prompt=PLANNER_PROMPT,
            user_content=(
                f"Topic: {str(state['topic'])[:500]}\n"
                f"Mode: {mode}\n"
                f"As-of: {state['as_of']} (recency_days={state['recency_days']})\n"
                f"{'Force blog_kind=news_roundup' if mode == 'open_book' else ''}\n\n"
                f"Evidence (Top 10):\n{trimmed_evidence}"
            ),
            schema=Plan,
        )
    except Exception as exc:
        logger.error("Planner LLM failed: %s. Generating fallback plan.", exc)
        from blog_agent.schemas import Task
        plan = Plan(
            blog_title=f"Overview of {str(state['topic'])[:50]}",
            audience="General",
            tone="Informative",
            blog_kind="explainer",
            tasks=[
                Task(
                    id=1,
                    title="Introduction and Overview",
                    goal="Provide a high-level summary.",
                    bullets=["Definition", "Key Concepts", "Conclusion"],
                    target_words=300
                )
            ]
        )

    # Enforce blog_kind for news-style topics
    if mode == "open_book":
        plan.blog_kind = "news_roundup"

    logger.info("Plan created: %r with %d sections.", plan.blog_title, len(plan.tasks))
    return {"status": "planning", "plan": plan}


def fanout_to_writers(state: BlogState):
    """Return a list of ``Send`` objects — one per planned task.

    LangGraph will execute each ``writer`` node in parallel.
    """
    plan = state["plan"]
    assert plan is not None, "fanout_to_writers called before plan was created."

    return [
        Send(
            "writer",
            {
                "task": task.model_dump(),
                "topic": state["topic"],
                "mode": state["mode"],
                "as_of": state["as_of"],
                "recency_days": state["recency_days"],
                "plan": plan.model_dump(),
                "evidence": [e.model_dump() for e in state.get("evidence", [])],
            },
        )
        for task in plan.tasks
    ]
