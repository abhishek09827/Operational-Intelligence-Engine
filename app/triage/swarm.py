"""Multi-agent swarm (Milestone 3): typed LangGraph orchestration.

    ┌─────────────────┐  deterministic tool fan-out (no LLM)
    │ Telemetry Agent │  ─┐
    │ Deployment Agent│  ─┼─► indexed evidence bundle
    │ Runbook Agent   │  ─┘
    └────────┬────────┘
             ▼
    ┌─────────────────┐   LLM call 1: synthesize grounded draft
    │IncidentCommander│ ─────────────────────────────────┐
    └─────────────────┘                                  ▼
                                              ┌──────────────────────┐
    ┌──────────────────┐   LLM call 2:      │ Adversarial Verifier │
    │ finalize / revise│ ◄── challenge       │ (supports / rejects) │
    └──────────────────┘                     └──────────────────────┘
             │  revision (LLM call 3, at most once)
             ▼
    IncidentTriageResponse with citations mapped from evidence indexes

Cost bound: at most **3 LLM calls** per swarm triage (1 synthesis + 1 verify +
at most 1 revision). Re-verification after a revision is deliberately skipped so
a local model cannot spiral.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict

from app.llm.client import LLMError, get_chat_client
from app.llm.json_utils import extract_json_object
from app.schemas.v2.alert import SanitizedAlertContext
from app.tools.base import EvidenceFact, ToolResult
from app.triage.evidence import EvidenceItem, build_evidence
from app.triage.fast_path import FastPathDraft, FastPathError, FastPathResult, degraded_draft

logger = logging.getLogger(__name__)

TOOL_TIMEOUT_LABELS = "collect_evidence"

MAX_LLM_CALLS = 3

COMMANDER_SYSTEM = (
    "You are the Incident Commander in a multi-agent SRE triage swarm. Specialist "
    "agents have already fetched evidence (logs, deployments, runbooks); you synthesize "
    "it into one grounded analysis. Use ONLY the numbered EVIDENCE bundle. Never invent "
    "log lines, commits, or runbook steps. If a specialist tool reported an error, state "
    "that gap in `unknowns` instead of filling it. Respond with a single JSON object."
)

COMMANDER_USER = """\
ALERT
name: {alertname}
service: {service_name}
severity: {severity}
environment: {environment}
window: {window_start} -> {window_end}

SPECIALIST FINDINGS
{tool_summaries}

EVIDENCE
{evidence}

Return exactly this JSON shape:
{{
  "root_cause_summary": "<1-2 sentences, evidence-grounded>",
  "confidence_score": <float 0.0-1.0>,
  "remediation_steps": ["<ordered action>", "..."],
  "evidence_refs": [<indexes from EVIDENCE you relied on>],
  "unknowns": ["<gaps, including any specialist tool errors>"]
}}
"""

VERIFIER_SYSTEM = (
    "You are the Adversarial Verifier (Challenger). Your job is to DISPROVE the "
    "Commander's draft: check every claim against the numbered EVIDENCE bundle, flag any "
    "reference that does not support the claim, and lower the confidence when the "
    "evidence is thin. Be strict but do not reject a draft that is honestly caveated. "
    "Respond with a single JSON object."
)

VERIFIER_USER = """\
EVIDENCE
{evidence}

COMMANDER DRAFT
{draft}

Return exactly this JSON shape:
{{
  "supported": <true|false>,
  "critique": "<what is unsupported or missing>",
  "drop_refs": [<evidence indexes that do NOT support the draft>],
  "adjusted_confidence": <float 0.0-1.0>
}}
"""

REVISE_SYSTEM = (
    "You are the Incident Commander receiving review feedback. Correct the draft using "
    "ONLY the numbered EVIDENCE bundle and the Verifier's critique. Respond with a "
    "single JSON object of the same shape as before."
)

REVISE_USER = """\
EVIDENCE
{evidence}

PREVIOUS DRAFT
{draft}

VERIFIER CRITIQUE
{critique}

