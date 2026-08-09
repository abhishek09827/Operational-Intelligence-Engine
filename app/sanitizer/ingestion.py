import hashlib
from datetime import datetime, timedelta, timezone
from typing import Union, List
from app.schemas.v2.alert import (
    AlertmanagerWebhookPayload,
    DirectAlertIngestRequest,
    SanitizedAlertContext,
    RoutingDecision,
)
from app.sanitizer.scrubber import sanitize_text, sanitize_data


class AlertIngestionService:
    """
    Handles alert ingestion from Prometheus Alertmanager webhooks or direct test triggers.
    Applies secret/PII sanitization and calculates deterministic context bounds.
    """

    @classmethod
    def process_webhook(cls, payload: AlertmanagerWebhookPayload) -> List[SanitizedAlertContext]:
        """Process incoming Alertmanager webhook payload with multiple alerts."""
        sanitized_contexts = []
        now = datetime.now(timezone.utc)

        for alert in payload.alerts:
            # Service and alertname extraction with defaults
            alertname = alert.labels.get("alertname") or alert.labels.get("alert") or "UnknownAlert"
            service_name = alert.labels.get("service") or alert.labels.get("service_name") or alert.labels.get("app") or "default-service"
            severity = alert.labels.get("severity") or alert.labels.get("priority") or "warning"
            environment = alert.labels.get("environment") or alert.labels.get("env") or "production"

            summary = alert.annotations.get("summary") or alert.annotations.get("message") or alertname
            description = alert.annotations.get("description") or alert.annotations.get("details") or ""

            # Time window: default [T - 15m, T + 5m]
            t_event = alert.starts_at or now
            t_start = t_event - timedelta(minutes=15)
            t_end = t_event + timedelta(minutes=5)

            # Scrub all text fields and labels/annotations
            clean_alertname = sanitize_text(alertname)
            clean_service = sanitize_text(service_name)
            clean_summary = sanitize_text(summary)
            clean_description = sanitize_text(description)
            clean_labels = sanitize_data(alert.labels)
            clean_annotations = sanitize_data(alert.annotations)

            # Fingerprint calculation
            fp = alert.fingerprint
            if not fp:
                hash_input = f"{clean_alertname}:{clean_service}:{environment}:{alert.starts_at}"
                fp = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

            ctx = SanitizedAlertContext(
                alertname=clean_alertname,
                service_name=clean_service,
                severity=severity.lower(),
                environment=environment.lower(),
                summary=clean_summary,
                description=clean_description,
                labels=clean_labels,
                annotations=clean_annotations,
                time_window_start=t_start,
                time_window_end=t_end,
                fingerprint=fp,
                raw_logs_sanitized=None,
            )
            sanitized_contexts.append(ctx)

        return sanitized_contexts

    @classmethod
    def process_direct_request(cls, req: DirectAlertIngestRequest) -> SanitizedAlertContext:
        """Process a direct alert ingestion or test trigger."""
        now = datetime.now(timezone.utc)
        t_start = req.time_window_start or (now - timedelta(minutes=15))
        t_end = req.time_window_end or (now + timedelta(minutes=5))

        clean_alertname = sanitize_text(req.alertname)
        clean_service = sanitize_text(req.service_name)
        clean_summary = sanitize_text(req.summary)
        clean_desc = sanitize_text(req.description or "")
        clean_logs = sanitize_text(req.raw_logs) if req.raw_logs else None

        clean_labels = sanitize_data(req.labels)
        clean_annotations = sanitize_data(req.annotations)

        hash_input = f"{clean_alertname}:{clean_service}:{req.environment}:{t_start.isoformat()}"
        fp = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

        return SanitizedAlertContext(
            alertname=clean_alertname,
            service_name=clean_service,
            severity=req.severity.lower(),
            environment=req.environment.lower(),
            summary=clean_summary,
            description=clean_desc,
            labels=clean_labels,
            annotations=clean_annotations,
            time_window_start=t_start,
            time_window_end=t_end,
            fingerprint=fp,
            raw_logs_sanitized=clean_logs,
        )

    @classmethod
    def classify_and_route(cls, alert: SanitizedAlertContext) -> RoutingDecision:
        """
        Routing & Classification:
        - Critical/Sev-1 alerts or multi-service cascading alerts -> MULTI_AGENT_SWARM
        - Localized/Warning/Single-service alerts -> FAST_PATH (single-turn deterministic pre-fetch)
        """
        sev = alert.severity.lower()
        alertname_lower = alert.alertname.lower()

        # Conditions for escalating to multi-agent swarm
        is_sev1 = sev in ("critical", "sev-1", "p1", "fatal")
        is_cascading = any(k in alertname_lower for k in ("cascad", "cross-service", "partition", "outage", "deadlock"))
        is_high_complexity = "cluster" in alert.labels or len(alert.labels.get("affected_services", "").split(",")) > 1

        if is_sev1 or is_cascading or is_high_complexity:
            return RoutingDecision(
                tier="multi_agent_swarm",
                reasoning=f"Escalated to multi-agent swarm due to severity={sev} and systemic risk (cascading={is_cascading}).",
                estimated_complexity="high",
                recommended_agents=[
                    "IncidentCommander",
                    "TelemetryAgent",
                    "DeploymentAgent",
                    "RunbookAgent",
                    "AdversarialVerifier",
                ]
            )

        return RoutingDecision(
            tier="fast_path",
            reasoning=f"Alert is localized to {alert.service_name} with severity '{sev}'. Routed to fast-path single LLM with bounded pre-fetch.",
            estimated_complexity="low" if sev in ("info", "warning") else "medium",
            recommended_agents=["FastPathInvestigator"]
        )
