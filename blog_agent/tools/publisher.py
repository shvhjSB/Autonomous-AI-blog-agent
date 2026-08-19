"""
Blog publishing utilities.

Publishes generated blog posts to external platforms:
- Dev.to

Hashnode support was removed on 2026-08-17: its GraphQL API became Pro-only
(https://hashnode.com/changelog/2026-05-13-graphql-api-paid-access), so both
queries and mutations fail on a free account.

Also provides an export-package helper for JSON download.
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional

import requests

from blog_agent.config import get_settings

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert text into a URL-safe, hyphen-separated slug."""
    s = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return s[:250] or "untitled"


# ---------------------------------------------------------------------------
# Dev.to
# ---------------------------------------------------------------------------

def publish_to_devto(
    title: str,
    markdown: str,
    tags: Optional[List[str]] = None,
    api_key: Optional[str] = None,
) -> dict:
    """Publish a blog post to Dev.to.

    Returns a dict with "success", "url", and optionally "error".
    """
    settings = get_settings()
    key = api_key or settings.devto_api_key

    if not key:
        return {"success": False, "error": "DEVTO_API_KEY is not configured."}

    logger.info("Publishing blog to Dev.to: %s", title[:60])

    # Dev.to allows at most 4 tags and rejects non-alphanumeric characters
    clean_tags = [
        cleaned
        for cleaned in (re.sub(r"[^a-z0-9]", "", t.lower()) for t in (tags or []))
        if cleaned
    ][:4]

    payload = {
        "article": {
            "title": title,
            "published": True,
            "body_markdown": markdown,
            "tags": clean_tags,
        }
    }

    try:
        resp = requests.post(
            "https://dev.to/api/articles",
            headers={
                "api-key": key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        if resp.status_code in (200, 201):
            data = resp.json()
            url = data.get("url", "")
            logger.info("Published to Dev.to: %s", url)
            return {"success": True, "url": url}
        else:
            error = resp.text[:300]
            logger.error("Dev.to publish failed (%d): %s", resp.status_code, error)
            return {"success": False, "error": f"HTTP {resp.status_code}: {error}"}

    except Exception as exc:
        logger.error("Dev.to publish error: %s", exc)
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Export package
# ---------------------------------------------------------------------------

def create_export_package(
    title: str,
    markdown: str,
    seo_metadata: Optional[dict] = None,
) -> str:
    """Create a JSON publishing package for download.

    Returns a JSON string ready for file download.
    """
    package = {
        "title": title,
        "markdown": markdown,
    }

    if seo_metadata:
        package.update({
            "seo_title": seo_metadata.get("seo_title", ""),
            "meta_description": seo_metadata.get("meta_description", ""),
            "keywords": seo_metadata.get("keywords", []),
            "slug": seo_metadata.get("slug", ""),
        })

    return json.dumps(package, indent=2, ensure_ascii=False)
