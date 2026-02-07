from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate, IncidentResponse, AnalysisRequest
from app.crew.crew import OpsCrew
from app.rag.vector_db import VectorDBService

router = APIRouter()

def run_analysis_task(incident_id: int, logs: str, db: Session):
    # This function would ideally run in a separate worker (Celery/RQ)
    # For MVP, we run it in background task or directly (blocking for now to be simple)
    # Re-creating session for background task safety if needed, 
    # but here we'll just run it synchronously for demonstration or use the passed session carefuly.
    
    # Actually, CrewAI might take time. Let's run it synchronously for the MVP 
    # to return the result immediately to the user, or we can update the DB later.
    # Given the request "return the analysis result", we should wait.
    pass 

from app.core.cache import cache
import hashlib
import json

@router.post("/analyze", response_model=IncidentResponse)
def analyze_logs(request: AnalysisRequest, db: Session = Depends(get_db)):
    """
    Analyze provided logs, detect anomalies, and generate an incident report.
    """
    # Check Cache
    cache_key = f"analysis:{hashlib.md5(request.logs.encode()).hexdigest()}"
    cached_result = cache.get(cache_key)
    if cached_result:
        # If we have a cached incident ID or full result, we could return it.
        # But we need an Incident record.
        # Let's assume cached_result contains the analysis string.
        # For full API caching, we might want to return the whole Response.
        # For simplicity in this phase, let's just cache the HEAVY PART: the CrewAI run.
        pass

    # 1. Create Incident Record
    incident = Incident(
        title="Automated Analysis", 
        description="Incident created from log analysis request",
        status="Analyzing",
        severity="Medium" # Default, will be updated
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    
    # 2. Trigger CrewAI
    # Check cache for analysis result (The heavy part)
    cache_key = f"crew_result:{hashlib.md5(request.logs.encode()).hexdigest()}"
    analysis_result = cache.get(cache_key)
    
    if not analysis_result:
        # Initialize Crew with DB session for RAG
        crew = OpsCrew(incident_id=str(incident.id), logs_content=request.logs, db_session=db)
        result = crew.run()
        analysis_result = str(result)
        # Cache the result for 24 hours
        cache.set(cache_key, analysis_result, ttl=86400)
    
    # 3. Parse and Update Incident
    # Note: parsing the raw string result from CrewAI into structured fields 
    # is a bit tricky without structured output. 
    # For now, we'll store the entire result in the 'root_cause' or a description field, 
    # or ideally we'd have the Crew return a JSON.
    
    # Assuming result is the final report.
    incident.root_cause = analysis_result # storing full report here for now
    incident.status = "Analyzed"
    
    # Generate embedding for future retrieval
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
    """
    List past incidents.
    """
    incidents = db.query(Incident).order_by(Incident.created_at.desc()).offset(skip).limit(limit).all()
    return incidents
