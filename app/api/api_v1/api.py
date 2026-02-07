from fastapi import APIRouter
from app.api.api_v1.endpoints import incident

api_router = APIRouter()
api_router.include_router(incident.router, prefix="/incident", tags=["incident"])
