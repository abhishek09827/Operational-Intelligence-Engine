"""Fast path: one structured LLM call for localized, low-complexity alerts.

Why no agent framework here
---------------------------
A localized alert needs *one* grounded completion, not a crew of role-playing
agents. The whole pipeline is: build evidence → one prompt → parse → validate →
assemble citations. Every step is deterministic and testable without a network.

Citation grounding
------------------
The model never writes citations. It may only return *indexes* into the evidence
bundle we built, and we map those indexes back to real sources. Invented or
out-of-range indexes are dropped, so a hallucinated citation cannot reach the
report.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError

from app.llm.client import ChatClient, LLMError, get_chat_client
from app.llm.json_utils import extract_json_object
from app.schemas.v2.alert import SanitizedAlertContext, VerifiableCitation
from app.triage.evidence import EvidenceItem, build_evidence

logger = logging.getLogger(__name__)

# Bounded prompt: the evidence bundle is already truncated per item.
MAX_CITATION_CHARS = 280
DEGRADED_CONFIDENCE = 0.25

SYSTEM_PROMPT = (
    "You are an on-call Site Reliability Engineer performing first-pass incident "
    "triage. You reason ONLY from the numbered EVIDENCE bundle provided. "
    "Never invent services, deploys, commits, metrics, or log lines that are not in "
    "the evidence. If the evidence is insufficient, say so in `unknowns` and lower "
    "`confidence_score` instead of guessing. "
    "Respond with a single JSON object and no other text."
)

USER_TEMPLATE = """\
ALERT
name: {alertname}
service: {service_name}
severity: {severity}
environment: {environment}
observed window: {window_start} -> {window_end}

EVIDENCE
{evidence}

TASK
Explain the most likely root cause and the immediate remediation, grounded strictly
in the evidence above. Prefer blast-radius reduction (rollback, restart, scale,
failover) over speculative code changes when the evidence is thin.

Respond with exactly this JSON shape:
{{
  "root_cause_summary": "<1-2 sentences, evidence-grounded>",
  "confidence_score": <float between 0.0 and 1.0>,
  "remediation_steps": ["<ordered, concrete action>", "..."],
  "evidence_refs": [<indexes from EVIDENCE you relied on>],
  "unknowns": ["<what the evidence does not tell you>"]
}}
"""


class FastPathError(RuntimeError):
    """The model was reachable but its answer could not be used."""


class FastPathDraft(BaseModel):
    """The only output shape the fast path accepts from a model."""

    root_cause_summary: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    remediation_steps: List[str] = Field(default_factory=list)
    evidence_refs: List[int] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)


def build_user_prompt(alert: SanitizedAlertContext, evidence: List[EvidenceItem]) -> str:
    """Render the single user turn: the alert plus its indexed evidence bundle."""
    return USER_TEMPLATE.format(
        alertname=alert.alertname,
        service_name=alert.service_name,
        severity=alert.severity,
        environment=alert.environment,
        window_start=alert.time_window_start.isoformat(),
        window_end=alert.time_window_end.isoformat(),
        evidence="\n\n".join(item.as_prompt_line() for item in evidence),
    )


def citations_from_refs(
    refs: List[int],
    evidence: List[EvidenceItem],
) -> List[VerifiableCitation]:
    """Map model-supplied evidence indexes to verifiable citations.

    Out-of-range or duplicate indexes are dropped. If nothing valid remains we
    fall back to index 0 (the alert itself) so the report is never uncited.
    """
    by_index = {item.index: item for item in evidence}
    valid_indexes = sorted({ref for ref in refs if ref in by_index}) or [0]
    return [
        VerifiableCitation(
            source_type=by_index[index].source_type,
            source_id=by_index[index].source_id,
            reference_snippet=by_index[index].snippet[:MAX_CITATION_CHARS],
        )
        for index in valid_indexes
    ]


def degraded_draft(alert: SanitizedAlertContext, reason: str) -> FastPathDraft:
    """Deterministic, honest fallback used when the LLM path cannot complete."""
    return FastPathDraft(
        root_cause_summary=(
            f"Automated root-cause analysis is unavailable ({reason}). "
            f"Alert '{alert.alertname}' ({alert.severity}) is firing on "
            f"{alert.service_name} in {alert.environment}; no root cause is asserted."
        ),
        confidence_score=DEGRADED_CONFIDENCE,
        remediation_steps=[
            f"Inspect {alert.service_name} telemetry and logs for the window "
            f"[{alert.time_window_start.isoformat()}, {alert.time_window_end.isoformat()}].",
            f"Follow the runbook for '{alert.alertname}' and escalate to the service owner.",
            "Re-run triage once the LLM provider is reachable to obtain a grounded root cause.",
        ],
        evidence_refs=[0],
        unknowns=["Root-cause analysis was not performed; human review required."],
    )


class FastPathTriage:
    """Single-turn, evidence-grounded triage for one alert."""

    def __init__(self, client: Optional[ChatClient] = None) -> None:
        self._client = client

    @property
    def client(self) -> ChatClient:
        # Resolved lazily so that constructing the triage object never needs a key.
        if self._client is None:
            self._client = get_chat_client()
        return self._client

    def draft(self, alert: SanitizedAlertContext) -> Tuple[FastPathDraft, List[EvidenceItem]]:
        """Call the provider once and validate its answer against the contract."""
        evidence = build_evidence(alert)
        raw = self.client.complete(SYSTEM_PROMPT, build_user_prompt(alert, evidence))

        payload = extract_json_object(raw)
        if payload is None:
            raise FastPathError("model response contained no JSON object")

        try:
            return FastPathDraft(**payload), evidence
        except ValidationError as exc:
            raise FastPathError(f"model response failed contract validation: {exc}") from exc


@dataclass
class FastPathResult:
    """Everything the response assembler needs, including degradation metadata."""

    draft: FastPathDraft
    evidence: List[EvidenceItem]
    provider: Optional[str] = None
    model: Optional[str] = None
    degraded: bool = False


def run_fast_path(
    alert: SanitizedAlertContext,
    client: Optional[ChatClient] = None,
) -> FastPathResult:
    """Run the fast path, degrading deterministically on any failure.

    This function never raises: an unreachable or misbehaving provider must not
    turn an alert webhook into a 5xx.
    """
    triage = FastPathTriage(client=client)
    try:
        draft, evidence = triage.draft(alert)
    except (LLMError, FastPathError) as exc:
        logger.warning(
            "fast path degraded for alert=%s service=%s: %s",
            alert.alertname,
            alert.service_name,
            exc,
        )
        return FastPathResult(
            draft=degraded_draft(alert, "provider or contract failure"),
            evidence=build_evidence(alert),
            provider=None,
            model=None,
            degraded=True,
        )

    used_client = triage.client
    return FastPathResult(
        draft=draft,
        evidence=evidence,
        provider=getattr(used_client, "provider", None),
        model=getattr(used_client, "model", None),
        degraded=False,
    )

