# Production Delivery Platform (PDP)

A local, resource-conscious platform for learning and demonstrating production-oriented software delivery, containerization, testing, observability, and reliability practices.

## Current Status

**Milestones 1–3: Containerized API, CI gates, and controlled local releases — Implemented**

The project provides a tested FastAPI service, versioned container images, CI quality and security checks, a local image registry, and an Nginx-based release switch with rollback verification.

## Architecture

```text
Developer
   |
   v
Python API Tests (pytest)
   |
   v
Docker Image: pdp-api:1.0.0
   |
   v
Docker Compose
   |
   v
FastAPI Service (port 8000)
   |
   +--> Health endpoints
   +--> Version endpoint
   +--> Prometheus metrics
   +--> Dependency-check endpoint
```

## Features

- **Service identity:** `GET /`
- **Liveness probe:** `GET /health/live`
- **Readiness endpoint:** `GET /health/ready`
- **Version information:** `GET /version`
- **Prometheus metrics:** `GET /metrics`
- **Dependency check:** `GET /dependency-check`
- **Automated API tests:** pytest and FastAPI TestClient
- **Containerized deployment:** Docker and Docker Compose
- **Non-root execution:** the API runs as `appuser` (UID 10001)
- **Container health check:** Docker monitors the liveness endpoint

The dependency-check endpoint intentionally returns HTTP 503 because no external dependency is configured yet. The current readiness endpoint is a basic placeholder, not a dependency-aware readiness check.

## Requirements

- Linux
- Git
- Python 3.12 or compatible
- Docker Engine
- Docker Compose

## Run Locally

Clone the repository and enter its directory. Create a Python virtual environment, install the dependencies, and run the tests:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
```

Build and start the containerized service from the repository root:

```bash
docker compose -f compose/compose.yaml up -d --build
```

Check the service:

```bash
docker compose -f compose/compose.yaml ps
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/version
curl http://127.0.0.1:8000/metrics
```

Stop the service when finished:

```bash
docker compose -f compose/compose.yaml down
```

## Roadmap

1. Strengthen release health checks and rollback validation.
2. Add metrics dashboards and alerting.
3. Introduce local Kubernetes deployment and rollout exercises.
4. Document service-level indicators, objectives, and recovery procedures.

See [docs/RELEASE-AND-ROLLBACK.md](docs/RELEASE-AND-ROLLBACK.md) for the implemented release and rollback workflow.

## Project Scope

PDP is a local learning and demonstration environment. It is designed to practice production engineering concepts using free, locally runnable tools; it does not claim to reproduce the scale or managed services of a cloud production environment.
