from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from typing import List, AsyncGenerator
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate, IncidentResponse, AnalysisRequest
from app.crew.crew import OpsCrew
from app.rag.vector_db import VectorDBService
from app.generators.fake_log_generator import (
    fake_log_generator,
    generate_realistic_stream,
    generate_spiked_stream
)
import asyncio
import json
import random
import io
import sys
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib
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
import re

def extract_json_from_text(text: str) -> str:
    """Extract JSON string from a larger text block by finding outer braces/brackets."""
    text = str(text).strip()
    
    start_obj = text.find('{')
    start_arr = text.find('[')
    
    if start_obj == -1 and start_arr == -1:
        return text
        
    start_idx = start_obj if start_obj != -1 and (start_arr == -1 or start_obj < start_arr) else start_arr
    end_idx = text.rfind('}') if text[start_idx] == '{' else text.rfind(']')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return text[start_idx:end_idx+1]
    
    return text

def format_analysis_as_markdown(analysis_data: dict) -> str:
    """Convert analysis JSON to formatted markdown for frontend"""
    analysis_list = analysis_data.get('analysis', [])
    if not analysis_list:
        return "No analysis available"
    
    # Get first analysis entry
    analysis = analysis_list[0]
    
    severity = analysis.get('severity', 'MEDIUM')
    category = analysis.get('category', 'N/A')
    
    md = f"""## 🔍 Incident Analysis

### Summary
- **Category**: `{category}`
- **Severity**: {severity}
- **Log ID**: `{analysis.get('log_id', 'N/A')}`
- **Confidence**: {analysis.get('confidence_score', 0.0):.1%}"""

    if analysis.get('root_cause'):
        md += f"\n\n### 🔥 Root Cause\n\n{analysis['root_cause']}"

    if analysis.get('detailed_explanation'):
        md += f"\n\n### 📖 Detailed Explanation\n\n{analysis['detailed_explanation']}"

    if analysis.get('primary_cause'):
        md += f"\n\n### ⚙️ Primary Cause\n\n{analysis['primary_cause']}"

    if analysis.get('secondary_symptoms'):
        symptoms = "\n".join(f"- {s}" for s in analysis['secondary_symptoms'][:3])
        md += f"\n\n### ⛓️ Secondary Symptoms\n\n{symptoms}"

    if analysis.get('user_impact'):
        md += f"\n\n### 👥 User Impact\n\n{analysis['user_impact']}"

    if analysis.get('orchestration_behavior'):
        md += f"\n\n### 🔄 System Behavior\n\n{analysis['orchestration_behavior']}"

    if analysis.get('recommended_fix'):
        md += f"\n\n### 🛠️ Recommended Fix\n\n{analysis['recommended_fix']}"

    if analysis.get('prevention_strategy'):
        md += f"\n\n### 🛡️ Prevention Strategy\n\n{analysis['prevention_strategy']}"

    if analysis.get('affected_services'):
        services = ", ".join(analysis['affected_services'])
        md += f"\n\n### ⚡ Affected Services\n\n{services}"

    if analysis.get('suggested_monitoring'):
        metrics = "\n".join(f"- {m}" for m in analysis['suggested_monitoring'])
        md += f"\n\n### 📊 Suggested Monitoring\n\n{metrics}"

    return md

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
    validation_output = None
    report_output = None
    
    if not analysis_result:
        # Initialize Crew with DB session for RAG
        crew = OpsCrew(incident_id=str(incident.id), logs_content=request.logs, db_session=db)
        
        # Capture stdout to display thinking process
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()
        
        try:
            result, task_outputs = crew.run()
            # Get the captured output
            captured_text = captured_output.getvalue()
        finally:
            sys.stdout = old_stdout
        
        # Parse captured output into structured logs
        for line in captured_text.split('\n'):
            if line.strip():
                crew_output.append(line)
        
        # Extract task outputs (validation_output is index 1, report_output is index 2)
        if task_outputs:
            if len(task_outputs) > 1:
                validation_output = task_outputs[1]
                if hasattr(validation_output, 'raw'):
                    validation_output = validation_output.raw
            if len(task_outputs) > 2:
                report_output = task_outputs[2]
                if hasattr(report_output, 'raw'):
                    report_output = report_output.raw
        
        analysis_result = str(validation_output) if validation_output else str(result)
        # Cache the result for 24 hours (as string for flexibility)
        cache.set(cache_key, analysis_result, ttl=86400)
    else:
        # If cached, check if it's a dict or string
        if isinstance(analysis_result, dict):
            # Already parsed JSON, convert back to string
            analysis_result = json.dumps(analysis_result)
        # If it's already a string, use it as-is
        crew_output = ["🤖 Loading cached analysis..."]
    
    # 3. Parse and Update Incident
    # Parse the JSON analysis result from CrewAI
    try:
        # Clean the result - extract JSON
        cleaned_result = extract_json_from_text(analysis_result)
        
        # Parse as JSON
        analysis_data = json.loads(cleaned_result)
        
        # Check if it's wrapped in 'analysis' key
        if 'analysis' in analysis_data and isinstance(analysis_data['analysis'], list):
            analysis_list = analysis_data['analysis']
        # Or if it's directly an array
        elif isinstance(analysis_data, list):
            analysis_list = analysis_data
        else:
            # Assume it's a single object
            analysis_list = [analysis_data]
        
        # Extract severity and root_cause from first analysis entry
        if len(analysis_list) > 0:
            # Safely handle potential nested 'analysis' keys or case mismatches
            analysis_dict = analysis_list[0] if isinstance(analysis_list[0], dict) else {}
            
            # CrewAI might output severity, severity_level, etc.
            severity = analysis_dict.get('severity') or analysis_dict.get('Severity') or analysis_dict.get('level') or 'Medium'
            incident.severity = severity
            
            incident.root_cause = str(report_output) if report_output else analysis_dict.get('root_cause', '')
            
            confidence_score = analysis_dict.get('confidence_score') or analysis_dict.get('confidence')
            if confidence_score is not None:
                try:
                    incident.confidence_score = float(confidence_score)
                except ValueError:
                    incident.confidence_score = None
            def format_analysis_as_markdown_local(analysis_dict):
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

            incident.description = format_analysis_as_markdown_local(analysis_list[0])
        else:
            incident.root_cause = cleaned_result
            
    except json.JSONDecodeError:
        # If not valid JSON, store cleaned result
        incident.root_cause = cleaned_result if 'cleaned_result' in locals() else analysis_result
    
    incident.status = "Analyzed"
    print(str(validation_output) + "val123")
    print(str(report_output) + "rep123")
    incident.thinking_process = "\n".join(crew_output)
    # Generate embedding for future retrieval
    vector_service = VectorDBService(db)
    vector_service.store_incident_with_embedding(incident)
    
    db.commit()
    db.refresh(incident)
    
    return incident


