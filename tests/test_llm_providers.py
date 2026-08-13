import httpx
import pytest

from app.core.config import settings
from app.llm.client import (
    GeminiClient,
    LLMError,
    OllamaClient,
    OpenRouterClient,
    get_chat_client,
    resolve_provider,
)
from app.llm.json_utils import extract_json_object


def test_resolve_provider_explicit_overrides():
    assert resolve_provider("google") == "gemini"
    assert resolve_provider("gemini") == "gemini"
    assert resolve_provider("openrouter") == "openrouter"
    assert resolve_provider("ollama") == "ollama"


def test_resolve_provider_rejects_unknown_provider():
    with pytest.raises(LLMError):
        resolve_provider("bedrock")


def test_resolve_provider_falls_back_to_gemini_without_openrouter_key(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "google-key")
    assert resolve_provider() == "gemini"


def test_resolve_provider_honours_configured_ollama(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    assert resolve_provider() == "ollama"


def test_get_chat_client_builds_each_provider(monkeypatch):
    gemini = get_chat_client("gemini", model="gemini-2.5-flash")
    assert isinstance(gemini, GeminiClient)
    assert gemini.provider == "gemini"
    assert gemini.model == "gemini-2.5-flash"

    openrouter = get_chat_client("openrouter", model="deepseek/deepseek-v4-flash-latest")
    assert isinstance(openrouter, OpenRouterClient)
    assert openrouter.provider == "openrouter"
    assert openrouter.base_url.endswith("/api/v1")

    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://ollama.internal:11434")
    ollama = get_chat_client("ollama", model="qwen2.5")
    assert isinstance(ollama, OllamaClient)
    assert ollama.provider == "ollama"
    assert ollama.base_url == "http://ollama.internal:11434"
    assert ollama.model == "qwen2.5"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_ollama_client_posts_structured_json_request(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        captured["timeout"] = timeout
        return _FakeResponse({"message": {"content": '{"ok": true}'}})

    monkeypatch.setattr(httpx, "post", fake_post)

    client = OllamaClient(base_url="http://localhost:11434", model="llama3.1")
    assert client.complete("sys", "user") == '{"ok": true}'

    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["payload"]["model"] == "llama3.1"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["format"] == "json"
    assert captured["payload"]["messages"][0] == {"role": "system", "content": "sys"}
    assert captured["payload"]["messages"][1] == {"role": "user", "content": "user"}


def test_ollama_client_can_skip_json_mode(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["payload"] = json
        return _FakeResponse({"message": {"content": "plain text answer"}})

    monkeypatch.setattr(httpx, "post", fake_post)

    assert OllamaClient().complete("s", "u", json_mode=False) == "plain text answer"
    assert "format" not in captured["payload"]


def test_ollama_client_raises_llm_error_when_unreachable(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", boom)

    with pytest.raises(LLMError):
        OllamaClient().complete("sys", "user")


def test_extract_json_object_handles_fences_prose_and_nesting():
    assert extract_json_object('{"a": 1}') == {"a": 1}
    assert extract_json_object('```json\n{"a": {"b": 2}}\n```') == {"a": {"b": 2}}
    assert extract_json_object('Here is the analysis:\n{"a": {"b": [1, 2]}}\nHope that helps') == {
        "a": {"b": [1, 2]}
    }
    assert extract_json_object("no json here") is None
    assert extract_json_object("") is None
