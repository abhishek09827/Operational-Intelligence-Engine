"""Time-windowed log collector: fetch only ``[T-15m, T+5m]`` evidence.

Deterministic context scoping is one of the project's five differentiators: the
tool never ships the whole log file to the model, only lines whose parsed
timestamp falls inside the alert's window and that mention the alerted service.

Every line is passed through the secret/PII sanitizer before it can become
evidence — logs are the most credential-rich artefact we handle.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Protocol, Sequence, Tuple

from app.core.config import settings
from app.sanitizer.scrubber import sanitize_text
from app.schemas.v2.alert import SanitizedAlertContext
from app.tools.base import EvidenceFact, ToolResult

logger = logging.getLogger(__name__)

TOOL_NAME = "log_collector"
SOURCE_TYPE = "log"
# Evidence presentation bound: lines per fact, so one fact stays prompt-sized.
LINES_PER_FACT = 40


class LogSource(Protocol):
    """Where raw lines come from (files today, Loki/ELK in production)."""

    def lines_for_service(self, service_name: str) -> Iterable[Tuple[str, str]]:
        """Yield ``(origin, line)`` pairs for a service."""
        ...


def _parse_timestamp(line: str) -> Optional[datetime]:
    """Parse a leading ISO-8601 timestamp; ``None`` when absent."""
    token = line.strip().split(" ", 1)[0].replace("Z", "+00:00")
    if "T" not in token or ":" not in token:
        return None
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class FileLogSource:
    """Reads ``<LOG_DIR>/*<service>*.log`` and every ``*.log`` as a fallback."""

    def __init__(self, log_dir: Optional[str] = None) -> None:
        self.log_dir = Path(log_dir or settings.LOG_DIR)

    def lines_for_service(self, service_name: str) -> Iterable[Tuple[str, str]]:
        if not self.log_dir.exists():
            return
        files = sorted(self.log_dir.glob("*.log"))
        preferred = [f for f in files if service_name.replace("-", "_") in f.stem or service_name in f.stem]
        for path in preferred or files:
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    for line in handle:
                        yield path.name, line.rstrip("\n")
            except OSError as exc:  # unreadable file must not break the tool
                logger.warning("log_collector: cannot read %s: %s", path, exc)


class SequenceLogSource:
    """In-memory source for tests and the chaos testbed."""

    def __init__(self, entries: Sequence[Tuple[str, str]]) -> None:
        self.entries = entries

    def lines_for_service(self, service_name: str) -> Iterable[Tuple[str, str]]:
        return iter(self.entries)


class LogCollector:
    """Collect the alert's log evidence for ``[start, end]`` only."""

    def __init__(self, source: Optional[LogSource] = None) -> None:
        self.source = source or FileLogSource()

    def collect(self, alert: SanitizedAlertContext) -> ToolResult:
        try:
            return self._collect(alert)
        except Exception as exc:  # never let a tool break triage
            logger.warning("log_collector failed: %s", exc)
            return ToolResult.failure(TOOL_NAME, f"log collection failed: {exc}")

    def _collect(self, alert: SanitizedAlertContext) -> ToolResult:
        start = alert.time_window_start
        end = alert.time_window_end
        service = alert.service_name

        matched: List[str] = []
        for origin, line in self.source.lines_for_service(service):
            stamp = _parse_timestamp(line)
            if stamp is None or not (start <= stamp <= end):
                continue
            if service not in line and f"{service}" not in origin and not _mentions_service(origin, service):
                continue
            matched.append(sanitize_text(line))

        matched = matched[-settings.LOG_MAX_LINES :]
        if not matched:
            return ToolResult.failure(
                TOOL_NAME,
                f"no lines for '{service}' within [{start.isoformat()}, {end.isoformat()}]",
            )

        facts = [
            EvidenceFact(
                source_type=SOURCE_TYPE,
                source_id=f"log:{service}:{index // LINES_PER_FACT}",
                snippet="\n".join(chunk),
            ).bounded(4000)
            for index, chunk in enumerate(
                [
                    matched[i : i + LINES_PER_FACT]
                    for i in range(0, len(matched), LINES_PER_FACT)
                ]
            )
        ]
        return ToolResult(
            tool=TOOL_NAME,
            ok=True,
            summary=(
                f"{len(matched)} sanitized log lines for '{service}' in "
                f"[{start.isoformat()}, {end.isoformat()}]"
            ),
            facts=facts,
        )


def _mentions_service(origin: str, service: str) -> bool:
    return service in origin or service.replace("-", "_") in origin