@router.get("/fake-log-stream")
async def get_fake_log_stream(
    interval: float = Query(default=1.0, description="Seconds between logs"),
    num_logs: int = Query(default=100, description="Number of logs to stream"),
    generator_type: str = Query(default="realistic", description="Type of generator")
) -> StreamingResponse:
    """
    Stream fake logs without analysis (for testing frontend).
    
    Args:
        interval: Seconds between logs
        num_logs: Number of logs to stream
        generator_type: Type of generator
        
    Returns:
        StreamingResponse with raw log data
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events with fake logs"""
        
        if generator_type == "spiked":
            log_generator = generate_spiked_stream(duration=num_logs/5)
        else:
            log_generator = fake_log_generator(
                interval=interval,
                num_logs=num_logs,
                start_immediately=True
            )
        
        log_count = 0
        for log in log_generator:
            log_count += 1
            payload = {
                "type": "log",
                "log_count": log_count,
                "log": log
            }

            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(interval)
        
        payload = {
            "type": "complete",
            "total_logs": log_count
        }

        yield f"data: {json.dumps(payload)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.post("/stream-analyze")
async def stream_analyze_logs(
    generator_type: str = Query(default="realistic", description="Type of generator ('realistic', 'spiked', or 'custom')"),
    duration: int = Query(default=60, description="Duration in seconds to stream logs"),
    logs_per_second: int = Query(default=1, description="Number of logs per second"),
    error_rate: float = Query(default=0.05, description="Probability of ERROR/CRITICAL logs"),
    batch_size: int = Query(default=5, description="Number of logs to analyze per CrewAI batch"),
    db: Session = Depends(get_db)
) -> StreamingResponse:
    """
    Stream fake logs and analyze them in real-time using CrewAI/LLM.
    
    Args:
        generator_type: Type of generator ('realistic', 'spiked', or 'custom')
        duration: Duration in seconds to stream logs
        logs_per_second: Number of logs per second
        error_rate: Probability of ERROR/CRITICAL logs
        batch_size: Number of logs to analyze per CrewAI batch (default: 5)
        
    Returns:
        StreamingResponse with real-time analysis updates from CrewAI
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events with logs and CrewAI analysis"""
        log_count = 0
        batch_logs = []
        
        # Select appropriate generator
        if generator_type == "spiked":
            log_generator = generate_spiked_stream(duration=duration)
        elif generator_type == "realistic":
            log_generator = generate_realistic_stream(
                duration=duration,
                logs_per_second=logs_per_second,
                error_rate=error_rate
            )
        else:
            # Custom generator
            log_generator = fake_log_generator(
                interval=1.0/logs_per_second,
                num_logs=duration * logs_per_second,
                error_rate=error_rate
            )
        
        # Stream logs and collect in batches for CrewAI analysis
        for log in log_generator:
            log_count += 1
            batch_logs.append(log)
            
            # Yield the log as it comes
            payload = {
                "type": "log",
                "log_count": log_count,
                "log": log
            }

            yield f"data: {json.dumps(payload)}\n\n"
            
            # Store embedding immediately for this log
            log_entry = Incident(
                title=f"Streamed Log #{log_count}",
                description=f"Log from {log['service_name']}: {log['message']}",
                status="Analyzing",
                severity=log['level'],
                root_cause=f"Streaming log {log_count} from {log['service_name']}",
                confidence_score=0.95
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)
            
            # Store embedding for retrieval
            vector_service = VectorDBService(db)
            vector_service.store_incident_with_embedding(log_entry)
            
            # Check if we have a batch ready for CrewAI analysis
            if len(batch_logs) >= batch_size:
                # Build logs content for CrewAI
                logs_content = "\n\n".join([
                    f"Log #{i+1} [{log['level']}] {log['service_name']}: {log['message']}"
                    for i, log in enumerate(batch_logs)
                ])
                
                # Run CrewAI analysis on the batch
                try:
                    crew = OpsCrew(
                        incident_id=str(log_entry.id),
                        logs_content=logs_content,
                        db_session=db
                    )
                    crew_output = []
                    
                    # Capture crew output
                    old_stdout = sys.stdout
                    captured_output = io.StringIO()
                    sys.stdout = captured_output
                    
                    try:
                        result, task_outputs = crew.run()
                        crew_text = captured_output.getvalue()
                        
                        validation_output = None
                        report_output = None
                        if task_outputs:
                            if len(task_outputs) > 1:
                                validation_output = task_outputs[1]
                                if hasattr(validation_output, 'raw'):
                                    validation_output = validation_output.raw
                            if len(task_outputs) > 2:
                                report_output = task_outputs[2]
                                if hasattr(report_output, 'raw'):
                                    report_output = report_output.raw
                    finally:
                        sys.stdout = old_stdout
                    
                    crew_output.append(crew_text)
                    
                    # Parse CrewAI output (same as /analyze endpoint)
                    raw_result = str(validation_output).strip() if validation_output else str(result).strip()
                    cleaned_result = extract_json_from_text(raw_result)
                    
                    # Clean and parse JSON
                    try:
                        analysis_data = json.loads(cleaned_result)
                        
                        # Check if it's wrapped in 'analysis' key
                        if 'analysis' in analysis_data and isinstance(analysis_data['analysis'], list):
                            analysis_list = analysis_data['analysis']
                        # Or if it's directly an array
                        elif isinstance(analysis_data, list):
                            analysis_list = analysis_data
                        else:
                            # Assume it's a single object
                            analysis_list = [analysis_data]
                        
                        # Extract severity and root_cause from first analysis entry (same as /analyze)
                        if len(analysis_list) > 0:
                            analysis_dict = analysis_list[0] if isinstance(analysis_list[0], dict) else {}
                            
                            severity = analysis_dict.get('severity') or analysis_dict.get('Severity') or analysis_dict.get('level') or incident.severity
                            incident.severity = severity
                            
                            incident.root_cause = str(report_output) if report_output else analysis_dict.get('root_cause', '')
                            
                            confidence_score = analysis_dict.get('confidence_score') or analysis_dict.get('confidence')
                            if confidence_score is not None:
                                try:
                                    incident.confidence_score = float(confidence_score)
                                except ValueError:
                                    pass
                            
                            # Format as visually appealing markdown for frontend (same as /analyze)
                            incident.description = format_analysis_as_markdown(analysis_list[0])
                            
                            incident.status = "Analyzed"
                            incident.thinking_process = "\n".join(crew_output)
                            
                            # Generate embedding for future retrieval (same as /analyze)
                            vector_service = VectorDBService(db)
                            vector_service.store_incident_with_embedding(incident)
                            
                            db.commit()
                            db.refresh(log_entry)
                        
                        # Send analysis update with CrewAI results and formatted description
                        payload = {
                            "type": "analysis_update",
                            "incident_id": log_entry.id,
                            "log_count": log_count,
                            "status": "Analyzed",
                            "severity": log['level'],
                            "description": incident.description,
                            "thinking_process": "\n".join(crew_output),
                        }
                        
                        yield f"data: {json.dumps(payload)}\n\n"
                        
                    except json.JSONDecodeError:
                        # If not valid JSON, store cleaned result (same as /analyze)
                        incident.root_cause = cleaned_result if 'cleaned_result' in locals() else cleaned_result
                        incident.status = "Analyzed (Invalid JSON)"
                        db.commit()
                        db.refresh(log_entry)
                        
                        payload = {
                            "type": "analysis_update",
                            "incident_id": log_entry.id,
                            "log_count": log_count,
                            "status": "Analyzed (Invalid JSON)",
                            "severity": log['level'],
                            "error": "Failed to parse CrewAI output as JSON",
                        }
                        
                        yield f"data: {json.dumps(payload)}\n\n"
                    
                except Exception as e:
                    # Fallback if CrewAI fails
                    payload = {
                        "type": "analysis_update",
                        "incident_id": log_entry.id,
                        "log_count": log_count,
                        "status": "Analyzed (LLM Error)",
                        "severity": log['level'],
                        "error": str(e),
                    }
                    
                    yield f"data: {json.dumps(payload)}\n\n"
                
                # Clear batch and continue
                batch_logs = []
        
        # Process any remaining logs in the last batch
        if batch_logs:
            logs_content = "\n\n".join([
                f"Log #{i+1} [{log['level']}] {log['service_name']}: {log['message']}"
                for i, log in enumerate(batch_logs)
            ])
            
            try:
                crew = OpsCrew(
                    incident_id=str(log_entry.id),
                    logs_content=logs_content,
                    db_session=db
                )
                crew_output = []
                
                old_stdout = sys.stdout
                captured_output = io.StringIO()
                sys.stdout = captured_output
                
                try:
                    result, task_outputs = crew.run()
                    crew_text = captured_output.getvalue()
                    
                    validation_output = None
                    report_output = None
                    if task_outputs:
                        if len(task_outputs) > 1:
                            validation_output = task_outputs[1]
                            if hasattr(validation_output, 'raw'):
                                validation_output = validation_output.raw
                        if len(task_outputs) > 2:
                            report_output = task_outputs[2]
                            if hasattr(report_output, 'raw'):
                                report_output = report_output.raw
                finally:
                    sys.stdout = old_stdout
                
                crew_output.append(crew_text)
                
                # Parse CrewAI output (same as /analyze endpoint)
                raw_result = str(validation_output).strip() if validation_output else str(result).strip()
                cleaned_result = extract_json_from_text(raw_result)
                
                # Clean and parse JSON
                try:
                    analysis_data = json.loads(cleaned_result)
                    
                    # Check if it's wrapped in 'analysis' key
                    if 'analysis' in analysis_data and isinstance(analysis_data['analysis'], list):
                        analysis_list = analysis_data['analysis']
                    # Or if it's directly an array
                    elif isinstance(analysis_data, list):
                        analysis_list = analysis_data
                    else:
                        # Assume it's a single object
                        analysis_list = [analysis_data]
                    
                    # Extract severity and root_cause from first analysis entry (same as /analyze)
                    if len(analysis_list) > 0:
                        analysis_dict = analysis_list[0] if isinstance(analysis_list[0], dict) else {}
                        
                        severity = analysis_dict.get('severity') or analysis_dict.get('Severity') or analysis_dict.get('level') or incident.severity
                        incident.severity = severity
                        
                        incident.root_cause = str(report_output) if report_output else analysis_dict.get('root_cause', '')
                        
                        confidence_score = analysis_dict.get('confidence_score') or analysis_dict.get('confidence')
                        if confidence_score is not None:
                            try:
                                incident.confidence_score = float(confidence_score)
                            except ValueError:
                                pass
                        
                        # Format as visually appealing markdown for frontend (same as /analyze)
                        incident.description = format_analysis_as_markdown(analysis_list[0])
                        
                        incident.status = "Analyzed"
                        incident.thinking_process = "\n".join(crew_output)
                        
                        # Generate embedding for future retrieval (same as /analyze)
                        vector_service = VectorDBService(db)
                        vector_service.store_incident_with_embedding(incident)
                        
                        db.commit()
                        db.refresh(log_entry)
                    
                    # Send analysis update with CrewAI results and formatted description
                    payload = {
                        "type": "analysis_update",
                        "incident_id": log_entry.id,
                        "log_count": log_count,
                        "status": "Analyzed",
                        "severity": batch_logs[0]['level'],
                        "description": incident.description,
                        "thinking_process": "\n".join(crew_output),
                    }
                    
                    yield f"data: {json.dumps(payload)}\n\n"
                    
                except json.JSONDecodeError:
                    # If not valid JSON, store cleaned result (same as /analyze)
                    incident.root_cause = cleaned_result if 'cleaned_result' in locals() else cleaned_result
                    incident.status = "Analyzed (Invalid JSON)"
                    db.commit()
                    db.refresh(log_entry)
                    
                    payload = {
                        "type": "analysis_update",
                        "incident_id": log_entry.id,
                        "log_count": log_count,
                        "status": "Analyzed (Invalid JSON)",
                        "severity": batch_logs[0]['level'],
                        "error": "Failed to parse CrewAI output as JSON",
                    }
                    
                    yield f"data: {json.dumps(payload)}\n\n"
                
            except Exception as e:
                payload = {
                    "type": "analysis_update",
                    "incident_id": log_entry.id,
                    "log_count": log_count,
                    "status": "Analyzed (LLM Error)",
                    "severity": batch_logs[0]['level'],
                    "error": str(e),
                }
                
                yield f"data: {json.dumps(payload)}\n\n"
        
        # Send completion event
        yield "data: " + json.dumps({
            'type': 'complete',
            'total_logs': log_count,
            'message': f'Streaming complete. Processed {log_count} logs with CrewAI analysis.'
        }) + "\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/performance-metrics")
