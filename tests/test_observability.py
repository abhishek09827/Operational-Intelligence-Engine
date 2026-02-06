from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check_logs():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}

def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    # Check for a standard prometheus metric
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds" in response.text
