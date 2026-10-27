# INC-002: Dependency Failure and Recovery Validation

## Summary

A controlled dependency outage was introduced in the local Production
Delivery Platform (PDP) environment to validate API readiness behavior,
failure detection, monitoring instrumentation, and recovery.

The dependency container was stopped and subsequently restarted.
The API correctly reported itself as not ready while the dependency
was unavailable and returned to a ready state after recovery.

## Environment

- Platform: Local Docker-based Production Delivery Platform
- Network: `pdp-release-net`
- API version under test: `1.0.2`
- Entry point: Nginx at `http://127.0.0.1:8080`
- Dependency container: `pdp-dependency`
- Monitoring: Prometheus and Grafana

## Incident Timeline

### 1. Healthy baseline

Request:

`GET /health/ready`

Observed result:

- HTTP 200 OK
- Response: `{"status":"ready"}`

Assessment: The API was ready before the failure was introduced.

### 2. Dependency failure

Action: Stopped the `pdp-dependency` container.

Command:

`sudo docker stop pdp-dependency`

Readiness request returned:

- HTTP 503 Service Unavailable
- Response: `{"status": "not_ready", "dependency": "unavailable"}`

Assessment: The API detected the unavailable dependency and did not
incorrectly report readiness.

### 3. Dependency recovery

Action: Restarted the dependency container.

Command:

`sudo docker start pdp-dependency`

The dependency health endpoint returned:

`{"status": "available"}`

### 4. End-to-end readiness recovery

Request:

`GET /health/ready`

Observed result:

- HTTP 200 OK
- Response: `{"status":"ready"}`

Assessment: Readiness recovered through the Nginx entry point after the
dependency became available again. No release switch or Nginx routing
change was needed for this test.

## Monitoring Evidence

Prometheus query:

`sum by (status_code) (pdp_http_requests_total)`

Observed cumulative counters at the time of verification:

| HTTP status | Request count |
| --- | ---: |
| 200 | 435 |
| 503 | 1 |

The API's Prometheus instrumentation recorded an HTTP 503 response.
These are cumulative counters, not counts limited to this incident.

## Outcome

The controlled test passed the following checks:

- Readiness was successful before the outage.
- Readiness returned HTTP 503 while the dependency was unavailable.
- The dependency health endpoint responded after restart.
- API readiness recovered to HTTP 200.
- Prometheus recorded the HTTP 503 response.

## Scope and Limitations

This test validates dependency-aware readiness and recovery. It does not
by itself prove automatic traffic removal, alert delivery, zero-downtime
recovery, or the behavior of every API release that shares the dependency.

## Follow-up Opportunities

- Configure and validate an alert for sustained readiness failures or
  elevated HTTP 5xx responses.
- Verify how the reverse proxy and orchestrator handle an unready API.
- Capture recovery duration and define a measurable recovery objective.
- Repeat the test under automated deployment and rollback workflows.