def get_performance_metrics(
    hours: int = Query(default=1, description="Lookback period in hours"),
    db: Session = Depends(get_db)
):
    """
    Get performance metrics for the streaming system.
    
    Args:
        hours: Lookback period in hours (default: 1)
        
    Returns:
        Dictionary with performance metrics
    """
    # Calculate time range
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    # Query incidents created in the time period
    incidents = db.query(Incident).filter(
        Incident.created_at >= start_time
    ).all()
    
    # Calculate metrics
    total_logs = len(incidents)
    
    # Severity distribution
    severity_counts = defaultdict(int)
    severity_rates = {}
    for incident in incidents:
        severity_counts[incident.severity] += 1
    
    # Average processing time (simulated based on creation time difference)
    processing_times = []
    for i in range(1, len(incidents)):
        time_diff = incidents[i].created_at - incidents[i-1].created_at
        processing_times.append(time_diff.total_seconds())
    
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    max_processing_time = max(processing_times) if processing_times else 0
    min_processing_time = min(processing_times) if processing_times else 0
    
    # Category distribution
    category_counts = defaultdict(int)
    for incident in incidents:
        if incident.description:
            # Extract category from description (simplified)
            for category in ["API_ERROR", "DATABASE", "NETWORK", "PAYMENT_FAILURE", "TIMEOUT", "PERFORMANCE"]:
                if category in incident.description:
                    category_counts[category] += 1
                    break
    
    # Service distribution
    service_counts = defaultdict(int)
    for incident in incidents:
        if incident.description:
            for word in incident.description.split():
                if word in ["auth-service", "api-gateway", "payment-service", "database", 
                          "redis-cache", "user-service", "notification-service", 
                          "analytics-service", "log-aggregator"]:
                    service_counts[word] += 1
    
    # Calculate throughput (logs per second)
    throughput = total_logs / hours if hours > 0 else 0
    
    # Calculate error rate
    error_rate = (severity_counts.get("ERROR", 0) + severity_counts.get("CRITICAL", 0)) / total_logs if total_logs > 0 else 0
    
    return {
        "period": {
            "start_time": start_time.isoformat(),
            "end_time": datetime.utcnow().isoformat(),
            "hours": hours
        },
        "throughput": {
            "logs_per_second": round(throughput, 2),
            "logs_per_minute": round(throughput * 60, 2),
            "logs_per_hour": total_logs
        },
        "processing_times": {
            "avg_seconds": round(avg_processing_time, 2),
            "max_seconds": round(max_processing_time, 2),
            "min_seconds": round(min_processing_time, 2)
        },
        "errors": {
            "total_errors": severity_counts.get("ERROR", 0) + severity_counts.get("CRITICAL", 0),
            "error_rate_percentage": round(error_rate * 100, 2)
        },
        "distribution": {
            "severity": dict(severity_counts),
            "categories": dict(category_counts),
            "services": dict(service_counts)
        },
        "summary": {
            "total_incidents": total_logs,
            "average_processing_speed": f"{round(1/avg_processing_time, 2) if avg_processing_time > 0 else 0} logs/second"
        }
    }


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