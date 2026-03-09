"""
LLM client factory and invocation helpers.

Provides a cached ChatOpenAI instance configured from application settings,
plus thin wrappers that eliminate boilerplate across agent nodes.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from threading import Lock
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from blog_agent.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

RATE_LIMIT_SECONDS = 12  # Gemini free tier = 5 req/min
_last_call_time = 0
_lock = Lock()

def rate_limiter():
    global _last_call_time
    
    with _lock:
        now = time.time()
        elapsed = now - _last_call_time
        
        if elapsed < RATE_LIMIT_SECONDS:
            time.sleep(RATE_LIMIT_SECONDS - elapsed)
            
        _last_call_time = time.time()


@lru_cache(maxsize=1)
def get_llm() -> ChatGoogleGenerativeAI:
    """
    Return a cached LLM client configured from application settings.
    """

    settings = get_settings()

    logger.info("Initializing LLM → Gemini Flash")

    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.google_api_key,
        temperature=0.2,
    )


def invoke_structured(
    system_prompt: str,
    user_content: str,
    schema: type[T],
) -> T:
    """
    Call the LLM and parse the response into a Pydantic model.
    """

    rate_limiter()
    llm = get_llm()

    structured = llm.with_structured_output(schema)

    result = structured.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
    )

    logger.debug("invoke_structured → %s", type(result).__name__)

    return result


def invoke_text(system_prompt: str, user_content: str) -> str:
    """
    Call the LLM and return the plain-text response.
    """

    rate_limiter()
    llm = get_llm()

    response = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
    )

    text = response.content.strip()

    logger.debug("invoke_text → %d chars", len(text))

    return text