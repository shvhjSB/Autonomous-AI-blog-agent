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

from blog_agent.config import get_settings
from blog_agent.llm import invoke_structured
from blog_agent.prompts import PLANNER_PROMPT
from blog_agent.schemas import BlogState, Plan, Task

logger = logging.getLogger(__name__)

_MIN_BULLETS = 3
_MAX_BULLETS = 6
_MIN_WORDS = 120
_MAX_WORDS = 550


def _normalize_plan(plan: Plan) -> Plan:
    """Clamp planner output into the ranges the prompt asks for.

    These bounds used to live on the Pydantic model, but Gemini's schema
    converter drops minItems/maxItems, so the model never sees them. Enforcing
    here keeps a slightly-off plan usable instead of discarding it.
    """

    # Section count is fixed. Trimming an over-long plan is safe; a short one
    # is left alone, since inventing filler sections would hurt the post more
    # than running one section light.
    wanted = get_settings().sections_per_post
    if len(plan.tasks) > wanted:
        logger.info("Planner returned %d sections; trimming to %d.",
                    len(plan.tasks), wanted)
        plan.tasks = plan.tasks[:wanted]
    elif len(plan.tasks) < wanted:
        logger.warning("Planner returned only %d sections (wanted %d).",
                       len(plan.tasks), wanted)

    # Renumber so ids stay contiguous after any trim — merge_sections sorts on
    # them and the writers echo them back.
    for idx, task in enumerate(plan.tasks, start=1):
        task.id = idx

    for task in plan.tasks:
        if len(task.bullets) > _MAX_BULLETS:
            task.bullets = task.bullets[:_MAX_BULLETS]

        # A section with no bullets would render as an empty "- " list.
        if not task.bullets:
            task.bullets = [task.goal or task.title]

        if len(task.bullets) < _MIN_BULLETS:
            logger.debug(
                "Section %d has %d bullet(s); prompt asked for %d-%d.",
                task.id, len(task.bullets), _MIN_BULLETS, _MAX_BULLETS,
            )

        task.target_words = max(_MIN_WORDS, min(_MAX_WORDS, task.target_words))

    return plan


def _fallback_plan(topic: str) -> Plan:
    """A full-length outline for when the planner call cannot be made.

    The planner is the single point whose failure ruins the whole article: it
    decides every section the writers then produce. The old fallback emitted a
    single "Introduction and Overview" task, so one flaky network call turned a
    2,900-word post into a 300-word stub that still got exported and could be
    published. This degrades to a generic-but-complete article instead.
    """
    topic = topic.strip()[:120]
    wanted = get_settings().sections_per_post

    skeleton = [
        ("What {t} Is and Why It Matters",
         "Define the subject and explain why it is worth understanding.",
         ["Plain definition", "The problem it solves", "Who should care"]),
        ("Core Concepts Behind {t}",
         "Establish the vocabulary and mental model the rest relies on.",
         ["Key terms", "How the pieces relate", "Common misconceptions"]),
        ("How {t} Works in Practice",
         "Walk through the mechanics end to end.",
         ["Step-by-step flow", "What happens under load", "A worked example"]),
        ("Design Trade-offs and Alternatives",
         "Compare the main approaches and when each wins.",
         ["Main options", "Strengths and costs", "Selection criteria"]),
        ("Implementation Patterns",
         "Show concretely how this is applied.",
         ["Typical architecture", "Code or config example", "Integration points"]),
        ("Common Pitfalls and How to Avoid Them",
         "Cover the failure modes practitioners actually hit.",
         ["Frequent mistakes", "Warning signs", "Mitigations"]),
        ("Operating It: Monitoring and Scaling",
         "Explain what running this in production requires.",
         ["What to measure", "Scaling behaviour", "Operational guardrails"]),
        ("When Not to Use {t}",
         "Give the honest limits and simpler alternatives.",
         ["Poor-fit scenarios", "Simpler options", "Migration signals"]),
    ]

    tasks = [
        Task(
            id=i,
            title=title.format(t=topic),
            goal=goal,
            bullets=bullets,
            target_words=380,
        )
        for i, (title, goal, bullets) in enumerate(skeleton[:wanted], start=1)
    ]

    return Plan(
        blog_title=f"{topic}: A Practical Guide",
        audience="Software engineers",
        tone="Clear and technical",
        blog_kind="explainer",
        tasks=tasks,
    )


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
        plan = _fallback_plan(str(state["topic"]))

    plan = _normalize_plan(plan)

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
