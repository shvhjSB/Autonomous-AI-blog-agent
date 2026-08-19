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

from blog_agent import design
from blog_agent.config import get_settings
from blog_agent.llm import invoke_structured
from blog_agent.prompts import IMAGE_PLANNER_PROMPT
from blog_agent.schemas import BlogState, GlobalImagePlan, ImageSpec
from blog_agent.tools.citations import strip_bad_citations, verify_citations
from blog_agent.tools.images import generate_image, normalize_filename

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


_MERMAID_KEYWORDS = (
    "flowchart", "graph", "sequencediagram", "statediagram", "classdiagram",
    "erdiagram", "journey", "gantt", "pie", "mindmap", "timeline",
    "quadrantchart", "xychart",
)


def _clean_mermaid(source: str) -> str | None:
    """Validate and tidy LLM-produced Mermaid source.

    Returns None when it does not look like Mermaid, so the caller can fall
    back to an image rather than embedding a block that renders as an error.
    """
    if not source:
        return None

    text = source.strip()

    # Models sometimes wrap the value in a fence despite instructions.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()

    if not text:
        return None

    first = text.splitlines()[0].strip().lower()
    if not any(first.startswith(k) for k in _MERMAID_KEYWORDS):
        return None

    return text


def _clean_prose(md: str) -> str:
    """Strip LLM formatting artifacts from the markdown.

    Fenced code blocks are left untouched — a bare ``2`` on its own line is an
    artifact in prose but may be meaningful program output inside a fence.
    """

    def demath(match: re.Match) -> str:
        """Turn a `$...$` TeX span into inline code.

        Nothing in the stack renders math, so LaTeX ships as literal dollar
        signs. Deliberately conservative: only spans that clearly *are* maths
        are touched, so prose like "between $5 and $10" is left alone.
        """
        inner = match.group(1).strip()
        looks_mathy = (
            "\\" in inner                                   # \log, \times
            or re.fullmatch(r"[A-Za-z\u0398\u03A9]+\s*\(.*\)", inner)  # O(n log n)
            or re.fullmatch(r"[A-Za-z]", inner)             # a lone variable
        )
        if not looks_mathy:
            return match.group(0)
        cleaned = re.sub(r"\\text\{([^}]*)\}", r"\1", inner)
        cleaned = cleaned.replace("\\cdot", "*")
        cleaned = re.sub(r"\\([A-Za-z]+)", r"\1", cleaned)   # \log -> log
        cleaned = re.sub(r"\s+", " ", cleaned)
        return f"`{cleaned.strip()}`"

    def scrub(text: str) -> str:
        # LaTeX -> inline code, before the other cosmetic passes.
        text = re.sub(r"\$([^$\n]{1,60})\$", demath, text)
        # Unreplaced [IMAGE: ...] placeholders
        text = re.sub(r"\[IMAGE:\s*[^\]]+\]", "", text)
        # Stray closing brackets left behind by the image planner
        text = re.sub(r"(?m)^\]\s*$", "", text)
        # Weak generic citations like (Source)
        text = re.sub(r"\(Source\)", "", text)
        # Stray single-digit lines (LLM placeholder-numbering artifacts)
        text = re.sub(r"(?m)^\d\s*$\n?", "", text)
        return text

    # Odd indices are the insides of ``` fences; leave them alone.
    parts = re.split(r"(?ms)(^[ \t]*```.*?^[ \t]*```[ \t]*$)", md)
    return "".join(
        part if i % 2 else scrub(part) for i, part in enumerate(parts)
    )


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
    settings = get_settings()
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

    # Cap image count (MAX_IMAGES; IMAGE_PROVIDER=none disables images entirely,
    # leaving _clean_prose to strip the planner's placeholders).
    cap = 0 if settings.image_provider == "none" else settings.max_images
    image_plan.images = image_plan.images[:cap]

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

        # Only create the images/ directory once something actually needs it —
        # a Mermaid-only post shouldn't leave an empty folder behind.
        def _ensure_images_dir() -> Path:
            images_dir.mkdir(parents=True, exist_ok=True)
            return images_dir

        for spec in image_specs:
            # Same normalizer generate_image() uses, so the link and the file
            # on disk always agree.
            fname = normalize_filename(spec.filename)

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

            # Structural diagrams render as Mermaid — free, and the labels
            # stay readable, which image models cannot guarantee.
            mermaid = (
                _clean_mermaid(spec.mermaid or "")
                if settings.diagram_mode in ("auto", "mermaid")
                else None
            )

            if mermaid:
                # Theme the diagram at emission — after _clean_mermaid has
                # validated, since that guard requires the first line to be a
                # diagram keyword. A %%{init}%% directive is the only styling
                # that survives publishing raw markdown to Dev.to or GitHub,
                # where stylesheets are stripped.
                themed = f"{design.mermaid_init(settings.ui_theme)}\n{mermaid}"
                block = (
                    f"\n\n```mermaid\n{themed}\n```\n\n"
                    f"*{spec.caption}*\n\n"
                )
                new_md, count = placeholder_re.subn(lambda _: block, md)
                if count == 0 and spec.placeholder in md:
                    new_md, count = md.replace(spec.placeholder, block), 1
                if count:
                    md = new_md
                    logger.info("Mermaid diagram inlined for slug=%s", slug)
                else:
                    logger.warning("Placeholder not found for mermaid slug=%s", slug)
                continue

            if settings.diagram_mode == "mermaid":
                # Mermaid-only mode: drop anything that would need an image.
                logger.info("Skipping non-structural visual (mermaid-only): %s", slug)
                continue

            try:
                img_path = generate_image(spec.model_dump(), _ensure_images_dir())
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
                new_md, count = placeholder_re.subn(lambda _: img_md, md)
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
                new_md, count = placeholder_re.subn(lambda _: fallback, md)
                if count > 0:
                    md = new_md
                else:
                    md = md.replace(spec.placeholder, fallback)

    md = _clean_prose(md)

    # ------------------------------------------------------------------
    # Verify citations (no LLM calls — pure HTTP + set comparison)
    # ------------------------------------------------------------------
    citation_report = None

    if settings.citation_policy != "off":
        evidence_urls = [e.url for e in state.get("evidence", []) if e.url]
        try:
            citation_report = verify_citations(
                md, evidence_urls, check_live=settings.citation_check_live
            )

            if settings.citation_policy == "strip":
                bad = citation_report["ungrounded"] + citation_report["dead"]
                if bad:
                    md = strip_bad_citations(md, bad)
                    logger.info("Stripped %d unverifiable citation(s).", len(bad))
        except Exception as exc:
            # Verification is a quality check, never a reason to lose the post.
            logger.error("Citation verification failed: %s", exc)

    # Write final blog file
    filename = f"{_safe_slug(plan.blog_title)}.md"
    blog_path = output_dir / filename
    # newline="" prevents Windows text mode rewriting \n as \r\n — publishing
    # APIs and markdown tooling are happier with plain LF.
    blog_path.write_text(md, encoding="utf-8", newline="")
    logger.info("Blog exported to: %s", blog_path)

    return {"status": "done", "final": md, "citation_report": citation_report}