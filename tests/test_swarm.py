import json

from app.core.config import settings
from app.llm.client import LLMError
from app.sanitizer.ingestion import AlertIngestionService
from app.schemas.v2.alert import DirectAlertIngestRequest
from app.tools.base import EvidenceFact, ToolResult
from app.triage.swarm import MAX_LLM_CALLS, run_swarm

COMMANDER_OK = {
    "root_cause_summary": "Checkout latency rose after the DB pool saturated.",
    "confidence_score": 0.8,
    "remediation_steps": ["Raise max_connections", "Watch p99"],
    "evidence_refs": [1],
    "unknowns": [],
}
VERIFIER_SUPPORTED = {
    "supported": True,
    "critique": "claims match evidence",
    "drop_refs": [],
    "adjusted_confidence": 0.55,
}
VERIFIER_REJECTS = {
    "supported": False,
    "critique": "no evidence for the deployment claim",
    "drop_refs": [1],
    "adjusted_confidence": 0.3,
}


def make_alert(**overrides):
    payload = {
        "alertname": "HighLatencyWarning",
        "service_name": "checkout-service",
        "severity": "warning",
        "summary": "p99 850ms",
    }
    payload.update(overrides)
    return AlertIngestionService.process_direct_request(DirectAlertIngestRequest(**payload))


def log_tool():
    def _collect(alert):
        return ToolResult(
            tool="log_collector",
            ok=True,
            summary="12 sanitized log lines",
            facts=[
                EvidenceFact(
                    source_type="log",
                    source_id="log:checkout-service:0",
                    snippet="WARN slow query duration=850ms",
                )
            ],
        )

    return _collect


def broken_tool():
    def _collect(alert):
        return ToolResult.failure("github_inspector", "GITHUB_TOKEN not configured")

    return _collect


class ScriptedClient:
    """Returns queued responses and records every prompt it was given."""

    provider = "fake"
    model = "fake-1"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, system_prompt, user_prompt, *, json_mode=True):
        self.calls.append({"system": system_prompt, "user": user_prompt})
        if isinstance(self.responses[0], Exception):
            raise self.responses.pop(0)
        return json.dumps(self.responses.pop(0))


def factory_for(client):
    return lambda: client


def test_swarm_happy_path_uses_tool_evidence_and_two_llm_calls():
    client = ScriptedClient([COMMANDER_OK, VERIFIER_SUPPORTED])
    result = run_swarm(
        make_alert(),
        tools=[log_tool(), broken_tool()],
        client_factory=factory_for(client),
    )

    assert result.degraded is False
    assert len(client.calls) == 2  # commander + verifier
    assert MAX_LLM_CALLS == 3
    assert result.provider == "fake"

    # Evidence bundle: alert facts first, then indexed tool facts.
    assert [item.index for item in result.evidence] == [0, 1]
    assert result.evidence[1].source_type == "log"

    # The verifier's lower adjusted confidence wins.
    assert result.draft.confidence_score == 0.55
    assert result.draft.evidence_refs == [1]

    # Tool failure is reported as an explicit non-claim.
    assert any("github_inspector" in unknown for unknown in result.draft.unknowns)

    # Prompts show the specialist summary and the indexed bundle.
    first = client.calls[0]["user"]
    assert "log_collector" in first
    assert "[1] (log)" in first
    assert "Unavailable evidence" in first


def test_swarm_revises_once_when_verifier_rejects():
    client = ScriptedClient([COMMANDER_OK, VERIFIER_REJECTS, COMMANDER_OK])
    result = run_swarm(
        make_alert(),
        tools=[log_tool()],
        client_factory=factory_for(client),
    )

    assert result.degraded is False
    assert len(client.calls) == 3  # cost bound: never a 4th call
    assert any("Verifier challenged" in unknown for unknown in result.draft.unknowns)
    # drop_refs from the rejection still applies after revision
    assert result.draft.evidence_refs == []
    assert result.draft.confidence_score == 0.3


def test_swarm_drops_refs_the_verifier_flags():
    commander = dict(COMMANDER_OK, evidence_refs=[1])
    client = ScriptedClient(
        [
            commander,
            {"supported": True, "critique": "ref 1 unsupported", "drop_refs": [1], "adjusted_confidence": 0.9},
        ]
    )
    result = run_swarm(
        make_alert(),
        tools=[log_tool()],
        client_factory=factory_for(client),
    )
    assert result.draft.evidence_refs == []
    assert result.draft.confidence_score == 0.9


def test_swarm_degrades_never_raises_when_provider_fails():
    client = ScriptedClient([LLMError("ollama unreachable")])
    result = run_swarm(
        make_alert(),
        tools=[log_tool()],
        client_factory=factory_for(client),
    )

    assert result.degraded is True
    assert result.provider is None
    assert result.draft.confidence_score == 0.25
    assert "unavailable" in result.draft.root_cause_summary
    # degraded path falls back to alert evidence only, citations still exist
    assert result.evidence[0].source_id.startswith("alert:")


def test_swarm_default_tools_all_degrade_offline_without_crashing(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "")
    monkeypatch.setattr(settings, "GITHUB_REPO", "")
    client = ScriptedClient([COMMANDER_OK, VERIFIER_SUPPORTED])

    result = run_swarm(make_alert(), client_factory=factory_for(client))

    assert result.degraded is False
    # at least github + runbook gaps are surfaced as explicit non-claims
    gaps = [unknown for unknown in result.draft.unknowns if unknown.startswith("Tool gap:")]
    assert any("github_inspector" in gap for gap in gaps)
    assert any("runbook_store" in gap for gap in gaps)

