"""Hand-crafted labeled incident set for false-positive evaluation."""

from __future__ import annotations

import random
from typing import Dict, List


def _event(level: str, service: str, message: str, latency_ms: int) -> Dict[str, object]:
    return {
        "level": level,
        "service": service,
        "message": message,
        "latency_ms": latency_ms,
    }


def _normal_incident(rng: random.Random, idx: int) -> Dict[str, object]:
    service = rng.choice(
        [
            "api-gateway",
            "auth-service",
            "payment-processor",
            "inventory-service",
            "notification-service",
            "db-proxy",
        ]
    )
    scenario = idx % 8
    if scenario == 0:
        reason = "normal traffic spike then recovery"
        events = [
            _event("INFO", service, "Traffic increase detected", rng.randint(20, 60)),
            _event("INFO", service, "Autoscaling triggered", rng.randint(30, 80)),
            _event("INFO", service, "New instances healthy", rng.randint(15, 45)),
            _event("INFO", service, "Queue depth stabilized", rng.randint(10, 40)),
            _event("INFO", service, "Traffic normalized", rng.randint(20, 50)),
        ]
    elif scenario == 1:
        reason = "cache warm-up completed successfully"
        events = [
            _event("INFO", service, "Cache cold start detected", rng.randint(25, 80)),
            _event("INFO", service, "Cache fill in progress", rng.randint(20, 70)),
            _event("INFO", service, "Cache hit ratio improving", rng.randint(10, 35)),
            _event("INFO", service, "Cache warm-up completed", rng.randint(12, 40)),
            _event("INFO", service, "Request latency returned to baseline", rng.randint(8, 30)),
        ]
    elif scenario == 2:
        reason = "scheduled deployment without errors"
        events = [
            _event("INFO", service, "Deployment started", rng.randint(15, 40)),
            _event("INFO", service, "Readiness checks passed", rng.randint(10, 25)),
            _event("INFO", service, "Rolling update at 50 percent", rng.randint(12, 28)),
            _event("INFO", service, "Deployment completed", rng.randint(10, 25)),
            _event("INFO", service, "All pods healthy", rng.randint(8, 20)),
        ]
    elif scenario == 3:
        reason = "temporary retry burst resolved"
        events = [
            _event("INFO", service, "Upstream timeout detected", rng.randint(60, 130)),
            _event("WARNING", service, "Retry count elevated", rng.randint(70, 160)),
            _event("INFO", service, "Circuit breaker remained closed", rng.randint(45, 110)),
            _event("INFO", service, "Retry burst subsided", rng.randint(20, 70)),
            _event("INFO", service, "Request success rate normalized", rng.randint(12, 35)),
        ]
    elif scenario == 4:
        reason = "batch job completed during off-peak window"
        events = [
            _event("INFO", service, "Batch job started", rng.randint(25, 60)),
            _event("INFO", service, "Large queue processed", rng.randint(30, 90)),
            _event("INFO", service, "Worker utilization high", rng.randint(40, 100)),
            _event("INFO", service, "Batch job completed", rng.randint(20, 55)),
            _event("INFO", service, "Queue cleared", rng.randint(10, 35)),
        ]
    elif scenario == 5:
        reason = "brief database latency increase with recovery"
        events = [
            _event("INFO", service, "Read replica lag increased", rng.randint(40, 120)),
            _event("WARNING", service, "Query response time elevated", rng.randint(90, 180)),
            _event("INFO", service, "Connection pool steady", rng.randint(25, 70)),
            _event("INFO", service, "Replica caught up", rng.randint(15, 50)),
            _event("INFO", service, "Latency returned to baseline", rng.randint(10, 35)),
        ]
    elif scenario == 6:
        reason = "notification backlog drained normally"
        events = [
            _event("INFO", service, "Notification queue depth rising", rng.randint(30, 85)),
            _event("INFO", service, "Worker capacity increased", rng.randint(35, 90)),
            _event("INFO", service, "Backlog reduced", rng.randint(25, 70)),
            _event("INFO", service, "Notifications sent successfully", rng.randint(12, 40)),
            _event("INFO", service, "Queue empty", rng.randint(8, 25)),
        ]
    else:
        reason = "routine auth traffic with no incident"
        events = [
            _event("INFO", service, "Authentication requests steady", rng.randint(15, 45)),
            _event("INFO", service, "Token validation successful", rng.randint(10, 30)),
            _event("INFO", service, "Session refresh succeeded", rng.randint(12, 35)),
            _event("INFO", service, "No anomalies detected", rng.randint(8, 20)),
            _event("INFO", service, "Traffic within expected range", rng.randint(10, 30)),
        ]

    while len(events) < 5:
        events.append(_event("INFO", service, "Routine log entry", rng.randint(10, 40)))

    return {
        "id": f"incident_{idx:03d}",
        "label": "not_anomaly",
        "reason": reason,
        "events": events[:10],
    }


