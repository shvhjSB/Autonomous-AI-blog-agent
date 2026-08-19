"""
LLM client factory and invocation helpers.

Provides a cached chat-model instance configured from application settings,
plus thin wrappers that eliminate boilerplate across agent nodes.

Providers
---------
``google`` (default)
    Gemini via the AI Studio free tier. Chosen because ``plan_images`` sends
    the whole merged blog and gets it back — a large single round trip that
    other free tiers reject on tokens-per-minute or context limits.
``openai``
    Paid fallback, kept so the original setup still works via ``LLM_PROVIDER``.

Rate limiting
-------------
Free tiers cap requests per minute well below what this pipeline's parallel
writer fan-out produces. A single shared ``InMemoryRateLimiter`` (thread-safe
token bucket) paces every call, which is why ``get_llm`` is cached — all
writer threads must share one bucket. This replaces the blanket sleep that
serialised the whole pipeline.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TypeVar, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.rate_limiters import InMemoryRateLimiter
from pydantic import BaseModel

from blog_agent.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Sensible model + throttle per provider. The RPM figures sit just under the
# published free-tier ceilings, leaving headroom for retries.
_PROVIDER_DEFAULTS: dict[str, dict] = {
    # "gemini-flash-latest" is an alias Google repoints at the current Flash
    # model. Pinned versions get retired for new accounts — `gemini-2.5-flash`
    # already returns "no longer available to new users" — so the alias avoids
    # that whole class of breakage. Pin via LLM_MODEL if you need determinism.
    #
    # It currently resolves to gemini-3.7-flash, whose free tier is 5 req/min
    # and 20 req/day (measured 2026-08-17). 4 rpm keeps us under the per-minute
    # ceiling; exceeding it makes the parallel writers 429 in a cascade.
    "google": {
        "model": "gemini-3-flash-preview",
        "rpm": 4,
        # Each of these carries its own 20 requests/day; the pool is walked in
        # order as each one's daily allowance runs out. Ordered by measured
        # per-minute headroom, most generous first.
        "pool": [
            "gemini-3-flash-preview",
            "gemini-3.6-flash",
            "gemini-flash-latest",
            "gemini-3.5-flash",
        ],
        # Flash-Lite has its own, much larger quota (12+ rapid calls with no
        # throttling observed), so auxiliary work is free of the Flash budget.
        "light_model": "gemini-flash-lite-latest",
        "light_rpm": 10,
    },
    "openai": {
        "model": "gpt-4o-mini",
        "rpm": 0,  # 0 = no client-side throttle
        "pool": ["gpt-4o-mini"],
        "light_model": "gpt-4o-mini",
        "light_rpm": 0,
    },
}


def _model_pool() -> list[str]:
    """Main-tier models to walk through as daily quotas run out."""
    settings = get_settings()
    defaults = _PROVIDER_DEFAULTS[settings.llm_provider]

    if settings.llm_model_pool.strip():
        pool = [m.strip() for m in settings.llm_model_pool.split(",") if m.strip()]
    elif settings.llm_model:
        # An explicit single model pins the pipeline to it.
        pool = [settings.llm_model]
    else:
        pool = list(defaults["pool"])

    return pool


# Models whose daily allowance is spent. Reset when the process restarts or
# when _reset_exhausted() is called; Google's quotas roll over at midnight PT.
_exhausted: set[str] = set()


def _is_daily_quota_error(exc: Exception) -> bool:
    """True when the failure is a spent daily allowance, not a per-minute blip.

    Per-minute limits are worth waiting out (the rate limiter and max_retries
    handle those); a spent day is not, so it should trigger a model switch.
    """
    text = str(exc)
    if "429" not in text and "RESOURCE_EXHAUSTED" not in text:
        return False
    return "PerDay" in text or "limit: 0" in text or "daily" in text.lower()


def _reset_exhausted() -> None:
    """Clear the exhausted-model set (used by tests)."""
    _exhausted.clear()
    get_llm.cache_clear()


# Transient connectivity failures. These are worth retrying on the *same*
# model — unlike a spent daily quota, nothing is gained by switching, and
# burning a model over a DNS blip wastes its remaining allowance.
_TRANSIENT_MARKERS = (
    "getaddrinfo",          # DNS lookup failed
    "connecterror",
    "connection reset",
    "forcibly closed",      # WinError 10054
    "access permissions",   # WinError 10013
    "deadline_exceeded",
    "timeout",
    "temporarily unavailable",
    "503",
    "504",
)


_TRANSIENT_RETRIES = 3


def _is_transient_error(exc: Exception) -> bool:
    """True for network/server hiccups that a plain retry usually clears."""
    text = str(exc).lower()
    return any(m in text for m in _TRANSIENT_MARKERS)


def _build_rate_limiter(rpm: int) -> InMemoryRateLimiter | None:
    """Return a shared token-bucket limiter, or None when unthrottled."""

    if rpm <= 0:
        return None

    limiter = InMemoryRateLimiter(
        requests_per_second=rpm / 60.0,
        # Poll often enough that waiting threads start promptly.
        check_every_n_seconds=0.1,
        # Allow a small burst, but never a full minute's quota at once.
        max_bucket_size=max(1, rpm // 4),
    )

    # The bucket is created empty, so the very first call would block for a
    # full interval (~7.5s at 8 rpm) before the router even runs. A cold
    # pipeline has consumed no quota, so start it full instead.
    limiter.available_tokens = float(limiter.max_bucket_size)

    return limiter


def _active_model() -> str:
    """First main-tier model whose daily allowance is not yet spent."""
    pool = _model_pool()
    for model in pool:
        if model not in _exhausted:
            return model

    # Everything is spent — fall back to the first entry so the caller gets a
    # real quota error rather than an IndexError.
    logger.warning("All %d main models report exhausted daily quota.", len(pool))
    return pool[0]


@lru_cache(maxsize=8)
def get_llm(tier: str = "main", model_override: str | None = None) -> BaseChatModel:
    """
    Return a cached LLM client for the given tier.

    ``main``  — planning and writing; quality-critical.
    ``light`` — router, research synthesis, SEO metadata.

    Cached per (tier, model) so each model gets its own rate limiter, which is
    correct because free-tier quotas are counted per model.
    """

    settings = get_settings()

    provider = settings.llm_provider
    defaults = _PROVIDER_DEFAULTS[provider]

    if tier == "light":
        model_name = model_override or settings.llm_model_light or defaults["light_model"]
        rpm = defaults["light_rpm"]
    else:
        model_name = model_override or _active_model()
        rpm = settings.llm_requests_per_minute or defaults["rpm"]

    rate_limiter = _build_rate_limiter(rpm)

    logger.info(
        "Initializing LLM [%s] → provider=%s model=%s throttle=%s",
        tier,
        provider,
        model_name,
        f"{rpm} req/min" if rpm > 0 else "off",
    )

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.google_api_key:
            logger.warning(
                "GOOGLE_API_KEY is not set — Gemini calls will fail. Get a free "
                "key at https://aistudio.google.com/apikey"
            )

        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.google_api_key or None,
            temperature=0.2,
            timeout=120,
            max_retries=settings.llm_max_retries,
            rate_limiter=rate_limiter,
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model_name,
        api_key=settings.openai_api_key or None,
        temperature=0.2,
        timeout=120,
        max_retries=settings.llm_max_retries,
        rate_limiter=rate_limiter,
    )


def _call_with_failover(run, tier: str):
    """Run ``run(llm)``, moving to the next pooled model on a spent daily quota.

    Only the main tier rotates — the light tier is a single model. Any given
    post is still produced by one model unless that model runs dry mid-post,
    so output stays stylistically consistent.
    """

    import time

    attempts = len(_model_pool()) if tier == "main" else 1
    last_exc: Exception | None = None

    for _ in range(attempts):
        model = _active_model() if tier == "main" else None

        # Transient network failures get their own retries on the same model.
        # A flaky connection would otherwise lose the call outright — and for
        # the planner that costs the entire article.
        for net_try in range(_TRANSIENT_RETRIES + 1):
            try:
                return run(get_llm(tier, model))
            except Exception as exc:
                last_exc = exc

                if _is_transient_error(exc) and net_try < _TRANSIENT_RETRIES:
                    delay = 2 ** net_try
                    logger.warning(
                        "Transient network error (%s) — retrying in %ds.",
                        str(exc)[:70], delay,
                    )
                    time.sleep(delay)
                    continue
                break

        exc = last_exc
        if tier != "main" or exc is None or not _is_daily_quota_error(exc):
            raise exc  # type: ignore[misc]

        if model:
            logger.warning(
                "Daily quota spent on %s — switching to the next model.", model
            )
            _exhausted.add(model)

        if _active_model() in _exhausted:
            break  # pool is fully spent

    assert last_exc is not None
    raise last_exc


def invoke_structured(
    system_prompt: str,
    user_content: str,
    schema: type[T],
    tier: str = "main",
) -> T:
    """
    Call the LLM and parse the response into a Pydantic model.
    """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    result = _call_with_failover(
        lambda llm: llm.with_structured_output(schema).invoke(messages), tier
    )

    logger.debug("invoke_structured → %s", type(result).__name__)

    return cast(T, result)


def _as_text(content: object) -> str:
    """Flatten a message ``content`` field into plain text.

    LangChain types ``content`` as ``str | list[str | dict]``; the list form
    shows up with multimodal or block-style responses.
    """

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
        return "".join(parts)

    return str(content)


def invoke_text(system_prompt: str, user_content: str, tier: str = "main") -> str:
    """
    Call the LLM and return the plain-text response.
    """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    response = _call_with_failover(lambda llm: llm.invoke(messages), tier)

    text = _as_text(response.content).strip()

    logger.debug("invoke_text → %d chars", len(text))

    return text