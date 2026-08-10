"""Provider-agnostic LLM access for the OpsPilot triage engine.

The fast path needs exactly one capability: a single, structured completion.
No Agent/Task/Crew abstractions, no framework-owned stdout, no hidden retries.
"""
from app.llm.client import (
    ChatClient,
    GeminiClient,
    LLMError,
    OllamaClient,
    OpenRouterClient,
    get_chat_client,
    resolve_provider,
)
from app.llm.json_utils import extract_json_object

__all__ = [
    "ChatClient",
    "GeminiClient",
    "LLMError",
    "OllamaClient",
    "OpenRouterClient",
    "get_chat_client",
    "resolve_provider",
    "extract_json_object",
]
