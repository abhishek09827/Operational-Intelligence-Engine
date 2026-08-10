from fastapi import APIRouter
from app.api.api_v2.endpoints import alerts

api_v2_router = APIRouter()
api_v2_router.include_router(alerts.router, prefix="/alerts", tags=["v2-alerts"])
