from app.api.api_v1.endpoints.incident import infer_severity, infer_confidence


def test_infer_severity_critical():
    assert infer_severity("FATAL: out of memory, service crashed") == "Critical"


def test_infer_severity_high():
    assert infer_severity("ERROR: connection refused") == "High"


def test_infer_severity_medium():
    assert infer_severity("WARN: retrying connection") == "Medium"


def test_infer_severity_low():
    assert infer_severity("all systems nominal, heartbeat ok") == "Low"


def test_infer_confidence_bounded_and_positive():
    full = "The root cause is a failed dependency. The recommended fix is to restart and rollback. " * 20
    c = infer_confidence(full)
    assert 0.0 < c <= 0.95


def test_infer_confidence_zero_for_empty():
    assert infer_confidence("") == 0.0
