"""Text-completion clients for the three supported LLM providers.

Design notes
------------
* A provider client exposes exactly one method, ``complete``. Anything smarter
  (schema validation, retries, prompt building) lives in ``app.triage``.
* Vendor SDK imports happen lazily inside ``complete`` so importing this package
  never requires an API key and never pays the import cost.
* Provider SDKs are never handed a secret that we then log: failures are
  re-raised as :class:`LLMError` with only non-sensitive context (provider,
  model, endpoint) attached.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when a provider call cannot be completed.

    The triage engine catches this and degrades deterministically instead of
    surfacing a 5xx to the alerting pipeline.
    """


@runtime_checkable
class ChatClient(Protocol):
    """Minimal contract the triage engine depends on."""

    provider: str
    model: str

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = True,
    ) -> str:  # pragma: no cover - protocol definition
        ...


def _flatten_content(content: Any) -> str:
    """Normalise LangChain-style list-of-blocks content into plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return str(content)



@dataclass
class GeminiClient:
    """Google Gemini via ``langchain-google-genai`` (already a dependency)."""

    api_key: str
    model: str
    temperature: float = 0.0
    provider: str = field(default="gemini", init=False)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = True,
    ) -> str:
        if not self.api_key:
            raise LLMError("GOOGLE_API_KEY is not configured")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise LLMError("langchain-google-genai is not installed") from exc

        model_name = self.model
        if not model_name.startswith("gemini-") and not model_name.startswith("models/"):
            model_name = "gemini-2.5-flash"

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=self.api_key,
            temperature=self.temperature,
        )
        if json_mode:
            # Gemini supports the JSON mime type natively; if this SDK build does
            # not expose it, the deterministic JSON extractor still applies.
            try:
                llm = llm.bind(response_mime_type="application/json")
            except Exception:  # pragma: no cover - SDK capability dependent
                pass

        try:
            response = llm.invoke(
                [("system", system_prompt), ("human", user_prompt)]
            )
        except Exception as exc:
            raise LLMError(f"gemini completion failed ({model_name}): {exc}") from exc

        return _flatten_content(getattr(response, "content", response))


@dataclass
class OpenRouterClient:
    """OpenRouter via the raw OpenAI client.

    The raw client is used deliberately: reasoning models (DeepSeek et al.)
    return ``reasoning_details`` that LangChain's parser can choke on.
    """

    api_key: str
    model: str
    base_url: str = "https://openrouter.ai/api/v1"
    temperature: float = 0.0
    provider: str = field(default="openrouter", init=False)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = True,
    ) -> str:
        if not self.api_key:
            raise LLMError("OPENROUTER_API_KEY is not configured")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise LLMError("openai package is not installed") from exc

        client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        request: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if json_mode:
            request["response_format"] = {"type": "json_object"}

        try:
            response = client.chat.completions.create(
                **request, extra_body={"reasoning": {"enabled": True}}
            )
        except Exception:
            # Some providers reject extra_body / response_format; retry minimally.
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                )
            except Exception as exc:
                raise LLMError(
                    f"openrouter completion failed ({self.model}): {exc}"
                ) from exc

        message = response.choices[0].message
        content = getattr(message, "content", None)
        if not content:
            content = getattr(message, "reasoning", None) or getattr(
                message, "reasoning_content", None
            )
        return _flatten_content(content)


@dataclass
class OllamaClient:
    """Ollama over plain HTTP.

    Uses the native ``/api/chat`` endpoint (``format: "json"`` gives structured
    output), so no extra SDK dependency is required — ``httpx`` is already pinned.
    """

    base_url: str = "http://localhost:11434"
    model: str = "qwen3:8b"
    temperature: float = 0.0
    provider: str = field(default="ollama", init=False)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = True,
    ) -> str:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise LLMError("httpx is not installed") from exc

        url = f"{self.base_url.rstrip('/')}/api/chat"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        if json_mode:
            payload["format"] = "json"

        try:
            response = httpx.post(
                url, json=payload, timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise LLMError(
                f"ollama request to {url} failed ({self.model}): {exc}"
            ) from exc

        return _flatten_content((data.get("message") or {}).get("content"))


def resolve_provider(explicit: Optional[str] = None) -> str:
    """Resolve which provider to use, in one deterministic order.

    1. An explicit override (``explicit="ollama"``) always wins.
    2. ``LLM_PROVIDER`` from settings, normalised (``google`` -> ``gemini``).
    3. If OpenRouter is selected but has no key while a Gemini key exists, fall
       back to Gemini rather than failing at request time.
    """
    if explicit:
        candidate = explicit.strip().lower()
        if candidate in {"google", "gemini"}:
            return "gemini"
        if candidate in {"openrouter", "ollama"}:
            return candidate
        raise LLMError(f"Unknown LLM provider: {explicit}")

    configured = (settings.LLM_PROVIDER or "").strip().lower()
    if configured in {"google", "gemini"}:
        return "gemini"
    if configured == "ollama":
        return "ollama"
    if configured in {"openrouter", ""}:
        if settings.OPENROUTER_API_KEY:
            return "openrouter"
        if settings.GOOGLE_API_KEY:
            logger.warning(
                "LLM_PROVIDER=openrouter but no OPENROUTER_API_KEY; using gemini"
            )
            return "gemini"
        return "openrouter"
    raise LLMError(f"Unknown LLM provider in settings: {settings.LLM_PROVIDER}")


def get_chat_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> ChatClient:
    """Build the chat client for the resolved provider.

    Construction performs no I/O and validates no credentials, so it is safe to
    call at import time and trivial to test.
    """
    resolved = resolve_provider(provider)

    if resolved == "gemini":
        return GeminiClient(
            api_key=settings.GOOGLE_API_KEY,
            model=model or settings.GEMINI_MODEL_NAME,
        )
    if resolved == "openrouter":
        return OpenRouterClient(
            api_key=settings.OPENROUTER_API_KEY or "",
            model=model or settings.OPENROUTER_MODEL_NAME,
        )
    return OllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model=model or settings.OLLAMA_MODEL_NAME,
    )
