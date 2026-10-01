#!/usr/bin/env bash
#
# Dump the Legacy CRM production PostgreSQL database to a local file.
#
# Usage:
#   WEB_APP_NAME=<your-web-app> RESOURCE_GROUP=<your-resource-group> ./scripts/dump_prod_db.sh
#
# Requirements:
#   - Azure CLI logged in (az login)
#   - EITHER pg_dump installed locally (brew install libpq && brew link --force libpq)
#     OR Docker running (the script will pull postgres:16-alpine if needed)
#
# The script reads DATABASE_URL from the Azure Web App configuration at
# runtime, so no credentials are stored in the repo. Dumps are written to
# db_backups/ which is gitignored.
#
# Before running a destructive data migration:
#   1. Run this script
#   2. Verify the dump file is non-empty and recent
#   3. Proceed with the migration
#
# To restore:
#   psql "$DATABASE_URL" < db_backups/legacy_crm_<timestamp>.sql
#
set -euo pipefail

WEB_APP_NAME="${WEB_APP_NAME:?Set WEB_APP_NAME to your Azure web app name}"
RESOURCE_GROUP="${RESOURCE_GROUP:?Set RESOURCE_GROUP to your Azure resource group}"
BACKUP_DIR="$(dirname "$0")/../db_backups"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
OUTFILE="${BACKUP_DIR}/legacy_crm_${TIMESTAMP}.sql"

mkdir -p "${BACKUP_DIR}"

if ! command -v az >/dev/null 2>&1; then
  echo "ERROR: az CLI not found. Install from https://docs.microsoft.com/cli/azure/install-azure-cli" >&2
  exit 1
fi

USE_DOCKER=0
if ! command -v pg_dump >/dev/null 2>&1; then
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "pg_dump not found locally — falling back to Docker postgres:16-alpine"
    USE_DOCKER=1
  else
    echo "ERROR: pg_dump not found and Docker is not running." >&2
    echo "Install pg_dump with 'brew install libpq && brew link --force libpq'" >&2
    echo "or start Docker Desktop." >&2
    exit 1
  fi
fi

echo "Fetching DATABASE_URL from Azure Web App config..."
DATABASE_URL="$(az webapp config appsettings list \
  --name "${WEB_APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query "[?name=='DATABASE_URL'].value" \
  -o tsv)"

if [[ -z "${DATABASE_URL}" ]]; then
  echo "ERROR: Could not read DATABASE_URL from Web App settings." >&2
  exit 1
fi

# FastAPI uses 'postgresql+psycopg://' but pg_dump wants plain 'postgresql://'
PG_URL="${DATABASE_URL/postgresql+psycopg:\/\//postgresql:\/\/}"

echo "Dumping production database to ${OUTFILE}..."
if [[ "${USE_DOCKER}" == "1" ]]; then
  docker run --rm -e PGURL="${PG_URL}" postgres:16-alpine \
    pg_dump --no-owner --no-acl --clean --if-exists "${PG_URL}" > "${OUTFILE}"
else
  pg_dump --no-owner --no-acl --clean --if-exists "${PG_URL}" > "${OUTFILE}"
fi

SIZE="$(du -h "${OUTFILE}" | cut -f1)"
LINES="$(wc -l < "${OUTFILE}")"
echo ""
echo "Dump complete."
echo "  File: ${OUTFILE}"
echo "  Size: ${SIZE}"
echo "  Lines: ${LINES}"
echo ""
echo "To restore later:"
echo "  psql \"\$DATABASE_URL\" < ${OUTFILE}"