Return exactly this JSON shape:
{{
  "root_cause_summary": "<1-2 sentences, evidence-grounded>",
  "confidence_score": <float 0.0-1.0>,
  "remediation_steps": ["<ordered action>", "..."],
  "evidence_refs": [<indexes from EVIDENCE>],
  "unknowns": ["<gaps>"]
}}
"""


@dataclass
class SwarmTools:
    """Injectable tool set so tests can run the graph with no I/O."""

    collectors: List[Callable[[SanitizedAlertContext], ToolResult]] = field(default_factory=list)


def default_tools(db_session: Any = None) -> List[Callable[[SanitizedAlertContext], ToolResult]]:
    """The three Milestone-2 tools, all safe to call offline (they degrade)."""
    from app.tools.github_inspector import DeploymentInspector
    from app.tools.log_collector import LogCollector
    from app.tools.runbook_store import RunbookStore

    inspector = DeploymentInspector()
    collector = LogCollector()
    store = RunbookStore(db_session=db_session)

    return [collector.collect, inspector.inspect, store.search]


def index_facts(basis: List[EvidenceItem], facts: List[EvidenceFact]) -> List[EvidenceItem]:
    """Append tool facts to the alert evidence with continuing indexes."""
    next_index = len(basis)
    indexed = list(basis)
    for fact in facts:
        indexed.append(
            EvidenceItem(
                index=next_index,
                source_type=fact.source_type,
                source_id=fact.source_id,
                snippet=fact.snippet,
            )
        )
        next_index += 1
    return indexed


class SwarmState(TypedDict, total=False):
    """Typed graph state — the whole point of using LangGraph over CrewAI."""

    alert: SanitizedAlertContext
    tools: List[Callable[[SanitizedAlertContext], ToolResult]]
    client_factory: Optional[Callable[[], Any]]
    evidence: List[EvidenceItem]
    tool_summaries: List[str]
    tool_errors: List[str]
    draft: Dict[str, Any]
    verifier: Dict[str, Any]
    revises: int
    calls: int
    provider: Optional[str]
    model: Optional[str]
    result: Any


def _render_evidence(evidence: List[EvidenceItem]) -> str:
    return "\n\n".join(item.as_prompt_line() for item in evidence)


def _render_tools(state: SwarmState) -> str:
    summaries = state.get("tool_summaries") or ["(no specialist ran)"]
    lines = [f"- {entry}" for entry in summaries]
    errors = state.get("tool_errors") or []
    if errors:
        lines.append(
            "Unavailable evidence (reflect in `unknowns`): " + "; ".join(errors)
        )
    return "\n".join(lines)


def _client(state: SwarmState) -> Any:
    factory = state.get("client_factory")
    return factory() if factory else get_chat_client()


def _complete(state: SwarmState, system: str, user: str) -> Tuple[Dict[str, Any], Any]:
    """One LLM call, counted against the swarm's cost bound."""
    client = _client(state)
    if state.get("calls", 0) >= MAX_LLM_CALLS:
        raise LLMError("swarm LLM call budget exceeded")
    raw = client.complete(system, user, json_mode=True)
    payload = extract_json_object(raw)
    if payload is None:
        raise FastPathError("swarm model response contained no JSON object")
    return payload, client


def node_collect_evidence(state: SwarmState) -> Dict[str, Any]:
    """Telemetry + Deployment + Runbook agents: pure tool fan-out, no LLM."""
    alert = state["alert"]
    facts: List[EvidenceFact] = []
    summaries: List[str] = []
    errors: List[str] = []

    for tool in state.get("tools") or []:
        try:
            result = tool(alert)
        except Exception as exc:  # defensive: tools promise not to raise
            summaries.append(f"- {getattr(tool, '__name__', 'tool')} FAILED: {exc}")
            errors.append(f"{getattr(tool, '__name__', 'tool')}: {exc}")
            continue
        if result.ok:
            summaries.append(f"- {result.tool}: {result.summary}")
            facts.extend(result.facts)
        else:
            summaries.append(f"- {result.tool}: unavailable ({result.error})")
            errors.append(f"{result.tool}: {result.error}")

    return {
        "evidence": index_facts(build_evidence(alert), facts),
        "tool_summaries": summaries,
        "tool_errors": errors,
        "revises": 0,
        "calls": 0,
    }


def node_incident_commander(state: SwarmState) -> Dict[str, Any]:
    """LLM call 1: synthesize a grounded draft from the evidence bundle."""
    alert = state["alert"]
    user = COMMANDER_USER.format(
        alertname=alert.alertname,
        service_name=alert.service_name,
        severity=alert.severity,
        environment=alert.environment,
        window_start=alert.time_window_start.isoformat(),
        window_end=alert.time_window_end.isoformat(),
        tool_summaries=_render_tools(state),
        evidence=_render_evidence(state["evidence"]),
    )
    payload, client = _complete(state, COMMANDER_SYSTEM, user)
    return {
        "draft": payload,
        "calls": state.get("calls", 0) + 1,
        "provider": getattr(client, "provider", None),
        "model": getattr(client, "model", None),
    }


def node_adversarial_verifier(state: SwarmState) -> Dict[str, Any]:
    """LLM call 2: try to disprove the Commander's draft."""
    user = VERIFIER_USER.format(
        evidence=_render_evidence(state["evidence"]),
        draft=json.dumps(state.get("draft") or {}, ensure_ascii=False, indent=2),
    )
    payload, client = _complete(state, VERIFIER_SYSTEM, user)

    # Deterministic guards: the verifier cannot invent refs either.
    drop_refs = payload.get("drop_refs") or []
    payload["drop_refs"] = [ref for ref in drop_refs if isinstance(ref, int)]
    payload["supported"] = bool(payload.get("supported", False))
    adjusted = payload.get("adjusted_confidence")
    if isinstance(adjusted, (int, float)):
        payload["adjusted_confidence"] = min(max(float(adjusted), 0.0), 1.0)

    return {
        "verifier": payload,
        "calls": state.get("calls", 0) + 1,
        "provider": getattr(client, "provider", None),
        "model": getattr(client, "model", None),
    }


