from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.sql import func
from app.models.base import Base

class LogEntry(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    level = Column(String, index=True)
    service_name = Column(String, index=True)
    message = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True)
