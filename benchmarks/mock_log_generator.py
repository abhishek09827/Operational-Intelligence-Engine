"""Realistic log event generator used by the OI-Engine benchmark suite."""

from __future__ import annotations

import random
import time
import uuid
from typing import Any, Dict, Iterable, List

try:
    from faker import Faker
except Exception:  # pragma: no cover - fallback when Faker is unavailable
    Faker = None


SERVICES = [
    "api-gateway",
    "auth-service",
    "payment-processor",
    "inventory-service",
    "notification-service",
    "db-proxy",
]

LOG_LEVELS = {
    "INFO": 0.75,
    "WARNING": 0.15,
    "ERROR": 0.08,
    "CRITICAL": 0.02,
}

NORMAL_MESSAGES = [
    "Request processed successfully",
    "Cache hit for key {key}",
    "Connection pool healthy: {n}/100 active",
    "Health check passed",
    "Rate limit check passed for user {user_id}",
]

ANOMALY_MESSAGES = [
    "Connection timeout after {ms}ms - threshold: 200ms",
    "Memory usage at {pct}% - approaching limit",
    "Database connection pool exhausted: {n}/100 used",
    "Retry attempt {n}/3 failed for endpoint {ep}",
    "Circuit breaker OPEN for service {svc}",
    "Latency spike detected: p99={ms}ms",
]

_FAKE = Faker() if Faker is not None else None


def _random_user_id() -> str:
    if _FAKE is not None:
        return _FAKE.uuid4().hex[:8]
    return uuid.uuid4().hex[:8]


def _random_key() -> str:
    return uuid.uuid4().hex[:8]


def generate_log_event(is_anomaly: bool = False) -> Dict[str, Any]:
    """Generate a single realistic log event.

    The structure intentionally mirrors the prompt so benchmark code can rely on
    stable keys without pulling in the rest of the application.
    """

    service = random.choice(SERVICES)
    if is_anomaly:
        level = random.choice(["ERROR", "CRITICAL"])
        msg_template = random.choice(ANOMALY_MESSAGES)
        message = msg_template.format(
            ms=random.randint(500, 5000),
            pct=random.randint(85, 99),
            n=random.randint(95, 100),
            ep="/api/v1/payments",
            svc=service,
            key=_random_key(),
        )
        latency_ms = random.randint(300, 5000)
    else:
        level = random.choices(
            list(LOG_LEVELS.keys()),
            weights=list(LOG_LEVELS.values()),
        )[0]
        msg_template = random.choice(NORMAL_MESSAGES)
        message = msg_template.format(
            key=_random_key(),
            n=random.randint(10, 80),
            user_id=_random_user_id(),
        )
        latency_ms = random.randint(1, 200)

    return {
        "event_id": str(uuid.uuid4()),
        "service": service,
        "level": level,
        "message": message,
        "timestamp": time.time(),
        "host": f"{service}-pod-{random.randint(1, 5)}",
        "trace_id": uuid.uuid4().hex,
        "latency_ms": latency_ms,
    }


def generate_log_events(count: int, anomaly_every: int = 0) -> List[Dict[str, Any]]:
    """Generate a list of events with a controllable anomaly cadence."""

    events: List[Dict[str, Any]] = []
    for index in range(count):
        is_anomaly = anomaly_every > 0 and index % anomaly_every == 0
        events.append(generate_log_event(is_anomaly=is_anomaly))
    return events


def iter_log_events(count: int, anomaly_every: int = 0) -> Iterable[Dict[str, Any]]:
    """Yield events one by one for streaming or throughput tests."""

    for index in range(count):
        yield generate_log_event(is_anomaly=anomaly_every > 0 and index % anomaly_every == 0)