def route_after_verify(state: SwarmState) -> str:
    """One revision max: revise -> finalize (no re-verify, cost bound)."""
    verifier = state.get("verifier") or {}
    if not verifier.get("supported", True) and state.get("revises", 0) < 1:
        return "revise"
    return "finalize"


def node_revise(state: SwarmState) -> Dict[str, Any]:
    """LLM call 3 (at most once): correct the draft using the critique."""
    verifier = state.get("verifier") or {}
    user = REVISE_USER.format(
        evidence=_render_evidence(state["evidence"]),
        draft=json.dumps(state.get("draft") or {}, ensure_ascii=False, indent=2),
        critique=verifier.get("critique") or "(none)",
    )
    payload, client = _complete(state, REVISE_SYSTEM, user)
    return {
        "draft": payload,
        "revises": state.get("revises", 0) + 1,
        "calls": state.get("calls", 0) + 1,
        "provider": getattr(client, "provider", None),
        "model": getattr(client, "model", None),
    }


def _as_ints(values: Any) -> List[int]:
    """Accept ints (and numeric strings) from model output; ignore garbage."""
    out: List[int] = []
    for value in values or []:
        try:
            out.append(int(value))
        except (TypeError, ValueError):
            continue
    return out


def node_finalize(state: SwarmState) -> Dict[str, Any]:
    """Apply all deterministic guards and emit the response-ready result."""
    draft = state.get("draft") or {}
    verifier = state.get("verifier") or {}

    refs = _as_ints(draft.get("evidence_refs") or [])
    dropped = set(_as_ints(verifier.get("drop_refs") or []))
    refs = [ref for ref in refs if ref not in dropped]

    try:
        confidence = float(draft.get("confidence_score", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    adjusted = verifier.get("adjusted_confidence")
    if isinstance(adjusted, (int, float)):
        confidence = float(adjusted)
    confidence = round(min(max(confidence, 0.0), 1.0), 2)

    unknowns = [str(item) for item in (draft.get("unknowns") or [])]
    unknowns += [f"Tool gap: {entry}" for entry in (state.get("tool_errors") or [])]
    if not verifier.get("supported", True):
        unknowns.append(
            "Verifier challenged the draft: " + str(verifier.get("critique") or "")[:300]
        )

    steps = [str(step) for step in (draft.get("remediation_steps") or [])]
    if not steps:
        alert = state["alert"]
        steps = [
            f"Inspect {alert.service_name} telemetry for "
            f"[{alert.time_window_start.isoformat()}, {alert.time_window_end.isoformat()}]."
        ]

    final_draft = FastPathDraft(
        root_cause_summary=str(
            draft.get("root_cause_summary")
            or "No root cause could be grounded in the fetched evidence."
        ),
        confidence_score=confidence,
        remediation_steps=steps,
        evidence_refs=refs,
        unknowns=unknowns,
    )
    return {
        "result": FastPathResult(
            draft=final_draft,
            evidence=state["evidence"],
            provider=state.get("provider"),
            model=state.get("model"),
            degraded=False,
        )
    }


def build_swarm_graph():
    """Compile the LangGraph state machine (typed state + conditional edges)."""
    from langgraph.graph import END, START, StateGraph

    graph: Any = StateGraph(SwarmState)
    graph.add_node("collect_evidence", node_collect_evidence)
    graph.add_node("incident_commander", node_incident_commander)
    graph.add_node("adversarial_verifier", node_adversarial_verifier)
    graph.add_node("revise", node_revise)
    graph.add_node("finalize", node_finalize)

    graph.add_edge(START, "collect_evidence")
    graph.add_edge("collect_evidence", "incident_commander")
    graph.add_edge("incident_commander", "adversarial_verifier")
    graph.add_conditional_edges(
        "adversarial_verifier",
        route_after_verify,
        {"revise": "revise", "finalize": "finalize"},
    )
    graph.add_edge("revise", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


_GRAPH: Any = None


def _graph() -> Any:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_swarm_graph()
    return _GRAPH


def run_swarm(
    alert: SanitizedAlertContext,
    db_session: Any = None,
    tools: Optional[List[Callable[[SanitizedAlertContext], ToolResult]]] = None,
    client_factory: Optional[Callable[[], Any]] = None,
) -> FastPathResult:
    """Execute the swarm for one alert.

    Never raises: an unavailable provider or an internal graph error degrades to
    the deterministic fallback, keeping the alert webhook at HTTP 200.
    """
    state: Dict[str, Any] = {
        "alert": alert,
        "tools": tools if tools is not None else default_tools(db_session),
        "client_factory": client_factory,
    }
    try:
        final = _graph().invoke(state)
        result = final.get("result") if isinstance(final, dict) else None
        if result is None:
            raise FastPathError("swarm graph produced no result")
        return result
    except (LLMError, FastPathError) as exc:
        logger.warning("swarm degraded for alert=%s: %s", alert.alertname, exc)
        reason = "swarm synthesis unavailable"
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("swarm crashed for alert=%s", alert.alertname)
        reason = "swarm internal failure"

    return FastPathResult(
        draft=degraded_draft(alert, reason),
        evidence=build_evidence(alert),
        provider=None,
        model=None,
        degraded=True,
    )


