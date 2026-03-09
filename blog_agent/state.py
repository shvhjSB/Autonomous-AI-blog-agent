"""
Initial state factory for the blog-writing pipeline.

Centralises the construction of a valid ``BlogState`` so that both the
CLI (``main.py``) and the Streamlit UI (``app.py``) share a single
source of truth for default values.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from blog_agent.schemas import BlogState


def make_initial_state(
    topic: str,
    as_of: Optional[str] = None,
) -> BlogState:
    """Construct a valid initial ``BlogState`` with sensible defaults.

    Args:
        topic: The blog topic to write about.
        as_of: ISO date string for recency control.
               Defaults to today's date.

    Returns:
        A fully-initialised ``BlogState`` dict ready for ``app.invoke()``.
    """
    return BlogState(
        topic=topic,
        status="",
        as_of=as_of or date.today().isoformat(),
        recency_days=3650,
        needs_research=False,
        mode="",
        queries=[],
        evidence=[],
        plan=None,
        sections=[],
        merged_md="",
        md_with_placeholders="",
        image_specs=[],
        final="",
        seo_metadata=None,
    )
