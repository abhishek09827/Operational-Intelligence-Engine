"""Triage engines and their shared, deterministic evidence layer."""
from app.triage.evidence import EvidenceItem, build_evidence
from app.triage.fast_path import (
    FastPathDraft,
    FastPathError,
    FastPathResult,
    FastPathTriage,
    citations_from_refs,
    degraded_draft,
    run_fast_path,
)
from app.triage.pipeline import TIER_FAST_PATH, TIER_SWARM, triage_alert
from app.triage.swarm import SwarmState, build_swarm_graph, run_swarm

__all__ = [
    "EvidenceItem",
    "build_evidence",
    "FastPathDraft",
    "FastPathError",
    "FastPathResult",
    "FastPathTriage",
    "citations_from_refs",
    "degraded_draft",
    "run_fast_path",
    "TIER_FAST_PATH",
    "TIER_SWARM",
    "triage_alert",
    "SwarmState",
    "build_swarm_graph",
    "run_swarm",
]
