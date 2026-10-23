#!/usr/bin/env bash

set -Eeuo pipefail

BASE_URL="${1:-http://127.0.0.1:8001}"
EXPECTED_VERSION="${2:?Usage: $0 BASE_URL EXPECTED_VERSION}"

check_http() {
    local endpoint="$1"

    if ! curl --silent --show-error --fail --max-time 5 \
        "${BASE_URL}${endpoint}"; then
        echo "FAIL: ${endpoint} did not return a successful HTTP response." >&2
        return 1
    fi
}

echo "Validating deployment at ${BASE_URL}"
echo "Expected version: ${EXPECTED_VERSION}"

LIVE_RESPONSE=$(check_http "/health/live") || exit 1
if [[ "$LIVE_RESPONSE" != '{"status":"alive"}' ]]; then
    echo "FAIL: Unexpected liveness response: ${LIVE_RESPONSE}" >&2
    exit 1
fi
echo "PASS: Liveness check"

VERSION_RESPONSE=$(check_http "/version") || exit 1
if ! EXPECTED_VERSION="$EXPECTED_VERSION" VERSION_RESPONSE="$VERSION_RESPONSE" \
    python3 -c '
import json
import os
import sys

try:
    data = json.loads(os.environ["VERSION_RESPONSE"])
except json.JSONDecodeError:
    sys.exit("FAIL: Version endpoint returned invalid JSON.")

expected = os.environ["EXPECTED_VERSION"]
actual = data.get("version")

if actual != expected:
    sys.exit(f"FAIL: Expected version {expected}, received {actual}.")
'; then
    exit 1
fi
echo "PASS: Version check (${EXPECTED_VERSION})"

READY_RESPONSE=$(check_http "/health/ready") || exit 1
if [[ "$READY_RESPONSE" != '{"status":"ready"}' ]]; then
    echo "FAIL: Unexpected readiness response: ${READY_RESPONSE}" >&2
    exit 1
fi
echo "PASS: Readiness endpoint check"

echo "SUCCESS: Deployment validation passed."
