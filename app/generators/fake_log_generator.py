"""
Fake Log Generator for testing and demo purposes.
Yields realistic log entries that can be streamed for real-time processing.
"""

import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Generator, Dict, Any


# Log patterns for different services
ERROR_PATTERNS = [
    "Connection timeout while connecting to database",
    "Failed to connect to Redis server",
    "API endpoint timeout after 30s",
    "Database deadlock detected",
    "Memory usage exceeded threshold",
    "Failed to process payment transaction",
    "Service unavailable for 5000 consecutive requests",
    "Circular dependency detected in service graph",
    "Garbage collection taking too long",
    "Network packet loss detected",
    "SQL injection attempt blocked",
    "Authentication failed for user admin",
    "File system permission denied",
    "Load balancer routing error",
    "Container OOM killer triggered"
]

WARNING_PATTERNS = [
    "High memory usage detected",
    "Slow response time (>200ms)",
    "High CPU utilization",
    "Cache hit rate dropping below threshold",
    "Database query optimization needed",
    "API rate limit approaching",
    "Service health check failing",
    "SSL certificate expiration warning",
    "Log rotation needed",
    "Disk space filling up"
]

INFO_PATTERNS = [
    "Service started successfully",
    "Request processed successfully",
    "Cache cleared",
    "Health check passed",
    "Configuration updated",
    "User logged in",
    "Data sync completed",
    "Scheduled task executed"
]

# Service names
SERVICES = [
    "auth-service",
    "api-gateway",
    "payment-service",
    "database",
    "redis-cache",
    "user-service",
    "notification-service",
    "analytics-service",
    "log-aggregator"
]

# Log levels
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Categories
CATEGORIES = ["API_ERROR", "DATABASE", "NETWORK", "PAYMENT_FAILURE", "TIMEOUT", "PERFORMANCE"]


def generate_fake_log(
    level: str = None,
    service_name: str = None,
    log_id: str = None,
    category: str = None,
    seed: str = None
) -> Dict[str, Any]:
    """
    Generate a single fake log entry.
    
    Args:
        level: Log level (defaults to random)
        service_name: Service name (defaults to random)
        log_id: Unique log ID (defaults to random)
        category: Error category (defaults to random)
        seed: Seed for reproducibility
        
    Returns:
        Dictionary containing the log entry
    """
    if seed:
        random.seed(seed)
    
    if level is None:
        # 5% chance of ERROR or CRITICAL
        if random.random() < 0.05:
            level = random.choice(["ERROR", "CRITICAL"])
        else:
            level = random.choice(LOG_LEVELS)
    
    if service_name is None:
        service_name = random.choice(SERVICES)
    
    if log_id is None:
        log_id = f"log_{uuid.uuid4().hex[:16]}"
    
    if category is None:
        category = random.choice(CATEGORIES)
    
    # Generate message based on level and category
    if level in ["ERROR", "CRITICAL"]:
        message = random.choice(ERROR_PATTERNS)
    elif level == "WARNING":
        message = random.choice(WARNING_PATTERNS)
    else:
        message = random.choice(INFO_PATTERNS)
    
    # Add context based on category
    context = {
        "log_id": log_id,
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "service_name": service_name,
        "category": category,
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "environment": random.choice(["production", "staging", "development"]),
        "message": message
    }
    
    # Add category-specific fields
    if category == "API_ERROR":
        context["api_error"] = {
            "endpoint": f"/api/{random.choice(['users', 'orders', 'payments', 'products'])}",
            "http_method": random.choice(["GET", "POST", "PUT", "DELETE"]),
            "response_time_ms": random.randint(100, 5000),
            "status_code": random.choice([500, 502, 503, 504])
        }
    elif category == "DATABASE":
        context["database_error"] = {
            "query_type": random.choice(["SELECT", "INSERT", "UPDATE", "DELETE"]),
            "table_name": random.choice(["users", "orders", "products", "payments"]),
            "duration_ms": random.randint(10, 5000)
        }
    elif category == "PAYMENT_FAILURE":
        context["payment_error"] = {
            "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
            "amount": random.randint(100, 10000),
            "currency": random.choice(["USD", "EUR", "INR"]),
            "error_code": random.choice(["INSUFFICIENT_FUNDS", "CARD_DECLINED", "BANK_ERROR"])
        }
    elif category == "TIMEOUT":
        context["timeout_error"] = {
            "timeout_seconds": random.choice([5, 10, 30, 60]),
            "endpoint": f"/api/{random.choice(['heavy', 'complex', 'long-running'])}",
            "retry_count": random.randint(0, 3)
        }
    
    return context


def fake_log_generator(
    interval: float = 1.0,
    num_logs: int = None,
    start_immediately: bool = True,
    error_rate: float = 0.05
) -> Generator[Dict[str, Any], None, None]:
    """
    Generator that yields fake logs at specified intervals.
    
    Args:
        interval: Time in seconds between logs (default: 1.0)
        num_logs: Maximum number of logs to yield (None for infinite)
        start_immediately: Start yielding immediately (default: True)
        error_rate: Probability of ERROR/CRITICAL logs (default: 0.05)
        
    Yields:
        Dictionary containing fake log entries
    """
    count = 0
    
    if start_immediately:
        count += 1
        yield generate_fake_log()
    
    while num_logs is None or count < num_logs:
        time.sleep(interval)
        
        # Randomize interval slightly
        actual_interval = interval * random.uniform(0.8, 1.2)
        time.sleep(actual_interval)
        
        count += 1
        yield generate_fake_log()


def generate_realistic_stream(
    duration: int = 60,
    logs_per_second: int = 1,
    error_rate: float = 0.05
) -> Generator[Dict[str, Any], None, None]:
    """
    Generate a realistic log stream for testing.
    
    Args:
        duration: Duration in seconds (default: 60)
        logs_per_second: Number of logs per second (default: 1)
        error_rate: Probability of ERROR/CRITICAL logs (default: 0.05)
        
    Yields:
        Dictionary containing fake log entries
    """
    total_logs = duration * logs_per_second
    generator = fake_log_generator(
        interval=1.0/logs_per_second,
        num_logs=total_logs,
        error_rate=error_rate
    )
    
    for log in generator:
        yield log


def generate_spiked_stream(
    base_interval: float = 2.0,
    spike_probability: float = 0.3,
    spike_multiplier: float = 5.0,
    duration: int = 60
) -> Generator[Dict[str, Any], None, None]:
    """
    Generate a log stream with random spikes in activity.
    
    Args:
        base_interval: Base interval between logs in seconds
        spike_probability: Probability of a spike event
        spike_multiplier: How many logs during a spike
        duration: Duration in seconds
        
    Yields:
        Dictionary containing fake log entries
    """
    spike_logs = int(base_interval * spike_multiplier * spike_probability)
    
    generator = fake_log_generator(
        interval=base_interval,
        num_logs=duration * spike_multiplier,
        error_rate=0.05
    )
    
    for i, log in enumerate(generator):
        # At random intervals, add spike logs
        if i % int(duration * spike_multiplier / 20) == 0 and random.random() < spike_probability:
            # Insert spike logs
            for _ in range(spike_logs):
                yield generate_fake_log()
        
        yield log