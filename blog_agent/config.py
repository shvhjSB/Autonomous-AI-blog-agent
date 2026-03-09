"""
Centralized configuration — loads all settings from .env via pydantic-settings.

Usage:
    from blog_agent.config import get_settings
    settings = get_settings()
    print(settings.llm_model)
"""

from __future__ import annotations

from functools import lru_cache

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

    # --- LLM ---
    llm_model: str = "gpt-4o-mini"

    # --- Image generation ---
    max_images: int = 3
    image_model: str = "gemini-2.0-flash-exp"

    # --- Output ---
    output_dir: str = "output"

    # --- Publisher API keys ---
    devto_api_key: str = ""
    hashnode_token: str = ""
    hashnode_publication_id: str = ""
    medium_token: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
