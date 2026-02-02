from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.models.base import Base

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="Open", index=True)
    severity = Column(String, default="Medium")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Analysis results
    root_cause = Column(Text, nullable=True)
    suggested_fix = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # RAG Embeddings (Dimension 768 for Gemini text-embedding-004)
    embedding = Column(Vector(768))
