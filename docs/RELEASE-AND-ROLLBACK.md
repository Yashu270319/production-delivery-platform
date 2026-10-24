# Release and Rollback Runbook

## Purpose

This runbook documents the local Production Delivery Platform (PDP) release workflow: image checks, deployment validation, Nginx traffic switching, and rollback after failed verification.

The lab uses Docker, a local registry, FastAPI, and Nginx without paid cloud services.

## Components

| Component | Purpose |
|---|---|
| Local registry | Stores versioned images at `127.0.0.1:5000` |
| `pdp-managed-release` | Managed release on host port `8002` |
| `pdp-release-1.0.1` | Existing release on host port `8001` |
| `pdp-proxy` | Nginx reverse proxy on host port `8080` |
| `validate-deployment.sh` | Checks liveness, version, and readiness |
| `deploy-release.sh` | Pulls and validates a registry image |
| `switch-release.sh` | Switches traffic and attempts rollback |

## Pre-deployment checks

Check running containers with `sudo docker ps`.

Check the live version with `curl -fsS http://127.0.0.1:8080/version`.

Check Nginx with `sudo docker exec pdp-proxy nginx -t`.

## Validate a candidate

Example for release `1.0.0`:

`./scripts/validate-deployment.sh http://127.0.0.1:8002 1.0.0`

The readiness endpoint is currently a placeholder and does not check dependency health.

## Deploy an image

Run `./scripts/deploy-release.sh 1.0.0` to check the local registry, pull the image, start the managed container on port `8002`, and validate it. The script refuses to replace an existing `pdp-managed-release` container and attempts to remove a newly created container if validation fails. Deployment does not automatically switch proxy traffic.

## Switch live traffic

Switch to release `1.0.0` with `./scripts/switch-release.sh 1.0.0`.

Switch back to release `1.0.1` with `./scripts/switch-release.sh 1.0.1`.

After switching, check `curl -fsS http://127.0.0.1:8080/version` and inspect the active upstream with `sudo docker exec pdp-proxy cat /etc/nginx/proxy/active-backend.conf`. The reported version and configured upstream should agree.

The switch script validates the candidate, updates the Nginx backend, tests and reloads Nginx, and checks the live version. If post-switch verification fails, it attempts to restore the previous backend and reload Nginx.

## Rollback test evidence

The release switch was tested in both directions: `1.0.1` to `1.0.0`, then back to `1.0.1`. Both switches passed candidate validation and live proxy verification.

A temporary copy of the switch script was then configured to expect the impossible version `9.9.9` during post-switch verification. The simulated verification failure triggered restoration of the previous backend. Afterward, the proxy returned `1.0.1`, the upstream pointed to `pdp-release-1.0.1:8000`, and both release containers remained running. The temporary test script was removed.

This demonstrates recovery from a simulated verification failure, not from an actual application crash or host failure.

## Operational limitations

- Keep the previous known-good release running until the candidate is verified.
- A successful Nginx reload alone does not prove the application is healthy; check the live API version.
- The readiness endpoint is currently a placeholder and does not verify dependency health.
- The lab does not yet provide monitoring-triggered rollback, durable release history, or high availability.
- This is a local learning environment, not a production-hardened deployment service.
