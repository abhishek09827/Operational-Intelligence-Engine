from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"
    INFO = "info"


class AlertStatus(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"


class AlertItem(BaseModel):
    """Represents an individual alert from Prometheus Alertmanager or custom payload."""
    status: AlertStatus = AlertStatus.FIRING
    labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Labels such as alertname, service, severity, instance, cluster, env"
    )
    annotations: Dict[str, str] = Field(
        default_factory=dict,
        description="Annotations like summary, description, runbook_url, dashboard"
    )
    starts_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the alert started firing (ISO-8601)"
    )
    ends_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the alert ended/resolved"
    )
    generator_url: Optional[str] = Field(
        default=None,
        description="Direct link to the Prometheus expression or rule"
    )
    fingerprint: Optional[str] = Field(
        default=None,
        description="Unique alert fingerprint hash from Alertmanager"
    )


class AlertmanagerWebhookPayload(BaseModel):
    """Standard Prometheus Alertmanager webhook payload schema."""
    version: Optional[str] = "4"
    group_key: Optional[str] = Field(default=None, alias="groupKey")
    status: AlertStatus = AlertStatus.FIRING
    receiver: Optional[str] = None
    group_labels: Dict[str, str] = Field(default_factory=dict, alias="groupLabels")
    common_labels: Dict[str, str] = Field(default_factory=dict, alias="commonLabels")
    common_annotations: Dict[str, str] = Field(default_factory=dict, alias="commonAnnotations")
    external_url: Optional[str] = Field(default=None, alias="externalURL")
    alerts: List[AlertItem] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class DirectAlertIngestRequest(BaseModel):
    """Direct or test trigger payload for alert triage."""
    alertname: str = Field(..., description="Name of the alert (e.g. PostgresConnectionPoolExhaustion)")
    service_name: str = Field(..., description="Target service name (e.g. order-service, payment-service)")
    severity: str = Field(default="high", description="critical, high, warning, or info")
    environment: str = Field(default="production", description="Environment e.g. production, staging")
    summary: str = Field(..., description="Short summary of the alert condition")
    description: Optional[str] = Field(default="", description="Detailed explanation or error snippet")
    time_window_start: Optional[datetime] = Field(default=None, description="Start of observed anomaly")
    time_window_end: Optional[datetime] = Field(default=None, description="End of observed anomaly")
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    raw_logs: Optional[str] = Field(default=None, description="Optional raw log snippet attached directly")


class SanitizedAlertContext(BaseModel):
    """Sanitized alert context prepared for routing and downstream engine."""
    alertname: str
    service_name: str
    severity: str
    environment: str
    summary: str
    description: str
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    time_window_start: datetime
    time_window_end: datetime
    fingerprint: str
    raw_logs_sanitized: Optional[str] = None


class RoutingDecision(BaseModel):
    """Engine routing decision: fast-path vs. multi-agent swarm escalation."""
    tier: str = Field(..., description="'fast_path' or 'multi_agent_swarm'")
    reasoning: str
    estimated_complexity: str = Field(..., description="'low', 'medium', or 'high'")
    recommended_agents: List[str] = Field(default_factory=list)


class VerifiableCitation(BaseModel):
    """Verifiable source citation grounding each statement."""
    source_type: str = Field(..., description="'log', 'git_diff', 'runbook', 'metric'")
    source_id: str = Field(..., description="Log timestamp/line ID, commit sha, runbook name")
    reference_snippet: str = Field(..., description="Quoted snippet validating the assertion")


class IncidentTriageResponse(BaseModel):
    """V2 Grounded Incident Report contract with strict citations."""
    incident_id: str
    fingerprint: str
    alertname: str
    service_name: str
    severity: str
    status: str
    routing_tier: str
    root_cause_summary: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    remediation_steps: List[str] = Field(default_factory=list)
    citations: List[VerifiableCitation] = Field(default_factory=list)
    unknowns: List[str] = Field(
        default_factory=list,
        description="What the evidence did not establish (explicit non-claims).",
    )
    llm_provider: Optional[str] = Field(
        default=None,
        description="Provider that produced the analysis ('gemini'/'openrouter'/'ollama'), None for deterministic stubs.",
    )
    llm_model: Optional[str] = Field(default=None, description="Model that produced the analysis.")
    sanitized_alert: SanitizedAlertContext
    created_at: datetime = Field(default_factory=datetime.utcnow)
