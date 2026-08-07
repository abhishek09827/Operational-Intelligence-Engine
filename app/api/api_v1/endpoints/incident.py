from fastapi import APIRouter, Depends, HTTPException
from typing import List
import hashlib

from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate, IncidentResponse, AnalysisRequest
from app.crew.crew import OpsCrew
from app.rag.vector_db import VectorDBService
from app.core.cache import cache

router = APIRouter()

# Keyword -> severity mapping used by the deterministic severity heuristic.
SEVERITY_KEYWORDS = {
    "Critical": ["fatal", "critical", "severe", "panic", "crash", "outage", "data loss"],
    "High": ["error", "fail", "exception", "timeout", "down", "refused"],
    "Medium": ["warn", "warning", "retry", "degraded", "slow"],
}


def infer_severity(logs: str) -> str:
    """Determine a severity level from keywords in the raw logs (heuristic).

    This is a cheap, deterministic fallback used to populate the `severity`
    field until the Crew returns structured JSON with an explicit severity.
    """
    lower = logs.lower()
    for severity, keywords in SEVERITY_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            return severity
    return "Low"


def infer_confidence(analysis_result: str) -> float:
    """A deterministic MVP confidence heuristic (0.0 - 0.95).

    The Crew currently returns a free-form markdown report, so we approximate
    confidence from proxy signals instead of a real model probability. This is
    intentionally never 1.0 and is bounded below a full-confidence ceiling.
    """
    text = analysis_result.lower()
    score = 0.0
    if any(k in text for k in ["root cause", "cause", "because", "why"]):
        score += 0.4
    if any(k in text for k in ["fix", "solution", "recommend", "change", "restart", "update", "rollback"]):
        score += 0.3
    if len(analysis_result.strip()) > 200:
        score += 0.2
    return round(min(score, 0.95), 2)


@router.post("/analyze", response_model=IncidentResponse)
def analyze_logs(request: AnalysisRequest, db: Session = Depends(get_db)):
    """Analyze provided logs, detect anomalies, and generate an incident report."""

    # 1. Create Incident Record (severity inferred from the raw logs)
    incident = Incident(
        title="Automated Analysis",
        description="Incident created from log analysis request",
        status="Analyzing",
        severity=infer_severity(request.logs),
        confidence_score=0.0,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    # 2. Trigger CrewAI (the heavy part is cached by log-hash for 24h)
    cache_key = f"crew_result:{hashlib.md5(request.logs.encode()).hexdigest()}"
    analysis_result = cache.get(cache_key)

    if not analysis_result:
        crew = OpsCrew(incident_id=str(incident.id), logs_content=request.logs, db_session=db)
        result = crew.run()
        analysis_result = str(result)
        cache.set(cache_key, analysis_result, ttl=86400)

    # 3. Persist the analysis results.
    # Note: the Crew returns a free-form markdown report today, so the full
    # report is stored in `root_cause` and `suggested_fix` is left unset until
    # the Crew is upgraded to structured (JSON) output.
    incident.root_cause = analysis_result
    incident.status = "Analyzed"
    incident.severity = infer_severity(request.logs)
    if incident.confidence_score is None or incident.confidence_score == 0.0:
        incident.confidence_score = infer_confidence(analysis_result)

    # 4. Generate embedding for future retrieval (RAG)
    vector_service = VectorDBService(db)
    vector_service.store_incident_with_embedding(incident)

    db.commit()
    db.refresh(incident)

    return incident


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.get("/", response_model=List[IncidentResponse])
def list_incidents(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """List past incidents."""
    incidents = db.query(Incident).order_by(Incident.created_at.desc()).offset(skip).limit(limit).all()
    return incidents

