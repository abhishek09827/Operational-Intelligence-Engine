"""Context-enrichment tool contracts.

Every swarm tool follows the same discipline:

* it is **deterministic** (no LLM inside the tool itself),
* it can never raise — failures come back as ``ToolResult(ok=False, error=...)``,
* it emits :class:`EvidenceFact` records that later become *indexed* citations,
  so the swarm can only ever cite data it actually fetched.

Source types align with ``VerifiableCitation.source_type``:
``log`` | ``git_diff`` | ``runbook`` | ``metric``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class EvidenceFact:
    """A citable fact produced by a tool, before index assignment."""

    source_type: str
    source_id: str
    snippet: str

    def bounded(self, limit: int = 600) -> "EvidenceFact":
        return EvidenceFact(self.source_type, self.source_id, self.snippet[:limit])


@dataclass(frozen=True)
class ToolResult:
    """Uniform tool envelope: never an exception, always a summary."""

    tool: str
    ok: bool
    summary: str
    facts: List[EvidenceFact] = field(default_factory=list)
    error: str | None = None

    @classmethod
    def failure(cls, tool: str, error: str) -> "ToolResult":
        return cls(tool=tool, ok=False, summary=f"{tool} unavailable", facts=[], error=error)
