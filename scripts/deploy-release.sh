#!/usr/bin/env bash

set -Eeuo pipefail

REGISTRY_URL="http://127.0.0.1:5000"
REGISTRY_HOST="localhost:5000"
IMAGE_NAME="pdp-api"
CONTAINER_NAME="pdp-managed-release"
HOST_PORT="8002"

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 VERSION" >&2
    exit 2
fi

VERSION="$1"

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: Version must use numeric MAJOR.MINOR.PATCH format." >&2
    exit 2
fi

IMAGE="${REGISTRY_HOST}/${IMAGE_NAME}:${VERSION}"
MANIFEST_URL="${REGISTRY_URL}/v2/${IMAGE_NAME}/manifests/${VERSION}"

echo "Requested release: ${VERSION}"
echo "Image: ${IMAGE}"

HTTP_STATUS=$(curl --silent --show-error \
    --output /dev/null \
    --write-out '%{http_code}' \
    --max-time 5 \
    --header 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json' \
    "$MANIFEST_URL") || {
        echo "ERROR: Could not contact the local registry." >&2
        exit 1
    }

if [[ "$HTTP_STATUS" != "200" ]]; then
    echo "ERROR: Version ${VERSION} was not found in the registry (HTTP ${HTTP_STATUS})." >&2
    exit 1
fi

if sudo docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    echo "ERROR: Container ${CONTAINER_NAME} already exists." >&2
    echo "Refusing to replace it automatically." >&2
    exit 1
fi

echo "Pulling ${IMAGE}..."
sudo docker pull "$IMAGE"

echo "Starting ${CONTAINER_NAME} on 127.0.0.1:${HOST_PORT}..."
sudo docker run --detach \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --publish "127.0.0.1:${HOST_PORT}:8000" \
    "$IMAGE"

echo "Running deployment validation..."

if ./scripts/validate-deployment.sh \
    "http://127.0.0.1:${HOST_PORT}" "$VERSION"; then
    echo "SUCCESS: Release ${VERSION} deployed and validated."
else
    echo "ERROR: Release validation failed. Removing the new container." >&2

    if sudo docker rm --force "$CONTAINER_NAME"; then
        echo "Cleanup complete. The failed managed container was removed." >&2
    else
        echo "WARNING: Could not remove ${CONTAINER_NAME}; inspect it manually." >&2
    fi

    exit 1
fi
