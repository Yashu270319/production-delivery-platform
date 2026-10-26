import json
import os
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from time import perf_counter
import httpx
from fastapi import FastAPI, Response


app = FastAPI(title="PDP Service Status API")

REQUEST_COUNT = Counter(
    "pdp_http_requests_total",
    "Total HTTP requests received by the PDP API",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "pdp_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


@app.middleware("http")
async def count_requests(request, call_next):
    start_time = perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code="500",
        ).inc()
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path,
        ).observe(perf_counter() - start_time)
        raise

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=str(response.status_code),
    ).inc()

    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(perf_counter() - start_time)

    return response


def check_dependency():
    dependency_url = os.getenv("DEPENDENCY_URL")

    if not dependency_url:
        return {"status": "not_configured"}, 503

    try:
        response = httpx.get(dependency_url, timeout=2.0)
        response.raise_for_status()
        return {"status": "available"}, 200
    except (httpx.HTTPError, ValueError):
        return {"status": "unavailable"}, 503


@app.get("/")
def root():
    return {"service": "pdp-api", "status": "running"}


@app.get("/health/live")
def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
def readiness():
    dependency_status, status_code = check_dependency()

    if status_code != 200:
        return Response(
            content=json.dumps({
                "status": "not_ready",
                "dependency": dependency_status["status"],
            }),
            status_code=status_code,
            media_type="application/json",
        )

    return {"status": "ready"}


@app.get("/version")
def version():
    return {"service": "pdp-api", "version": os.getenv("APP_VERSION", "dev")}


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/dependency-check")
def dependency_check():
    dependency_status, status_code = check_dependency()

    return Response(
        status_code=status_code,
        content=json.dumps(dependency_status),
        media_type="application/json",
    )
