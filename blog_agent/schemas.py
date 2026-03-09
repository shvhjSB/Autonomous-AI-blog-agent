"""
Pydantic models and LangGraph state definition.

All data structures used across the pipeline live here for a single source of truth.
"""

from __future__ import annotations

import operator
from typing import Annotated, List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Blog plan schemas
# ---------------------------------------------------------------------------

class Task(BaseModel):
    """A single section of the planned blog post."""

    id: int
    title: str
    goal: str = Field(..., description="One sentence: what the reader learns.")
    bullets: List[str] = Field(..., min_length=3, max_length=6)
    target_words: int = Field(..., description="Target word count (120–550).")

    tags: List[str] = Field(default_factory=list)
    requires_research: bool = False
    requires_citations: bool = False
    requires_code: bool = False


class Plan(BaseModel):
    """Structured blog outline produced by the planner."""

    blog_title: str
    audience: str
    tone: str
    blog_kind: Literal[
        "explainer", "tutorial", "news_roundup", "comparison", "system_design"
    ] = "explainer"
    constraints: List[str] = Field(default_factory=list)
    tasks: List[Task]


# ---------------------------------------------------------------------------
# Research schemas
# ---------------------------------------------------------------------------

class EvidenceItem(BaseModel):
    """One piece of evidence harvested from web search."""

    title: str
    url: str
    published_at: Optional[str] = None   # ISO YYYY-MM-DD preferred
    snippet: Optional[str] = None
    source: Optional[str] = None


class RouterDecision(BaseModel):
    """Output of the router node — decides research mode and queries."""

    needs_research: bool
    mode: Literal["closed_book", "hybrid", "open_book"]
    reason: str
    queries: List[str] = Field(default_factory=list)
    max_results_per_query: int = Field(default=5)


class EvidencePack(BaseModel):
    """Wrapper for the list of synthesized evidence items."""

    evidence: List[EvidenceItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Image schemas
# ---------------------------------------------------------------------------

class ImageSpec(BaseModel):
    """Specification for a single AI-generated image."""

    placeholder: str = Field(..., description="e.g. [IMAGE: transformer_encoder]")
    filename: str = Field(..., description="e.g. transformer_encoder.png")
    alt: str
    caption: str
    prompt: str = Field(..., description="Detailed prompt for the image model.")
    image_type: Literal[
        "architecture_diagram",
        "flowchart",
        "comparison_chart",
        "concept_illustration",
        "pipeline_diagram",
        "market_chart",
        "economic_chart",
    ] = "concept_illustration"
    size: Literal["1024x1024", "1024x1536", "1536x1024"] = "1024x1024"
    quality: Literal["low", "medium", "high"] = "medium"


class GlobalImagePlan(BaseModel):
    """LLM output: markdown with placeholders + image specifications."""

    md_with_placeholders: str
    images: List[ImageSpec] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# SEO schemas
# ---------------------------------------------------------------------------

class SEOMetadata(BaseModel):
    """SEO metadata generated for the final blog post."""

    seo_title: str = Field(..., description="SEO-optimized page title (50-60 chars)")
    meta_description: str = Field(..., description="Meta description (under 160 chars)")
    keywords: List[str] = Field(..., description="5-8 relevant SEO keywords")
    slug: str = Field(..., description="URL-friendly slug")
    twitter_title: str = Field(..., description="Twitter card title")
    twitter_description: str = Field(..., description="Twitter card description")
    linkedin_title: str = Field(..., description="LinkedIn share title")
    linkedin_description: str = Field(..., description="LinkedIn share description")


# ---------------------------------------------------------------------------
# LangGraph pipeline state
# ---------------------------------------------------------------------------

class BlogState(TypedDict):
    """Shared mutable state flowing through the LangGraph pipeline.

    The ``sections`` and ``evidence`` fields use ``operator.add`` as a
    reducer so that parallel worker nodes can each append their result
    without conflicts.
    """

    topic: str

    # Pipeline observability
    status: str

    # Router / research
    mode: str
    needs_research: bool
    queries: List[str]
    evidence: Annotated[List[EvidenceItem], operator.add]
    plan: Optional[Plan]

    # Recency control
    as_of: str
    recency_days: int

    # Worker outputs (reducer — lists are concatenated automatically)
    sections: Annotated[List[tuple[int, str]], operator.add]

    # Compiler stage
    merged_md: str
    md_with_placeholders: str
    image_specs: List[ImageSpec]

    # Final rendered blog
    final: str

    # SEO metadata
    seo_metadata: Optional[SEOMetadata]
