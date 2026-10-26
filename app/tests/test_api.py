
from fastapi.testclient import TestClient

from app.src.main import app

import httpx

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

def test_readiness_fails_when_dependency_is_not_configured(monkeypatch):
    monkeypatch.delenv("DEPENDENCY_URL", raising=False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependency": "not_configured",
    }


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


def test_readiness_succeeds_when_dependency_is_healthy(monkeypatch):
    monkeypatch.setenv("DEPENDENCY_URL", "http://dependency.test/health")

    def mock_get(url, timeout):
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr("app.src.main.httpx.get", mock_get)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_fails_when_dependency_is_unavailable(monkeypatch):
    monkeypatch.setenv("DEPENDENCY_URL", "http://dependency.test/health")

    def mock_get(url, timeout):
        request = httpx.Request("GET", url)
        return httpx.Response(503, request=request)

    monkeypatch.setattr("app.src.main.httpx.get", mock_get)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependency": "unavailable",
    }


def test_liveness_remains_healthy_when_dependency_is_unavailable(monkeypatch):
    monkeypatch.setenv("DEPENDENCY_URL", "http://dependency.test/health")

    def mock_get(url, timeout):
        request = httpx.Request("GET", url)
        return httpx.Response(503, request=request)

    monkeypatch.setattr("app.src.main.httpx.get", mock_get)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