def _anomaly_incident(rng: random.Random, idx: int) -> Dict[str, object]:
    service = rng.choice(
        [
            "api-gateway",
            "auth-service",
            "payment-processor",
            "inventory-service",
            "notification-service",
            "db-proxy",
        ]
    )
    scenario = idx % 8
    if scenario == 0:
        reason = "connection pool exhausted"
        events = [
            _event("WARNING", service, "Pool at 80 percent", rng.randint(120, 220)),
            _event("ERROR", service, "Pool at 95 percent", rng.randint(220, 380)),
            _event("CRITICAL", service, "Connection pool exhausted", rng.randint(400, 1200)),
            _event("ERROR", service, "Request timeout", rng.randint(300, 1500)),
            _event("ERROR", service, "Request timeout", rng.randint(300, 1500)),
        ]
    elif scenario == 1:
        reason = "database deadlock and retry storm"
        events = [
            _event("WARNING", service, "Slow query detected", rng.randint(150, 260)),
            _event("ERROR", service, "Deadlock found while waiting for lock", rng.randint(300, 700)),
            _event("ERROR", service, "Retry attempt 1 failed", rng.randint(280, 600)),
            _event("ERROR", service, "Retry attempt 2 failed", rng.randint(320, 800)),
            _event("CRITICAL", service, "Transaction aborted after retries", rng.randint(500, 1400)),
        ]
    elif scenario == 2:
        reason = "memory leak causing service instability"
        events = [
            _event("WARNING", service, "Memory usage at 86 percent", rng.randint(220, 420)),
            _event("WARNING", service, "GC pause increasing", rng.randint(300, 600)),
            _event("ERROR", service, "Memory usage at 94 percent", rng.randint(650, 1300)),
            _event("CRITICAL", service, "OOM kill triggered", rng.randint(900, 2500)),
            _event("ERROR", service, "Pod restarted after crash", rng.randint(500, 1500)),
        ]
    elif scenario == 3:
        reason = "downstream dependency outage"
        events = [
            _event("WARNING", service, "Upstream health degraded", rng.randint(120, 260)),
            _event("ERROR", service, "Dependency request failed", rng.randint(280, 700)),
            _event("ERROR", service, "Circuit breaker OPEN", rng.randint(350, 900)),
            _event("CRITICAL", service, "Fallback service unavailable", rng.randint(600, 1800)),
            _event("ERROR", service, "Request queue stalled", rng.randint(400, 1200)),
        ]
    elif scenario == 4:
        reason = "rate limit abuse on public endpoint"
        events = [
            _event("INFO", service, "Traffic spike detected", rng.randint(90, 180)),
            _event("WARNING", service, "Rate limit threshold reached", rng.randint(150, 300)),
            _event("ERROR", service, "429 responses increasing", rng.randint(220, 500)),
            _event("CRITICAL", service, "Burst traffic blocked", rng.randint(300, 700)),
            _event("ERROR", service, "Client retries amplifying load", rng.randint(250, 650)),
        ]
    elif scenario == 5:
        reason = "disk full blocking writes"
        events = [
            _event("WARNING", service, "Disk usage at 88 percent", rng.randint(180, 320)),
            _event("WARNING", service, "Cleanup job delayed", rng.randint(200, 400)),
            _event("ERROR", service, "Write failed: no space left on device", rng.randint(500, 1200)),
            _event("CRITICAL", service, "Persistent volume full", rng.randint(700, 1800)),
            _event("ERROR", service, "Service unable to persist events", rng.randint(400, 1500)),
        ]
    elif scenario == 6:
        reason = "certificate expiration causing request failures"
        events = [
            _event("WARNING", service, "TLS certificate expiring soon", rng.randint(80, 160)),
            _event("ERROR", service, "Handshake failed", rng.randint(240, 520)),
            _event("ERROR", service, "Client connection rejected", rng.randint(260, 600)),
            _event("CRITICAL", service, "Certificate expired", rng.randint(600, 1400)),
            _event("ERROR", service, "API unavailable to clients", rng.randint(420, 1000)),
        ]
    else:
        reason = "message queue backlog with consumer lag"
        events = [
            _event("INFO", service, "Queue length rising", rng.randint(80, 170)),
            _event("WARNING", service, "Consumer lag increasing", rng.randint(150, 320)),
            _event("ERROR", service, "Delivery delay exceeded threshold", rng.randint(300, 900)),
            _event("CRITICAL", service, "Queue backlog critical", rng.randint(700, 1800)),
            _event("ERROR", service, "Messages timing out", rng.randint(350, 1200)),
        ]

    while len(events) < 5:
        events.append(_event("ERROR", service, "Anomaly continued", rng.randint(250, 1000)))

    return {
        "id": f"incident_{idx:03d}",
        "label": "anomaly",
        "reason": reason,
        "events": events[:10],
    }


def build_labeled_test_set() -> List[Dict[str, object]]:
    """Create 200 incidents with controlled randomness and accurate labels."""

    rng = random.Random(42)
    incidents: List[Dict[str, object]] = []

    for index in range(1, 161):
        incidents.append(_normal_incident(rng, index))

    for index in range(161, 201):
        incidents.append(_anomaly_incident(rng, index))

    return incidents


LABELED_TEST_SET = build_labeled_test_set()

