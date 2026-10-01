#!/usr/bin/env bash
set -euo pipefail

# Azure Container Registry
ACR_LOGIN_SERVER="${ACR_LOGIN_SERVER:?Set ACR_LOGIN_SERVER, e.g. myregistry.azurecr.io}"
IMAGE_NAME="legacy-crm"
TAG="${1:-latest}"

echo "Building production image (linux/amd64)..."
# Use buildx with explicit platform — `docker build --platform` is silently
# ignored on Apple Silicon when buildx is the default driver, which produces
# an arm64 image that Azure App Service (amd64) can't pull. --provenance=false
# keeps the manifest as a single-arch image instead of an OCI image index.
docker buildx build \
    --platform linux/amd64 \
    --provenance=false \
    --output type=docker \
    -f Dockerfile.prod \
    -t "${IMAGE_NAME}:${TAG}" \
    -t "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${TAG}" \
    .

echo "Pushing to ACR..."
# buildx already tagged for the registry; no separate `docker tag` step needed.
docker push "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${TAG}"

echo "Done! Image pushed: ${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${TAG}"
