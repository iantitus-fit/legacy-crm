#!/bin/bash
git push origin main && \
docker build --platform linux/amd64 -f Dockerfile.prod -t <your-registry>.azurecr.io/legacy-crm:latest . && \
az acr login --name <your-registry> && \
docker push <your-registry>.azurecr.io/legacy-crm:latest && \
az webapp restart --name legacy-crm --resource-group legacy-crm-prod
