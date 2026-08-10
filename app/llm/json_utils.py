"""Deterministic JSON extraction for LLM responses.

LLMs wrap JSON in prose, fences, or trailing commentary, and reasoning models
sometimes emit the payload after a chain-of-thought block. A regex like
``\\{.*?\\}`` truncates nested objects, so we scan for the first *balanced* JSON
object instead.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _strip_fences(text: str) -> str:
    match = _FENCE_RE.search(text)
    return match.group(1) if match else text


def _first_balanced_object(text: str) -> Optional[str]:
    """Return the first balanced ``{...}`` slice, honouring strings and escapes."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        start = text.find("{", start + 1)
    return None


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of a single JSON object from model output.

    Returns ``None`` when no parseable object can be found; callers are expected
    to degrade deterministically rather than guess.
    """
    if not text:
        return None

    candidate = _strip_fences(text).strip()

    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, TypeError):
        pass

    balanced = _first_balanced_object(candidate)
    if balanced is None:
        return None

    try:
        parsed = json.loads(balanced)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None
