#!/bin/bash
# Build, push and restart the production app on Azure.
# Usage: ACR_NAME=<registry> WEB_APP_NAME=<web-app> RESOURCE_GROUP=<resource-group> ./scripts/deploy.sh
set -euo pipefail
: "${ACR_NAME:?Set ACR_NAME to your Azure Container Registry name}"
: "${WEB_APP_NAME:?Set WEB_APP_NAME to your Azure web app name}"
: "${RESOURCE_GROUP:?Set RESOURCE_GROUP to your Azure resource group}"
IMAGE="${ACR_NAME}.azurecr.io/legacy-crm:latest"

git push origin main
docker build --platform linux/amd64 -f Dockerfile.prod -t "$IMAGE" .
az acr login --name "$ACR_NAME"
docker push "$IMAGE"
az webapp restart --name "$WEB_APP_NAME" --resource-group "$RESOURCE_GROUP"
