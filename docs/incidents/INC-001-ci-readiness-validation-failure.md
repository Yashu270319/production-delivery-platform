# INC-001: CI Deployment Readiness Validation Failure

## Incident Summary

| Field | Details |
|---|---|
| Incident ID | INC-001 |
| Severity | SEV-3 — CI pipeline failure |
| Component | GitHub Actions, Docker deployment validation, FastAPI readiness endpoint |
| Status | Fix committed; post-fix CI verification pending |
| Detection method | Automated deployment validation |
| Affected environment | GitHub Actions CI runner |

## 1. Incident Description

The GitHub Actions container-validation job failed while validating API version `1.0.0`.

The liveness and version checks passed, but the readiness check returned HTTP `503 Service Unavailable`. As a result, the deployment validation script exited with status code `1`, causing the workflow job to fail.

### Observed output

```text
PASS: Liveness check
PASS: Version check (1.0.0)
curl: (22) The requested URL returned error: 503
FAIL: /health/ready did not return a successful HTTP response.
Error: Process completed with exit code 1.
```

## 2. Impact

- The container-validation job could not complete successfully.
- The CI pipeline did not establish that the container was ready to serve requests.
- This was a CI validation failure; the available evidence does not establish a production outage or customer impact.

## 3. Technical Background

The API implements separate health checks:

- `/health/live` checks whether the application process is alive.
- `/version` reports the application version.
- `/health/ready` checks whether the application can serve requests, including whether its configured dependency is available.

The API uses the `DEPENDENCY_URL` environment variable to locate its dependency health endpoint.

A running application process does not necessarily mean its dependencies are available. Therefore, readiness validation correctly rejects an API that cannot confirm dependency availability.

## 4. Root Cause

The original GitHub Actions workflow started the API container without starting its required dependency health server or configuring `DEPENDENCY_URL`.

Consequently, the API could not confirm dependency availability and returned HTTP 503 from `/health/ready`.

The issue was an incomplete CI test environment, not evidence that the liveness endpoint or version reporting was broken.

## 5. Remediation

The CI workflow was updated to:

1. Create a dedicated Docker network named `pdp-ci-net`.
2. Start the dependency health server in a separate container.
3. Start the API container on the same network.
4. Configure the API with:

   ```text
   DEPENDENCY_URL=http://pdp-dependency-ci:8081/health
   ```

5. Retry the liveness check while the API starts.
6. Run the deployment validation script.
7. Remove the temporary containers and network using an unconditional cleanup step.

The readiness check was retained. The fix supplies the dependency required by the application instead of bypassing the health check.

## 6. Validation Evidence

### Local automated tests

Command:

```bash
PYTHONPATH=. .venv/bin/pytest -q
```

Result:

```text
9 passed, 1 warning
```

The warning concerned Starlette's deprecated use of `httpx` with its test client. It did not cause the tests to fail.

### CI workflow change

The workflow fix was committed and pushed:

```text
e97f830 fix(ci): configure dependency for readiness validation
```

### Post-fix verification

**Pending confirmation:** The subsequent GitHub Actions run must be inspected to confirm that the container-validation job and `/health/ready` check pass.

Local pytest results alone do not prove that the Docker-based CI validation succeeds.

## 7. Preventive Actions

- Keep liveness, readiness, and version checks separate.
- Ensure CI environments start all required dependencies.
- Configure dependencies explicitly through environment variables.
- Retain deployment validation as a release gate.
- Capture container logs when health checks fail.
- Verify the GitHub Actions result after each workflow change.
- Consider automated integration tests for dependency-unavailable and dependency-recovered scenarios.

## 8. Lessons Learned

A healthy process is not necessarily a ready service. Reliable deployment validation must test the application's dependencies and ability to serve requests, not merely confirm that the process is running.

The incident demonstrates the importance of reproducing required service dependencies in CI and preserving meaningful readiness checks.

## 9. Resolution Criteria

This incident can be marked fully resolved after a GitHub Actions run confirms that:

- The API container starts successfully.
- Liveness validation passes.
- The expected version is reported.
- Readiness validation returns a successful HTTP response.
- The deployment validation job completes successfully.
