"""
App Settings
============

Shared runtime objects for the platform.
"""

from os import getenv

from agno.models.openai import OpenAIChat, OpenAIResponses
from agno.models.openai.like import OpenAILike


def default_model():
    """Fresh model instance per agent — avoids shared-state footguns."""
    model_provider = getenv("MODEL_PROVIDER", "openai").strip().lower()
    model_id = getenv("MODEL_ID", "gpt-5.6-sol").strip()
    api_key = getenv("OPENAI_API_KEY", "").strip() or "sk-no-key-required"
    base_url = getenv("OPENAI_BASE_URL", "").strip()

    # Local or third-party OpenAI-compatible backends (e.g. llama.cpp server)
    if model_provider in {"openai_like", "openai-like", "llama.cpp", "llamacpp"}:
        return OpenAILike(
            id=model_id,
            api_key=api_key,
            base_url=base_url or "http://host.docker.internal:8080/v1",
        )

    # If a custom OpenAI-compatible base_url is provided, use chat-completions API
    # for best compatibility with local runtimes.
    if base_url:
        return OpenAIChat(id=model_id, api_key=api_key, base_url=base_url)

    # Default cloud OpenAI path.
    return OpenAIResponses(id=model_id)
