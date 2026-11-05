# Release and Rollback Runbook

## 1. Purpose

This runbook documents the managed release workflow in the Production Delivery Platform (PDP).

It covers:

- Local container image availability checks.
- Candidate deployment and validation.
- Nginx reverse-proxy traffic switching.
- Post-switch verification.
- Restoration of the previous backend after failed verification.

The environment uses Docker, a local container registry, FastAPI, and Nginx. It is designed to demonstrate release-engineering practices without paid cloud infrastructure.

## 2. Architecture and Components

| Component | Purpose | Host endpoint |
|---|---|---|
| Local Docker Registry | Stores versioned application images | `127.0.0.1:5000` |
| `pdp-managed-release` | Managed release `1.0.0` | `127.0.0.1:8002` |
| `pdp-release-1.0.1` | Existing release `1.0.1` | `127.0.0.1:8001` |
| `pdp-candidate-1.0.2` | Candidate release `1.0.2` | `127.0.0.1:8003` |
| `pdp-proxy` | Nginx reverse proxy | `127.0.0.1:8080` |

### Release scripts

| Script | Responsibility |
|---|---|
| `scripts/validate-deployment.sh` | Validates liveness, expected version, and readiness |
| `scripts/deploy-release.sh` | Checks the registry, pulls an image, starts a managed container, and validates it |
| `scripts/switch-release.sh` | Validates a supported release, switches Nginx traffic, verifies the live version, and attempts restoration on failure |

The traffic-switch script currently supports `1.0.0`, `1.0.1`, and `1.0.2`.

## 3. Pre-deployment Checks

Inspect running containers:

```bash
sudo docker ps
```

Check the currently active application version:

```bash
curl -fsS http://127.0.0.1:8080/version
```

Validate the Nginx configuration:

```bash
sudo docker exec pdp-proxy nginx -t
```

Inspect the current upstream:

```bash
sudo docker exec pdp-proxy cat /etc/nginx/proxy/active-backend.conf
```

Confirm that the candidate container and its required dependency are available before attempting a traffic switch.

## 4. Candidate Deployment and Validation

Candidate validation is performed by:

```bash
./scripts/validate-deployment.sh BASE_URL EXPECTED_VERSION
```

Example for release `1.0.0`:

```bash
./scripts/validate-deployment.sh http://127.0.0.1:8002 1.0.0
```

The validation script checks three conditions:

1. **Liveness:** `/health/live` must return HTTP 200 with the expected response.
2. **Version:** `/version` must report the requested application version.
3. **Readiness:** `/health/ready` must return HTTP 200 with `{"status":"ready"}`.

### Liveness and readiness semantics

Liveness checks whether the application process is responsive.

Readiness checks whether the application can serve requests, including the availability of its configured dependency.

If `DEPENDENCY_URL` is missing or the dependency is unavailable, readiness returns HTTP 503. The application can remain alive while being unready.

The Docker health check uses the liveness endpoint. Consequently, a dependency outage does not necessarily make the application container unhealthy.

A candidate must pass readiness validation before it is accepted by the deployment validation script.

## 5. Deploy an Image from the Local Registry

Example:

```bash
./scripts/deploy-release.sh 1.0.0
```

The deployment script:

1. Validates the requested numeric version format.
2. Checks the local registry for the image manifest.
3. Refuses to replace an existing `pdp-managed-release` container.
4. Pulls the requested versioned image.
5. Starts the managed container on `127.0.0.1:8002`.
6. Runs deployment validation.
7. Removes the newly created container if validation fails.

The deployment operation does not switch Nginx traffic.

**Important:** This deployment script uses a fixed managed container name and host port. It is not a general-purpose multi-release deployment manager.

## 6. Switch Live Traffic

The traffic-switch script accepts one supported version:

```bash
./scripts/switch-release.sh VERSION
```

Supported release mappings:

