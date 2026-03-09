"""
Compiler node — post-writing pipeline (reducer subgraph).

Three sub-steps run in sequence after all writer nodes finish:

  1. ``merge_sections``   — sort and join ordered section markdown
  2. ``plan_images``      — LLM plans per-section diagrams
  3. ``generate_and_export`` — create images, replace placeholders, export ``.md``
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

from blog_agent.config import get_settings
from blog_agent.llm import invoke_structured
from blog_agent.prompts import IMAGE_PLANNER_PROMPT
from blog_agent.schemas import BlogState, GlobalImagePlan, ImageSpec
from blog_agent.tools.images import generate_image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_slug(title: str) -> str:
    """Convert a title into a filesystem-safe slug."""
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9 _-]+", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s or "blog"


# ---------------------------------------------------------------------------
# Sub-nodes
# ---------------------------------------------------------------------------

def merge_sections(state: BlogState) -> dict:
    """Sort and join all parallel-written sections into a single markdown doc."""
    plan = state["plan"]
    if plan is None:
        raise ValueError("merge_sections called without a plan in state.")

    ordered = [md for _, md in sorted(state["sections"], key=lambda x: x[0])]
    body = "\n\n".join(ordered).strip()
    merged_md = f"# {plan.blog_title}\n\n{body}\n"

    logger.info("Merged %d sections into blog markdown.", len(ordered))
    return {"status": "compiling", "merged_md": merged_md}


def plan_images(state: BlogState) -> dict:
    """Ask the LLM to plan per-section images using the full merged markdown.

    Returns ``md_with_placeholders`` and ``image_specs``.
    """
    plan = state["plan"]
    assert plan is not None
    merged_md = state["merged_md"]

    try:
        image_plan = invoke_structured(
            system_prompt=IMAGE_PLANNER_PROMPT,
            user_content=(
                f"Blog kind: {plan.blog_kind}\n"
                f"Topic: {str(state['topic'])[:500]}\n"
                f"Number of sections: {len(plan.tasks)}\n\n"
                f"Full blog markdown:\n\n{merged_md}"
            ),
            schema=GlobalImagePlan,
        )
    except Exception as exc:
        logger.error("Image planner LLM failed: %s. Falling back to no images.", exc)
        image_plan = GlobalImagePlan(md_with_placeholders=merged_md, images=[])

    # Cap at 5 images max
    image_plan.images = image_plan.images[:5]

    logger.info("Image plan: %d images proposed.", len(image_plan.images))

    # Validate: if the LLM returned a truncated/mangled markdown, fall back
    result_md = image_plan.md_with_placeholders
    if len(result_md) < len(merged_md) / 2:
        logger.warning("Image planner returned truncated markdown, using original.")
        result_md = merged_md

    return {
        "status": "compiling",
        "md_with_placeholders": result_md,
        "image_specs": image_plan.images,
    }


def generate_and_export(state: BlogState) -> dict:
    """Generate images, replace [IMAGE: slug] placeholders, and export .md."""
    settings = get_settings()
    plan = state["plan"]
    assert plan is not None

    md = state.get("md_with_placeholders") or state["merged_md"]
    image_specs: List[ImageSpec] = state.get("image_specs", []) or []

    # Prepare output directory
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if image_specs:
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)

        for spec in image_specs:
            # Normalize filename — ensure it always ends with .png
            fname = spec.filename
            if not fname.lower().endswith(".png"):
                fname = fname + ".png"

            # Extract slug for robust matching: strip [IMAGE: ...] wrapper if present
            raw = spec.placeholder.strip()
            if raw.startswith("[IMAGE:") and raw.endswith("]"):
                slug = raw[7:-1].strip()
            elif raw.startswith("[") and raw.endswith("]"):
                slug = raw[1:-1].strip()
            else:
                slug = raw.strip()

            # Build regex that matches [IMAGE: slug] with flexible whitespace
            escaped_slug = re.escape(slug)
            placeholder_re = re.compile(
                rf"\[IMAGE:\s*{escaped_slug}\s*\]", re.IGNORECASE
            )

            try:
                img_path = generate_image(spec.model_dump(), images_dir)
                logger.info("Image generated: %s", img_path)

                # Build markdown image link
                caption_line = f"*{spec.caption}*"
                _CHART_TYPES = {"comparison_chart", "market_chart", "economic_chart"}
                if spec.image_type in _CHART_TYPES:
                    caption_line += "\n\n*Illustrative diagram generated for explanatory purposes.*"
                img_md = (
                    f"\n\n![{spec.alt}](images/{fname})\n\n"
                    f"{caption_line}\n\n"
                )

                # Try regex replacement first, fall back to exact string replace
                new_md, count = placeholder_re.subn(img_md, md)
                if count > 0:
                    md = new_md
                    logger.info("Replaced %d placeholder(s) for slug=%s", count, slug)
                elif spec.placeholder in md:
                    md = md.replace(spec.placeholder, img_md)
                    logger.info("Replaced placeholder (exact match) for slug=%s", slug)
                else:
                    logger.warning(
                        "Placeholder not found in markdown for slug=%s (placeholder=%r)",
                        slug, spec.placeholder,
                    )

            except Exception as exc:
                logger.error("Image generation failed for %s: %s", slug, exc)
                fallback = (
                    f"\n> **[Image not generated]** {spec.caption}\n"
                    f"> Diagram type: {spec.image_type}\n"
                )
                new_md, count = placeholder_re.subn(fallback, md)
                if count > 0:
                    md = new_md
                else:
                    md = md.replace(spec.placeholder, fallback)

    # Clean up any remaining unreplaced [IMAGE: ...] placeholders
    md = re.sub(
        r"\[IMAGE:\s*[^\]]+\]",
        "",
        md,
    )

    # remove stray closing brackets
    md = re.sub(r"(?m)^\]\s*$", "", md)

    # Remove weak generic citations like (Source)
    md = re.sub(r"\(Source\)", "", md)

    # Remove stray single-digit lines (artifacts from LLM placeholder numbering)
    md = re.sub(r"(?m)^\d\s*$\n?", "", md)

    # Write final blog file
    filename = f"{_safe_slug(plan.blog_title)}.md"
    blog_path = output_dir / filename
    blog_path.write_text(md, encoding="utf-8")
    logger.info("Blog exported to: %s", blog_path)

    return {"status": "done", "final": md}