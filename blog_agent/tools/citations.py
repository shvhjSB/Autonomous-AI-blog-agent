"""Citation verification.

The writer prompt demands `(Source Title - URL)` citations and forbids citing
anything outside the evidence pack, but nothing enforced that — so a model
inventing a plausible URL shipped straight into the post. This module checks
every cited link against two independent tests:

* **grounded** — the URL actually came from the research evidence
* **live**     — the URL resolves over HTTP

Both are pure network/string work with **no LLM calls**, so verification costs
nothing against the free-tier quota that limits everything else here.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, List, Optional, Set
from urllib.parse import urlparse, urlunparse

import requests

logger = logging.getLogger(__name__)

# Markdown links [text](url) — the leading (?<!!) skips ![alt](img) images.
_MD_LINK = re.compile(r"(?<!!)\[([^\]]*)\]\((https?://[^)\s]+)\)")

# Bare URLs, including the "(Title - URL)" citation style the writer uses.
_BARE_URL = re.compile(r"https?://[^\s)<>\]\"']+")

_CHECK_TIMEOUT = 12
_MAX_WORKERS = 8


def _normalize(url: str) -> str:
    """Canonical form for comparison: no scheme diff, no www., no trailing /."""
    try:
        p = urlparse(url.strip().rstrip(".,;"))
    except Exception:
        return url.strip().lower()

    netloc = p.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = p.path.rstrip("/")

    return urlunparse(("", netloc, path, "", p.query, "")).lstrip("/")


def extract_urls(markdown: str) -> List[str]:
    """Return every distinct external URL cited in the post, in order."""
    # Ignore fenced code blocks: a URL in a snippet is illustrative, not a claim.
    prose = re.sub(r"(?ms)^[ \t]*```.*?^[ \t]*```[ \t]*$", "", markdown)

    found: List[str] = []
    seen: Set[str] = set()

    for match in list(_MD_LINK.finditer(prose)) + list(_BARE_URL.finditer(prose)):
        url = (match.group(2) if match.re is _MD_LINK else match.group(0)).rstrip(".,;")
        key = _normalize(url)
        if key not in seen:
            seen.add(key)
            found.append(url)

    return found


def _is_live(url: str) -> Optional[bool]:
    """True if the URL resolves, False if it clearly does not, None if unknown."""
    try:
        resp = requests.head(url, timeout=_CHECK_TIMEOUT, allow_redirects=True)
        # Plenty of sites reject HEAD but serve GET fine.
        if resp.status_code >= 400:
            resp = requests.get(url, timeout=_CHECK_TIMEOUT, allow_redirects=True,
                                stream=True)
            resp.close()
        if resp.status_code == 404 or resp.status_code == 410:
            return False
        if resp.status_code >= 500 or resp.status_code == 403:
            # Server trouble or bot-blocking says nothing about the citation.
            return None
        return resp.status_code < 400
    except requests.RequestException:
        return None


def verify_citations(
    markdown: str,
    evidence_urls: Iterable[str],
    check_live: bool = True,
) -> dict:
    """Check every cited URL for grounding and reachability.

    Returns a plain dict so it can live in LangGraph state and be serialised.
    """

    grounded_keys = {_normalize(u) for u in evidence_urls if u}
    urls = extract_urls(markdown)

    if not urls:
        return {"total": 0, "grounded": 0, "ungrounded": [], "dead": [],
                "unverified": []}

    ungrounded = [u for u in urls if _normalize(u) not in grounded_keys]

    dead: List[str] = []
    unverified: List[str] = []

    if check_live:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            for url, live in zip(urls, pool.map(_is_live, urls)):
                if live is False:
                    dead.append(url)
                elif live is None:
                    unverified.append(url)

    report = {
        "total": len(urls),
        "grounded": len(urls) - len(ungrounded),
        "ungrounded": ungrounded,
        "dead": dead,
        "unverified": unverified,
    }

    logger.info(
        "Citations: %d total, %d grounded, %d ungrounded, %d dead.",
        report["total"], report["grounded"], len(ungrounded), len(dead),
    )

    return report


def strip_bad_citations(markdown: str, bad_urls: Iterable[str]) -> str:
    """Remove citations pointing at the given URLs, keeping the sentence.

    `(Title - https://x)` is dropped whole; a markdown link is reduced to its
    anchor text so the prose still reads correctly.
    """
    out = markdown

    for url in bad_urls:
        esc = re.escape(url)
        # "(Some Title - https://x)" or "(https://x)"
        out = re.sub(rf"\s*\([^()]*{esc}[^()]*\)", "", out)
        # "[anchor](https://x)" -> "anchor"
        out = re.sub(rf"\[([^\]]*)\]\({esc}\)", r"\1", out)

    return out
