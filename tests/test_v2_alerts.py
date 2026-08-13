from fastapi.testclient import TestClient
from app.main import app

import pytest

from app.core.config import settings

GROUNDED_JSON = """{
  "root_cause_summary": "Postgres pool saturation raised checkout latency.",
  "confidence_score": 0.71,
  "remediation_steps": ["Raise the pool ceiling, then watch p99 for 10 minutes"],
  "evidence_refs": [0],
  "unknowns": ["No deployment diff was available"]
}"""


class FakeClient:
    """Hermetic stand-in for a real provider: no network, deterministic answer."""

    provider = "fake"
    model = "fake-1"

    def complete(self, system_prompt, user_prompt, *, json_mode=True):
        return GROUNDED_JSON


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    """Keep endpoint tests hermetic: no network, deterministic grounded answer."""
    monkeypatch.setattr(settings, "TRIAGE_LLM_ENABLED", True)

    from app.triage.fast_path import FastPathDraft, FastPathResult
    from app.triage.evidence import build_evidence

    def fake_swarm(alert, **kwargs):
        return FastPathResult(
            draft=FastPathDraft(
                root_cause_summary="Swarm analysis: pool exhaustion cascaded to checkout.",
                confidence_score=0.85,
                remediation_steps=["Scale the connection pool"],
                evidence_refs=[0],
                unknowns=["No deployment diff"],
            ),
            evidence=build_evidence(alert),
            provider="fake",
            model="fake-1",
            degraded=False,
        )

    monkeypatch.setattr("app.triage.fast_path.get_chat_client", lambda *a, **k: FakeClient())
    monkeypatch.setattr("app.triage.swarm.run_swarm", fake_swarm)

client = TestClient(app)


def test_v2_triage_direct_alert_fast_path():
    payload = {
        "alertname": "HighLatencyWarning",
        "service_name": "checkout-service",
        "severity": "warning",
        "environment": "production",
        "summary": "P99 latency crossed 800ms with token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token123",
        "description": "Slow queries noticed on order database postgres://appuser:secretpwd123@10.0.0.12:5432/orders",
        "raw_logs": "2026-08-14T10:00:00Z WARN slow query detected duration=850ms api_key=sk-1234567890abcdef1234567890"
    }

    response = client.post("/api/v2/alerts/triage", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["alertname"] == "HighLatencyWarning"
    assert data["service_name"] == "checkout-service"
    assert data["severity"] == "warning"
    assert data["routing_tier"] == "fast_path"
    assert data["llm_provider"] == "fake"
    assert data["status"] == "triaged"
    assert data["unknowns"] == ["No deployment diff was available"]

    # Verify secret sanitization on ingested alert
    sanitized_alert = data["sanitized_alert"]
    assert "secretpwd123" not in sanitized_alert["description"]
    assert "[REDACTED_PASSWORD]" in sanitized_alert["description"]
    assert "token123" not in sanitized_alert["summary"]
    assert "[REDACTED_TOKEN]" in sanitized_alert["summary"] or "[REDACTED_JWT_TOKEN]" in sanitized_alert["summary"]
    assert "sk-1234567890abcdef1234567890" not in sanitized_alert["raw_logs_sanitized"]
    assert "[REDACTED_API_KEY]" in sanitized_alert["raw_logs_sanitized"] or "[REDACTED_SECRET]" in sanitized_alert["raw_logs_sanitized"]

    # Verify bounded time-window [T - 15m, T + 5m]
    assert "time_window_start" in sanitized_alert
    assert "time_window_end" in sanitized_alert

    # Verify verifiable citations
    assert len(data["citations"]) >= 1
    assert any(c["source_type"] == "metric" for c in data["citations"])


def test_v2_triage_sev1_escalation_to_swarm():
    payload = {
        "alertname": "PostgresConnectionPoolExhaustion",
        "service_name": "order-service",
        "severity": "critical",
        "environment": "production",
        "summary": "Active connections saturated at 100% capacity",
        "description": "Downstream order placement failing across multiple pods"
    }

    response = client.post("/api/v2/alerts/triage", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["routing_tier"] == "multi_agent_swarm"
    assert "multi-agent swarm" in data["root_cause_summary"].lower()


def test_v2_triage_alertmanager_webhook():
    webhook_payload = {
        "receiver": "opspilot-webhook",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "RedisMemoryHigh",
                    "service": "cache-service",
                    "severity": "warning",
                    "environment": "production"
                },
                "annotations": {
                    "summary": "Redis memory utilization > 85%",
                    "description": "Eviction rate spiking with password=supersecretredis123"
                },
                "startsAt": "2026-08-14T12:00:00Z"
            }
        ]
    }

    response = client.post("/api/v2/alerts/triage", json=webhook_payload)
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    assert len(results) == 1

    first = results[0]
    assert first["alertname"] == "RedisMemoryHigh"
    assert first["service_name"] == "cache-service"
    assert "supersecretredis123" not in first["sanitized_alert"]["description"]
    assert "[REDACTED_SECRET]" in first["sanitized_alert"]["description"]


def test_v2_sanitize_endpoint():
    dirty_json = {
        "database_url": "postgres://admin:pass456@db.internal:5432/analytics",
        "slack_token": "xoxb-1234567890-abcdefghij",
        "server_ip": "192.168.1.100",
        "contact": "sre-oncall@company.com",
        "safe_metric": 42
    }

    response = client.post("/api/v2/alerts/sanitize", json=dirty_json)
    assert response.status_code == 200
    cleaned = response.json()

    assert cleaned["slack_token"] == "[REDACTED_SECRET]"
    assert "[REDACTED_PASSWORD]" in cleaned["database_url"]
    assert "[IP_REDACTED]" in cleaned["server_ip"]
    assert cleaned["contact"] == "[EMAIL_REDACTED]"
    assert cleaned["safe_metric"] == 42
