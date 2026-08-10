"""Triage pipeline: route a sanitized alert to an engine and assemble the report.

Routing is decided by :class:`AlertIngestionService.classify_and_route`; this
module owns what happens *after* that decision and is the single place where the
response contract is assembled.

===========  =========================================================
Tier         Engine
===========  =========================================================
fast_path    Single grounded LLM call (``app.triage.fast_path``)
multi_agent  LangGraph swarm with specialist tools (``app.triage.swarm``)
===========  =========================================================

Both engines share one contract-assembly path and one failure policy: when
``TRIAGE_LLM_ENABLED`` is false we return a deterministic stub; when an engine
degrades we still return HTTP 200 with ``status="triaged_degraded"``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from app.core.config import settings
from app.schemas.v2.alert import (
    IncidentTriageResponse,
    RoutingDecision,
    SanitizedAlertContext,
    VerifiableCitation,
)
from app.triage.evidence import build_evidence
from app.triage.fast_path import FastPathResult, citations_from_refs, run_fast_path

logger = logging.getLogger(__name__)

TIER_FAST_PATH = "fast_path"
TIER_SWARM = "multi_agent_swarm"

STATUS_TRIAGED = "triaged"
STATUS_DEGRADED = "triaged_degraded"
STATUS_AWAITING_LLM = "awaiting_llm"

SWARM_AGENTS = [
    "IncidentCommander",
    "TelemetryAgent",
    "DeploymentAgent",
    "RunbookAgent",
    "AdversarialVerifier",
]


def _assemble(
    alert: SanitizedAlertContext,
    decision: RoutingDecision,
    incident_id: str,
    result: FastPathResult,
    tier: str = TIER_FAST_PATH,
) -> IncidentTriageResponse:
    """Turn an engine result into the grounded response contract."""
    steps: List[str] = list(result.draft.remediation_steps)
    if not steps:
        steps = [
            f"Inspect {alert.service_name} telemetry and logs for the window "
            f"[{alert.time_window_start.isoformat()}, {alert.time_window_end.isoformat()}]."
        ]

    return IncidentTriageResponse(
        incident_id=incident_id,
        fingerprint=alert.fingerprint,
        alertname=alert.alertname,
        service_name=alert.service_name,
        severity=alert.severity,
        status=STATUS_DEGRADED if result.degraded else STATUS_TRIAGED,
        routing_tier=tier,
        root_cause_summary=result.draft.root_cause_summary,
        confidence_score=result.draft.confidence_score,
        remediation_steps=steps,
        citations=citations_from_refs(result.draft.evidence_refs, result.evidence),
        unknowns=result.draft.unknowns,
        sanitized_alert=alert,
        llm_provider=result.provider,
        llm_model=result.model,
        created_at=datetime.now(timezone.utc),
    )


def _deterministic_stub(
    alert: SanitizedAlertContext,
    decision: RoutingDecision,
    incident_id: str,
) -> IncidentTriageResponse:
    """Used when ``TRIAGE_LLM_ENABLED=false``: contract intact, no claims made."""
    evidence = build_evidence(alert)
    return IncidentTriageResponse(
        incident_id=incident_id,
        fingerprint=alert.fingerprint,
        alertname=alert.alertname,
        service_name=alert.service_name,
        severity=alert.severity,
        status=STATUS_AWAITING_LLM,
        routing_tier=decision.tier,
        root_cause_summary=(
            f"LLM engines are disabled (TRIAGE_LLM_ENABLED=false); sanitized alert "
            f"'{alert.alertname}' ({alert.severity}) on {alert.service_name} was ingested "
            f"and routed to '{decision.tier}'. No root cause is asserted."
        ),
        confidence_score=0.0,
        remediation_steps=[
            f"Check telemetry and logs for service '{alert.service_name}' between "
            f"{alert.time_window_start.isoformat()} and {alert.time_window_end.isoformat()}.",
            f"Consult the service runbook for '{alert.alertname}'.",
            "Re-run with TRIAGE_LLM_ENABLED=true for automated analysis.",
        ],
        citations=citations_from_refs([0], evidence),
        unknowns=["Automated analysis disabled; human review required."],
        sanitized_alert=alert,
        llm_provider=None,
        llm_model=None,
        created_at=datetime.now(timezone.utc),
    )


def triage_alert(
    alert: SanitizedAlertContext,
    decision: RoutingDecision,
    incident_id: str,
) -> IncidentTriageResponse:
    """Run the routed engine and return the grounded report contract."""
    if not settings.TRIAGE_LLM_ENABLED:
        logger.info(
            "TRIAGE_LLM_ENABLED=false; deterministic stub for alert=%s", alert.alertname
        )
        return _deterministic_stub(alert, decision, incident_id)

    if decision.tier == TIER_SWARM:
        from app.triage.swarm import run_swarm

        return _assemble(alert, decision, incident_id, run_swarm(alert), TIER_SWARM)

    return _assemble(
        alert, decision, incident_id, run_fast_path(alert), TIER_FAST_PATH
    )
