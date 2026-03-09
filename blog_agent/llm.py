"""
LLM client factory and invocation helpers.

Provides a cached ChatOpenAI instance configured from application settings,
plus thin wrappers that eliminate boilerplate across agent nodes.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from blog_agent.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """
    Return a cached LLM client configured from application settings.
    """

    settings = get_settings()

    # Default to a stable model if .env is missing or incorrect
    model_name = settings.llm_model or "gpt-4o-mini"

    logger.info("Initializing LLM → %s", model_name)

    return ChatOpenAI(
        model=model_name,
        api_key=settings.openai_api_key,
        temperature=0.2,
        timeout=120,
    )


def invoke_structured(
    system_prompt: str,
    user_content: str,
    schema: type[T],
) -> T:
    """
    Call the LLM and parse the response into a Pydantic model.
    """

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