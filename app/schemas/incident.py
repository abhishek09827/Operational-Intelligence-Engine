from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class IncidentBase(BaseModel):
    title: str
    description: str
    severity: Optional[str] = "Medium"

class IncidentCreate(IncidentBase):
    logs: str

class IncidentUpdate(BaseModel):
    root_cause: Optional[str] = None
    suggested_fix: Optional[str] = None
    confidence_score: Optional[float] = None
    status: Optional[str] = None

class IncidentResponse(IncidentBase):
    id: int
    status: str
    created_at: datetime
    root_cause: Optional[str] = None
    suggested_fix: Optional[str] = None
    confidence_score: Optional[float] = None

    class Config:
        from_attributes = True

class AnalysisRequest(BaseModel):
    logs: str
