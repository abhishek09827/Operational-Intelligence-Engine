import pytest

from app.core.config import settings
from app.llm.client import LLMError
from app.sanitizer.ingestion import AlertIngestionService
from app.schemas.v2.alert import DirectAlertIngestRequest, RoutingDecision
from app.triage import pipeline
from app.triage.evidence import build_evidence
from app.triage.fast_path import FastPathDraft, FastPathResult, citations_from_refs, run_fast_path
from app.triage.pipeline import TIER_FAST_PATH, TIER_SWARM, triage_alert

GROUNDED_JSON = """
Here is my triage:
```json
{
  "root_cause_summary": "Checkout latency rose after the DB connection pool saturated.",
  "confidence_score": 0.66,
  "remediation_steps": ["Scale the connection pool", "Watch p99 for 10 minutes"],
  "evidence_refs": [0, 1],
  "unknowns": ["No deployment diff was available"]
}
```
"""


class FakeClient:
    """Stand-in provider that records the prompt it received."""

    provider = "fake"
    model = "fake-1"

    def __init__(self, response: str = GROUNDED_JSON, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def complete(self, system_prompt, user_prompt, *, json_mode=True):
        self.calls.append(
            {"system": system_prompt, "user": user_prompt, "json_mode": json_mode}
        )
        if self.error:
            raise self.error
        return self.response


def make_alert(**overrides):
    payload = {
        "alertname": "HighLatencyWarning",
        "service_name": "checkout-service",
        "severity": "warning",
        "environment": "production",
        "summary": "P99 latency 850ms",
        "raw_logs": "WARN slow query duration=850ms",
    }
    payload.update(overrides)
    return AlertIngestionService.process_direct_request(DirectAlertIngestRequest(**payload))


def test_evidence_bundle_is_indexed_and_ordered():
    evidence = build_evidence(make_alert())
    assert [item.index for item in evidence] == [0, 1]
    assert evidence[0].source_type == "metric"
    assert evidence[0].source_id.startswith("alert:")
    assert evidence[1].source_type == "log"


def test_fast_path_returns_grounded_draft_and_provider_metadata():
    client = FakeClient()
    result = run_fast_path(make_alert(), client=client)

    assert isinstance(result, FastPathResult)
    assert result.degraded is False
    assert result.provider == "fake"
    assert result.model == "fake-1"
    assert result.draft.confidence_score == pytest.approx(0.66)
    assert result.draft.evidence_refs == [0, 1]

    # The model must be handed the sanitized, indexed evidence bundle.
    prompt = client.calls[0]["user"]
    assert "[0]" in prompt and "[1]" in prompt
    assert "WARN slow query duration=850ms" in prompt
    assert client.calls[0]["json_mode"] is True


def test_fast_path_citation_mapping_uses_real_sources_only():
    evidence = run_fast_path(make_alert(), client=FakeClient()).evidence
    mapped = citations_from_refs([1], evidence)
    assert len(mapped) == 1
    assert mapped[0].source_type == "log"
    assert mapped[0].source_id == "log-window:checkout-service"


def test_fast_path_drops_hallucinated_evidence_indexes():
    mapped = citations_from_refs([42], build_evidence(make_alert()))
    assert len(mapped) == 1
    assert mapped[0].source_id.startswith("alert:")


def test_fast_path_degrades_when_response_has_no_json():
    result = run_fast_path(make_alert(), client=FakeClient(response="I cannot help with that"))

    assert result.degraded is True
    assert result.provider is None
    assert result.draft.confidence_score == pytest.approx(0.25)
    assert result.draft.evidence_refs == [0]
    assert result.draft.unknowns


def test_fast_path_degrades_on_provider_failure_instead_of_raising():
    result = run_fast_path(make_alert(), client=FakeClient(error=LLMError("ollama unreachable")))

    assert result.degraded is True
    assert "unavailable" in result.draft.root_cause_summary
    assert result.draft.remediation_steps


def test_pipeline_assembles_fast_path_response(monkeypatch):
    decision = RoutingDecision(
        tier=TIER_FAST_PATH,
        reasoning="localized",
        estimated_complexity="low",
        recommended_agents=["FastPathInvestigator"],
    )
    monkeypatch.setattr(settings, "TRIAGE_LLM_ENABLED", True)
    monkeypatch.setattr(
        pipeline,
        "run_fast_path",
        lambda alert: FastPathResult(
            draft=FastPathDraft(
                root_cause_summary="Pool saturation caused the latency spike.",
                confidence_score=0.7,
                remediation_steps=["Scale the pool"],
                evidence_refs=[0],
                unknowns=["No deploy diff"],
            ),
            evidence=build_evidence(alert),
            provider="fake",
            model="fake-1",
            degraded=False,
        ),
    )

    response = triage_alert(make_alert(), decision, "inc-v2-test")
    assert response.routing_tier == TIER_FAST_PATH
    assert response.status == "triaged"
    assert response.confidence_score == pytest.approx(0.7)
    assert response.llm_provider == "fake"
    assert response.citations[0].reference_snippet
    assert response.unknowns == ["No deploy diff"]


def test_pipeline_stub_is_deterministic_when_llm_disabled(monkeypatch):
    decision = RoutingDecision(
        tier=TIER_FAST_PATH,
        reasoning="localized",
        estimated_complexity="low",
        recommended_agents=[],
    )
    monkeypatch.setattr(settings, "TRIAGE_LLM_ENABLED", False)

    response = triage_alert(make_alert(), decision, "inc-v2-test")
    assert response.status == "awaiting_llm"
    assert response.confidence_score == 0.0
    assert response.llm_provider is None
    assert "TRIAGE_LLM_ENABLED=false" in response.root_cause_summary


def test_pipeline_dispatches_swarm_tier_and_assembles_result(monkeypatch):
    decision = RoutingDecision(
        tier=TIER_SWARM,
        reasoning="Escalated to multi-agent swarm",
        estimated_complexity="high",
        recommended_agents=["IncidentCommander"],
    )
    alert = make_alert(severity="critical")
    canned = FastPathResult(
        draft=FastPathDraft(
            root_cause_summary="Connection pool exhaustion cascaded to checkout.",
            confidence_score=0.8,
            remediation_steps=["Scale the connection pool"],
            evidence_refs=[0],
            unknowns=["No deployment diff"],
        ),
        evidence=build_evidence(alert),
        provider="fake",
        model="fake-1",
        degraded=False,
    )
    monkeypatch.setattr("app.triage.swarm.run_swarm", lambda alert_arg, **kwargs: canned)

    response = triage_alert(alert, decision, "inc-v2-test")
    assert response.routing_tier == TIER_SWARM
    assert response.status == "triaged"
    assert response.llm_provider == "fake"
    assert "cascaded" in response.root_cause_summary
    assert response.citations[0].source_id.startswith("alert:")
