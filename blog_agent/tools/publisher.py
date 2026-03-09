"""
Blog publishing utilities.

Publishes generated blog posts to external platforms:
- Dev.to
- Hashnode
- Medium (placeholder)

Also provides an export-package helper for JSON download.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

import requests

from blog_agent.config import get_settings

logger = logging.getLogger(__name__)


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

    # Dev.to limits tags to 4 and lowercase
    clean_tags = [t.lower().replace(" ", "") for t in (tags or [])][:4]

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
# Hashnode
# ---------------------------------------------------------------------------

def publish_to_hashnode(
    title: str,
    markdown: str,
    tags: Optional[List[str]] = None,
    token: Optional[str] = None,
    publication_id: Optional[str] = None,
) -> dict:
    """Publish a blog post to Hashnode via GraphQL API.

    Returns a dict with "success", "url", and optionally "error".
    """
    settings = get_settings()
    key = token or settings.hashnode_token
    pub_id = publication_id or settings.hashnode_publication_id

    if not key:
        return {"success": False, "error": "HASHNODE_TOKEN is not configured."}

    if not pub_id:
        return {"success": False, "error": "HASHNODE_PUBLICATION_ID is not configured."}

    logger.info("Publishing blog to Hashnode: %s", title[:60])

    clean_tags = [{"name": t, "slug": t.lower().replace(" ", "-")} for t in (tags or [])][:5]

    query = """
    mutation PublishPost($input: PublishPostInput!) {
        publishPost(input: $input) {
            post {
                url
                title
            }
        }
    }
    """
    slug = title.lower().replace(" ", "-")
    variables = {
        "input": {
            "title": title,
            "slug": slug,
            "contentMarkdown": markdown,
            "publicationId": pub_id,
            "tags": clean_tags,
        }
    }

    try:
        resp = requests.post(
            "https://gql.hashnode.com",
            headers={
                "Authorization": key,
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": variables},
            timeout=30,
        )

        data = resp.json()

        if "errors" in data:
            error = data["errors"][0].get("message", "Unknown error")
            logger.error("Hashnode publish failed: %s", error)
            return {"success": False, "error": error}

        post = data.get("data", {}).get("publishPost", {}).get("post", {})
        url = post.get("url", "")
        logger.info("Published to Hashnode: %s", url)
        return {"success": True, "url": url}

    except Exception as exc:
        logger.error("Hashnode publish error: %s", exc)
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
