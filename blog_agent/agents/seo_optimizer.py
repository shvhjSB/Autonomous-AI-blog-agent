"""
SEO Optimizer node — generates SEO metadata from the final blog.

Runs AFTER the compiler stage. Analyzes the completed blog markdown
and produces structured SEO metadata for publishing and social sharing.
"""

from __future__ import annotations

import logging

from blog_agent.llm import invoke_structured
from blog_agent.prompts import SEO_OPTIMIZER_PROMPT
from blog_agent.schemas import BlogState, SEOMetadata

logger = logging.getLogger(__name__)


def seo_optimizer_node(state: BlogState) -> dict:
    """Generate SEO metadata from the final blog markdown."""

    final_md = state.get("final", "")

    if not final_md:
        logger.warning("No final markdown found — skipping SEO optimization.")
        return {"seo_metadata": None}

    logger.info("Generating SEO metadata for blog (%d chars).", len(final_md))

    # Send a preview to save tokens (SEO only needs structure + key content)
    preview = final_md[:4000]

    try:
        seo = invoke_structured(
            system_prompt=SEO_OPTIMIZER_PROMPT,
            user_content=f"Analyze this blog post and generate SEO metadata:\n\n{preview}",
            schema=SEOMetadata,
        )
    except Exception as exc:
        logger.error("SEO optimizer LLM failed: %s", exc)
        return {"seo_metadata": None}

    logger.info("SEO metadata generated: slug=%s, keywords=%d", seo.slug, len(seo.keywords))

    return {"seo_metadata": seo}
