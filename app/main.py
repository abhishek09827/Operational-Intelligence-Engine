from fastapi import FastAPI, Request
from app.core.config import settings
from app.core.logging import setup_logging
from prometheus_fastapi_instrumentator import Instrumentator
import logging
import time

# Setup structured logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)

# Instrument Prometheus
Instrumentator().instrument(app).expose(app)

from app.api.api_v1.api import api_router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    logger.info(
        "Request processed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration": process_time
        }
    )
    return response

@app.get("/health")
def health_check():
    logger.info("Health check requested")
    return {"status": "ok", "version": "0.1.0"}

@app.get("/")
def root():
    return {"message": "Welcome to OpsPilot AI API"}
