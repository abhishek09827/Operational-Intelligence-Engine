"""Deterministic evidence bundles.

Every claim the triage engine makes must point back at an entry in this bundle.
The bundle is built **before** the LLM is called and is the only thing the model
is allowed to cite, which is what makes the citations verifiable rather than
decorative.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.schemas.v2.alert import SanitizedAlertContext

# Evidence source types, matching VerifiableCitation.source_type
SOURCE_ALERT = "metric"
SOURCE_LOG = "log"

# Keep prompts bounded: this many characters of raw log context maximum.
MAX_LOG_SNIPPET_CHARS = 2000


@dataclass(frozen=True)
class EvidenceItem:
    """One citable fact handed to the model, referenced by its index."""

    index: int
    source_type: str
    source_id: str
    snippet: str

    def as_prompt_line(self) -> str:
        return f"[{self.index}] ({self.source_type}) {self.source_id}\n{self.snippet}"


def build_evidence(alert: SanitizedAlertContext) -> List[EvidenceItem]:
    """Build the ordered, index-addressable evidence bundle for an alert.

    Index 0 is always the alert itself, so a model that cites nothing still
    yields at least one verifiable, non-hallucinated citation downstream.
    """
    evidence: List[EvidenceItem] = [
        EvidenceItem(
            index=0,
            source_type=SOURCE_ALERT,
            source_id=f"alert:{alert.fingerprint}",
            snippet=(
                f"{alert.alertname} ({alert.severity}) on {alert.service_name} "
                f"in {alert.environment}: {alert.summary}"
            ),
        )
    ]

    if alert.description:
        evidence.append(
            EvidenceItem(
                index=len(evidence),
                source_type=SOURCE_ALERT,
                source_id=f"annotation:{alert.fingerprint}",
                snippet=alert.description[:MAX_LOG_SNIPPET_CHARS],
            )
        )

    if alert.raw_logs_sanitized:
        evidence.append(
            EvidenceItem(
                index=len(evidence),
                source_type=SOURCE_LOG,
                source_id=f"log-window:{alert.service_name}",
                snippet=alert.raw_logs_sanitized[:MAX_LOG_SNIPPET_CHARS],
            )
        )

    return evidence
