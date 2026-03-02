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
import io
import sys

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
        severity="Medium",
        root_cause = "",
        suggested_fix = "",
        confidence_score = None
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    
    # 2. Trigger CrewAI
    # Check cache for analysis result (The heavy part)
    cache_key = f"crew_result:{hashlib.md5(request.logs.encode()).hexdigest()}"
    analysis_result = cache.get(cache_key)
    
    # Capture crew output
    crew_output = []
    
    if not analysis_result:
        # Initialize Crew with DB session for RAG
        crew = OpsCrew(incident_id=str(incident.id), logs_content=request.logs, db_session=db)
        
        # Capture stdout to display thinking process
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()
        
        try:
            result = crew.run()
            # Get the captured output
            captured_text = captured_output.getvalue()
        finally:
            sys.stdout = old_stdout
        
        # Parse captured output into structured logs
        for line in captured_text.split('\n'):
            if line.strip():
                crew_output.append(line)
        
        analysis_result = str(result)
        # Cache the result for 24 hours
        cache.set(cache_key, analysis_result, ttl=86400)
    else:
        # If cached, we can still provide a "thinking" placeholder
        crew_output = ["🤖 Loading cached analysis..."]
    
    # 3. Parse and Update Incident
    # Parse the JSON analysis result from CrewAI
    try:
        # Clean the result - remove markdown backticks and extra text
        cleaned_result = analysis_result.strip()
        
        # Remove leading ```json or ``` if present
        if cleaned_result.startswith('```'):
            # Remove everything from first ``` to end
            parts = cleaned_result.split('```')
            if len(parts) > 1:
                cleaned_result = parts[1].strip()
        
        # Remove leading "json" on its own line (AI output format)
        lines = cleaned_result.split('\n')
        if lines and lines[0].strip() == 'json':
            cleaned_result = '\n'.join(lines[1:]).strip()
        
        # Remove trailing ``` or other text like ```analysis_result
        if cleaned_result.endswith('```'):
            parts = cleaned_result.rsplit('```', 1)
            if len(parts) > 1:
                cleaned_result = parts[0].strip()
        
        # Try to parse as JSON
        if cleaned_result.startswith('{'):
            analysis_data = json.loads(cleaned_result)
            # Extract severity from analysis
            if 'analysis' in analysis_data and len(analysis_data['analysis']) > 0:
                # Get severity from first analysis entry (not all)
                severity = analysis_data['analysis'][0].get('severity', 'MEDIUM')
                incident.severity = severity
                incident.root_cause = analysis_data['analysis'][0].get('root_cause', '')
                # Convert confidence_score to float if available, None otherwise
                confidence_val = analysis_data['analysis'][0].get('confidence_score')
                incident.confidence_score = float(confidence_val) if confidence_val is not None else None
                incident.suggested_fix = analysis_data['analysis'][0].get('prevention_strategy', '')
                
                # Format as visually appealing markdown for frontend
                def format_analysis_as_markdown(analysis_dict):
                    """Convert analysis JSON to formatted markdown for frontend"""
                    md = f"""## 🔴 Critical Incident Detected

### Summary
- **Category**: `{analysis_dict.get('category', 'N/A')}`
- **Severity**: {severity}
- **Log ID**: `{analysis_dict.get('log_id', 'N/A')}`
- **Confidence**: {analysis_dict.get('confidence_score', 0.0)}"""

                    if analysis_dict.get('root_cause'):
                        md += f"\n\n### 🔍 Root Cause\n\n{analysis_dict.get('root_cause')}"

                    if analysis_dict.get('detailed_explanation'):
                        md += f"\n\n### 📝 Detailed Explanation\n\n{analysis_dict.get('detailed_explanation')}"

                    if analysis_dict.get('prevention_strategy'):
                        md += f"\n\n### 🛡️ Prevention Strategy\n\n{analysis_dict.get('prevention_strategy')}"

                    if analysis_dict.get('affected_services'):
                        services = ", ".join(analysis_dict.get('affected_services', []))
                        md += f"\n\n### ⚡ Affected Services\n\n{services}"

                    if analysis_dict.get('suggested_monitoring'):
                        metrics = "\n".join(f"- {m}" for m in analysis_dict.get('suggested_monitoring', []))
                        md += f"\n\n### 📊 Suggested Monitoring\n\n{metrics}"

                    return md

                incident.description = format_analysis_as_markdown(analysis_data['analysis'][0])
            else:
                incident.root_cause = cleaned_result
        else:
            # If not JSON, store as-is
            incident.root_cause = cleaned_result
            
    except json.JSONDecodeError:
        # If not valid JSON, store cleaned result
        incident.root_cause = cleaned_result if 'cleaned_result' in locals() else analysis_result
    
    incident.status = "Analyzed"
    incident.thinking_process = "\n".join(crew_output)
    
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