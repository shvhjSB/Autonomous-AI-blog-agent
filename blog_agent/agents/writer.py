from __future__ import annotations

import logging

from blog_agent.llm import invoke_text
from blog_agent.prompts import WRITER_PROMPT
from blog_agent.schemas import EvidenceItem, Plan, Task

logger = logging.getLogger(__name__)


def writer_node(payload: dict) -> dict:
    """Write one section of the blog based on the task payload."""

    task = Task(**payload["task"])
    plan = Plan(**payload["plan"])
    evidence = [EvidenceItem(**e) for e in payload.get("evidence", [])]

    logger.info("Writing section %d: %s", task.id, task.title)

    # Bullet formatting
    bullets_text = "\n- " + "\n- ".join(task.bullets)

    # Compact evidence format (max 8 items to reduce per-writer token cost)
    evidence_text = "\n".join(
        f"{i+1}. [{e.title}]({e.url}) — {e.snippet}"
        for i, e in enumerate(evidence[:8])
        if e.snippet
    )

    try:
        section_md = invoke_text(
            system_prompt=WRITER_PROMPT,
            user_content=(
                f"Blog title: {plan.blog_title}\n"
                f"Audience: {plan.audience}\n"
                f"Tone: {plan.tone}\n"
                f"Blog kind: {plan.blog_kind}\n"
                f"Constraints: {plan.constraints}\n"
                f"Topic: {str(payload['topic'])[:500]}\n"
                f"Mode: {payload.get('mode')}\n"
                f"As-of: {payload.get('as_of')} "
                f"(recency_days={payload.get('recency_days')})\n\n"

                f"Section title: {task.title}\n"
                f"Goal: {task.goal}\n"
                f"Target words: {task.target_words}\n"
                f"Tags: {task.tags}\n"
                f"requires_research: {task.requires_research}\n"
                f"requires_citations: {task.requires_citations}\n"
                f"requires_code: {task.requires_code}\n"

                f"Bullets:{bullets_text}\n\n"

                f"Evidence Sources (use these URLs for citations):\n"
                f"{evidence_text}\n\n"

                "Citation rules:\n"
                "- Cite sources using this format: (Source Title – URL)\n"
                "- Example: (CrowdStrike Threat Report – https://crowdstrike.com/report)\n"
                "- DO NOT write generic citations like (Source)\n"
                "- Only cite URLs provided in the evidence list\n"
            ),
        )

    except Exception as exc:
        logger.error("Writer LLM failed for section %d: %s", task.id, exc)
        section_md = (
            f"## {task.title}\n\n"
            f"> *Error: Could not generate this section due to an API failure ({exc}).*\n"
        )

    logger.info("Finished section %d (%d chars).", task.id, len(section_md))

    return {"sections": [(task.id, section_md)]}