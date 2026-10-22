import os

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

app = FastAPI(title="PDP Service Status API")

REQUEST_COUNT = Counter(
    "pdp_http_requests_total",
    "Total HTTP requests received by the PDP API",
    ["method", "endpoint"],
)


@app.middleware("http")
async def count_requests(request, call_next):
    response = await call_next(request)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
    ).inc()
    return response


@app.get("/")
def root():
    return {"service": "pdp-api", "status": "running"}


@app.get("/health/live")
def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
def readiness():
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
    return Response(
        status_code=503,
        content='{"status":"not_configured"}',
        media_type="application/json",
    )
