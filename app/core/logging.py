import logging
import sys
from pythonjsonlogger import jsonlogger
from app.core.config import settings

def setup_logging():
    """
    Configure logging to output JSON formatted logs to stdout.
    This is best practice for containerized applications.
    """
    logger = logging.getLogger()
    
    # Check if handlers already exist to avoid duplication
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        
        # Define the JSON format
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ"
        )
        
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Set log level
        logger.setLevel(logging.INFO)
        
        # Set specific levels for third-party libraries if needed
        logging.getLogger("uvicorn.access").disabled = True # Disable default uvicorn access logs to avoid duplicates if handled by middleware or proxy