| Version | Container | Host port |
|---|---|---|
| `1.0.0` | `pdp-managed-release` | `8002` |
| `1.0.1` | `pdp-release-1.0.1` | `8001` |
| `1.0.2` | `pdp-candidate-1.0.2` | `8003` |

### Example: Switch to release 1.0.0

```bash
./scripts/switch-release.sh 1.0.0
```

### Example: Switch back to release 1.0.1

```bash
./scripts/switch-release.sh 1.0.1
```

### Example: Switch to release 1.0.2

```bash
./scripts/switch-release.sh 1.0.2
```

### Traffic-switch sequence

The script performs the following operations:

1. Checks that the requested version is supported.
2. Tests the existing Nginx configuration.
3. Confirms that the candidate container is running.
4. Validates the candidate directly through its host port.
5. Backs up the existing upstream configuration.
6. Writes the new upstream configuration using a temporary file and atomic replacement.
7. Tests the updated Nginx configuration.
8. Reloads Nginx.
9. Checks the application version through the live proxy.
10. Attempts to restore the previous upstream if switching or post-switch verification fails.

The active backend is configured in:

```text
proxy/active-backend.conf
```

The proxy listens on host port `8080` and forwards requests to the selected application container on port `8000`.

### Verify the active release

Check the live version:

```bash
curl -fsS http://127.0.0.1:8080/version
```

Inspect the active backend:

```bash
sudo docker exec pdp-proxy cat /etc/nginx/proxy/active-backend.conf
```

The reported application version and configured upstream should correspond to the same release.

## 7. Rollback Procedure

If a newly selected release fails verification, the switch script attempts to restore the previous upstream configuration and reload Nginx.

If manual rollback is required, select a previously validated release:

```bash
./scripts/switch-release.sh 1.0.1
```

Or, if `1.0.0` is the known-good release:

```bash
./scripts/switch-release.sh 1.0.0
```

Verify the result:

```bash
curl -fsS http://127.0.0.1:8080/version
sudo docker exec pdp-proxy cat /etc/nginx/proxy/active-backend.conf
```

Keep the previous known-good release running until the replacement has passed verification.

Automatic restoration is best-effort. If restoration itself fails, the script reports a critical error and manual inspection is required.

## 8. Rollback Test Evidence

The release-switch workflow was tested in both directions:

- Release `1.0.1` to `1.0.0`.
- Release `1.0.0` back to `1.0.1`.

Both switches passed candidate validation and live proxy verification.

A separate failure exercise used a temporary copy of the switch script configured to expect the impossible application version `9.9.9` during post-switch verification.

The simulated verification failure triggered restoration of the previous backend.

After the exercise:

- The proxy returned application version `1.0.1`.
- The upstream pointed to `pdp-release-1.0.1:8000`.
- Both release containers remained running.
- The temporary test script was removed.

Automated tests are also available:

```bash
python -m unittest tests.test_switch_release -v
```

These tests use temporary files and mocked Docker commands. They cover rejection of unsupported versions and preservation of the previous backend when the new Nginx configuration fails validation.

The tests do not modify the live release environment.

## 9. Operational Limitations

The current implementation has several deliberate limitations:

- The previous known-good release must remain available for rollback.
- Rollback is based on configuration restoration and verification, not a complete orchestration platform.
- A successful Nginx reload does not independently prove application health.
- Restoration can itself fail and require manual intervention.
- Monitoring-triggered automatic rollback is not implemented.
- Alert delivery is not configured.
- Durable release-history and audit services are not implemented.
- The environment does not provide high availability or managed cloud deployment.

PDP is a local engineering and learning environment, not a production-hardened deployment service.

## 10. Future Improvements

Potential extensions include:

- Release audit history and deployment metadata.
- Actionable Prometheus alert rules and alert delivery.
- Automated dependency-failure and recovery exercises.
- Stronger rollback verification and recovery reporting.
- Local Kubernetes deployment and rollout management.
