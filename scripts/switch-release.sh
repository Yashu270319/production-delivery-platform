#!/usr/bin/env bash

set -Eeuo pipefail

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_FILE="${BASE_DIR}/proxy/active-backend.conf"
PROXY_CONTAINER="pdp-proxy"
PROXY_URL="http://127.0.0.1:8080"

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 VERSION (supported: 1.0.0 or 1.0.1)" >&2
    exit 2
fi

VERSION="$1"

case "$VERSION" in
    1.0.0)
        CONTAINER="pdp-managed-release"
        HOST_PORT="8002"
        ;;
    1.0.1)
        CONTAINER="pdp-release-1.0.1"
        HOST_PORT="8001"
        ;;
    *)
        echo "ERROR: Unsupported release: ${VERSION}" >&2
        exit 2
        ;;
esac

if [[ ! -f "$BACKEND_FILE" ]]; then
    echo "ERROR: Backend configuration not found: ${BACKEND_FILE}" >&2
    exit 1
fi

echo "Requested release: ${VERSION}"
echo "Candidate container: ${CONTAINER}"

# Confirm that the proxy's current configuration is valid.
if ! sudo docker exec "$PROXY_CONTAINER" nginx -t; then
    echo "ERROR: Existing Nginx configuration is invalid; refusing to switch." >&2
    exit 1
fi

# Confirm the candidate is running.
if ! sudo docker container inspect "$CONTAINER" \
    --format '{{.State.Running}}' 2>/dev/null | grep -qx true; then
    echo "ERROR: Candidate container is not running." >&2
    exit 1
fi

# Validate the candidate directly before changing traffic.
if ! "${BASE_DIR}/scripts/validate-deployment.sh" \
    "http://127.0.0.1:${HOST_PORT}" "$VERSION"; then
    echo "ERROR: Candidate validation failed; traffic was not changed." >&2
    exit 1
fi

# Keep backup and temporary files on the same filesystem as the config.
BACKUP_FILE="$(mktemp "${BASE_DIR}/proxy/.active-backend.backup.XXXXXX")"
TEMP_FILE=""

cp -p -- "$BACKEND_FILE" "$BACKUP_FILE"

SWITCH_IN_PROGRESS=0

cleanup() {
    if [[ -n "$TEMP_FILE" ]]; then
        rm -f -- "$TEMP_FILE"
    fi
    rm -f -- "$BACKUP_FILE"
}
trap cleanup EXIT

restore_previous() {
    echo "Restoring previous backend configuration..." >&2

    local restore_file
    restore_file="$(mktemp "${BASE_DIR}/proxy/.active-backend.restore.XXXXXX")"

    if ! cp -- "$BACKUP_FILE" "$restore_file"; then
        rm -f -- "$restore_file"
        echo "CRITICAL: Could not prepare the previous configuration." >&2
        return 1
    fi

    if ! chmod --reference="$BACKUP_FILE" "$restore_file"; then
        rm -f -- "$restore_file"
        echo "CRITICAL: Could not preserve configuration permissions." >&2
        return 1
    fi

    if ! mv -f -- "$restore_file" "$BACKEND_FILE"; then
        rm -f -- "$restore_file"
        echo "CRITICAL: Could not restore the previous configuration file." >&2
        return 1
    fi

    if sudo docker exec "$PROXY_CONTAINER" nginx -t &&
       sudo docker exec "$PROXY_CONTAINER" nginx -s reload; then
        echo "Previous backend configuration restored." >&2
        SWITCH_IN_PROGRESS=0
        return 0
    fi

    echo "CRITICAL: Restoration reload failed. Inspect Nginx immediately." >&2
    return 1
}

handle_signal() {
    local signal="$1"
    local exit_code=130

    [[ "$signal" == "TERM" ]] && exit_code=143

    trap - INT TERM
    echo "ERROR: Received ${signal}; attempting rollback if needed." >&2

    if [[ "$SWITCH_IN_PROGRESS" -eq 1 ]]; then
        restore_previous || true
    fi

    exit "$exit_code"
}
trap 'handle_signal INT' INT
trap 'handle_signal TERM' TERM

# Prepare the new configuration separately.
TEMP_FILE="$(mktemp "${BASE_DIR}/proxy/.active-backend.new.XXXXXX")"

printf 'upstream pdp_backend {\n    server %s:8000;\n}\n' \
    "$CONTAINER" > "$TEMP_FILE"

chmod --reference="$BACKEND_FILE" "$TEMP_FILE"

# Mark the transaction before changing the active file.
SWITCH_IN_PROGRESS=1

# Atomic replacement: both files are on the same filesystem.
if ! mv -f -- "$TEMP_FILE" "$BACKEND_FILE"; then
    echo "ERROR: Could not install the new backend configuration." >&2
    exit 1
fi
TEMP_FILE=""

# Validate before reloading the proxy.
if ! sudo docker exec "$PROXY_CONTAINER" nginx -t; then
    echo "ERROR: New Nginx configuration is invalid." >&2
    restore_previous || true
    exit 1
fi

if ! sudo docker exec "$PROXY_CONTAINER" nginx -s reload; then
    echo "ERROR: Nginx reload failed." >&2
    restore_previous || true
    exit 1
fi

# Verify that proxy traffic reaches the requested release.
ACTUAL_VERSION=""

for attempt in {1..5}; do
    ACTUAL_VERSION="$(curl --silent --show-error --fail --max-time 3 \
        "${PROXY_URL}/version" 2>/dev/null || true)"

    if EXPECTED_VERSION="$VERSION" ACTUAL_RESPONSE="$ACTUAL_VERSION" \
        python3 -c '
import json
import os
import sys

try:
    actual = json.loads(os.environ["ACTUAL_RESPONSE"]).get("version")
except (json.JSONDecodeError, AttributeError):
    sys.exit(1)

sys.exit(0 if actual == os.environ["EXPECTED_VERSION"] else 1)
'; then
        SWITCH_IN_PROGRESS=0
        echo "SUCCESS: Traffic now reaches release ${VERSION}."
        exit 0
    fi

    sleep 1
done

echo "ERROR: Proxy did not serve expected version ${VERSION}." >&2
restore_previous || true
exit 1
