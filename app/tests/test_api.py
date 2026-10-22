
from fastapi.testclient import TestClient

from app.src.main import app

client = TestClient(app)


def test_root_returns_service_identity():
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "pdp-api"
    assert body["status"] == "running"


def test_liveness_endpoint():
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_endpoint():
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_version_endpoint(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "9.8.7")

    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"service": "pdp-api", "version": "9.8.7"}


def test_metrics_endpoint_exposes_prometheus_format():
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "pdp_http_requests_total" in response.text


def test_dependency_check_reports_unconfigured_dependency():
    response = client.get("/dependency-check")

    assert response.status_code == 503
    assert response.json()["status"] == "not_configured"
