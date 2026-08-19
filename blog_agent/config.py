"""
Centralized configuration — loads all settings from .env via pydantic-settings.

Usage:
    from blog_agent.config import get_settings
    settings = get_settings()
    print(settings.llm_model)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, auto-loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- API keys ---
    openai_api_key: str = ""
    tavily_api_key: str = ""
    google_api_key: str = ""
    openrouter_api_key: str = ""

    # Cloudflare Workers AI — free image generation (10,000 neurons/day,
    # ~50 neurons per FLUX-1-schnell image, so roughly 200 images/day).
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""

    # --- LLM ---
    # "google" uses the Gemini free tier (AI Studio key); "openai" is the
    # paid fallback. Leave llm_model empty to take the provider's default.
    llm_provider: Literal["google", "openai"] = "google"
    llm_model: str = ""

    # Free-tier quotas are per model, so auxiliary nodes (router, research
    # synthesis, SEO) run on a lighter model. That leaves the scarce
    # main-model quota for the work that actually needs it — planning and
    # writing — roughly doubling posts/day. Empty picks the provider default.
    llm_model_light: str = ""

    # Comma-separated fallback models for the main tier. Every Gemini Flash
    # model is capped at 20 requests/day on the free tier, but each one has its
    # own independent allowance — so when the current model reports its daily
    # quota exhausted, the pipeline moves to the next and keeps going. Four
    # models therefore give ~4x the posts/day at identical quality, since each
    # post is still written entirely by a single model.
    # Empty uses the provider default pool.
    llm_model_pool: str = ""

    # Every section gets its own dedicated LLM call — batching them would cut
    # the call count but thins out later sections in a batch, so it is not
    # done. Section count is fixed rather than a 5-9 range.
    sections_per_post: int = 7

    # Client-side throttle, in requests per minute, shared across the parallel
    # writer fan-out. 0 disables it. Empty (the default) picks a value that
    # suits the provider's free tier.
    llm_requests_per_minute: int = 0

    # Retries on transient failures (429s in particular).
    llm_max_retries: int = 5

    # --- Image generation ---
    # There is no free backend that draws usable technical diagrams: Gemini
    # reports limit: 0 on every image model for free-tier keys, and
    # Pollinations' only model (sana) cannot render readable labels.
    # OpenRouter (Nano Banana 2) is the default, at a *measured* ~$0.068 per
    # image — roughly 17x what its token rate implies, so budget from real
    # usage, not arithmetic. With DIAGRAM_MODE=auto most posts spend nothing
    # because structural diagrams go to Mermaid. "none" omits images entirely.
    image_provider: Literal[
        "cloudflare", "openrouter", "pollinations", "openai", "gemini", "none"
    ] = "cloudflare"

    # Cloudflare Workers AI image model. All FLUX variants bill in neurons out
    # of the same 10,000/day free allocation, but the real cost differs wildly
    # from what the per-tile price list implies — measured 2026-08-17:
    #   flux-2-dev      PERFECT labels, ~60s, but ~3,000 neurons => only ~3
    #                   images/day. Exhausted the daily quota in one run.
    #   flux-2-klein-4b good labels (minor typos), ~9s, far cheaper — the
    #                   sensible default.
    #   flux-1-schnell  cheapest and fastest (~3s) but garbles labels badly.
    cloudflare_image_model: str = "@cf/black-forest-labs/flux-2-klein-4b"

    # How to render planned visuals:
    #   auto    - Mermaid for structural diagrams, images for illustrations
    #   mermaid - Mermaid only; skip anything that needs an image backend
    #   image   - always use the image backend, ignoring Mermaid
    diagram_mode: Literal["auto", "mermaid", "image"] = "auto"

    # OpenRouter image model. Nano Banana 2 gives Pro-level text rendering at
    # Flash pricing; google/gemini-3-pro-image is better but ~4x the cost.
    openrouter_image_model: str = "google/gemini-3.1-flash-image"

    # Caps the credit OpenRouter reserves per image request. One image costs a
    # few thousand tokens; leaving this unset reserves the whole context window
    # and 402s on small balances. Affordability moves around, so keep this low.
    openrouter_max_tokens: int = 4096

    # Upper bound on images per post (the image-planner prompt asks for <= 5).
    max_images: int = 5
    # Gemini fallback model. Must be an image-capable id — plain
    # `gemini-2.0-flash` cannot emit images.
    image_model: str = "gemini-3.1-flash-image"

    # --- Citation verification ---
    # Every cited URL is checked against the research evidence (was it actually
    # found, or invented?) and against the live web (does it resolve?). This is
    # pure HTTP — no LLM calls — so it costs nothing against the free tier.
    #   report - annotate the run with a report, leave the text alone (default)
    #   strip  - additionally remove invented/dead citations from the markdown
    #   off    - skip entirely
    citation_policy: Literal["report", "strip", "off"] = "report"

    # Whether to HTTP-check each URL. Disable to keep verification offline and
    # instant; grounding is still checked against the evidence pack.
    citation_check_live: bool = True

    # --- Look and feel ---
    # Palette shared by the app chrome, the exported article, the Mermaid
    # diagrams and the illustration prompts. See blog_agent/design.py.
    ui_theme: str = "arcade"

    # --- Output ---
    output_dir: str = "output"

    # --- Publisher API keys ---
    devto_api_key: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
