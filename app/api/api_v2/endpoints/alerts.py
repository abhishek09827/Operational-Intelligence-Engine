"""v2 alert ingestion endpoints.

    [Prometheus / Alertmanager / Test Trigger]
                       │
                       ▼ POST /api/v2/alerts/triage
         ┌───────────────────────────┐
         │    Alert Ingestion &      │
         │    Secret Sanitization    │
         └─────────────┬─────────────┘
                       ▼
         ┌───────────────────────────┐
         │  Routing & Classification │
         └─────────────┬─────────────┘
             fast_path │ swarm
                       ▼
                app.triage.pipeline
"""
import uuid
from typing import Any, Dict, List, Union

from fastapi import APIRouter, Request

from app.sanitizer.ingestion import AlertIngestionService
from app.schemas.v2.alert import (
    AlertmanagerWebhookPayload,
    DirectAlertIngestRequest,
    IncidentTriageResponse,
)
from app.triage.pipeline import triage_alert

router = APIRouter()


@router.post("/triage", response_model=Union[IncidentTriageResponse, List[IncidentTriageResponse]])
async def ingest_and_triage_alert(request: Request):
    """Ingest, sanitize, route, and triage one alert (or an Alertmanager batch).

    Accepts both standard Prometheus Alertmanager webhook payloads (a JSON body
    containing an ``alerts`` array) and direct test triggers. Every text field is
    passed through the deterministic sanitizer before anything reaches an LLM.
    """
    body = await request.json()

    # Standard Alertmanager webhook: one report per alert in the batch.
    if "alerts" in body:
        contexts = AlertIngestionService.process_webhook(AlertmanagerWebhookPayload(**body))
        return [
            triage_alert(
                alert=context,
                decision=AlertIngestionService.classify_and_route(context),
                incident_id=f"inc-v2-{uuid.uuid4().hex[:8]}",
            )
            for context in contexts
        ]

    # Direct ingest / test trigger.
    alert = AlertIngestionService.process_direct_request(DirectAlertIngestRequest(**body))
    decision = AlertIngestionService.classify_and_route(alert)
    return triage_alert(
        alert=alert,
        decision=decision,
        incident_id=f"inc-v2-{uuid.uuid4().hex[:8]}",
    )


@router.post("/sanitize", response_model=Dict[str, Any])
async def sanitize_payload(payload: Dict[str, Any]):
    """Utility endpoint: redact secrets and PII from an arbitrary JSON payload."""
    from app.sanitizer.scrubber import sanitize_data

    return sanitize_data(payload)
