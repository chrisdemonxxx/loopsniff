#!/usr/bin/env bash
# Creates Secret Manager entries expected by deploy-cloud-run.sh for kliqboost-api,
# then grants the API Cloud Run service account secretAccessor on each.
#
# Usage (from repo root):
#   export DATABASE_URL_VALUE='postgresql+asyncpg://...'
#   export API_JWT_SECRET_VALUE='...'                  # long random string
#   export SYNC_KEY_VALUE='...'                       # worker sync / bootstrap key
#   export REDIS_URL_VALUE='redis://...'
#   bash infra/gcp/provision-api-secrets.sh
#
# Optional: PROJECT_ID, REGION (unused but kept for parity with deploy script),
# KLIQBOOST_API_SA (override API runtime SA email),
# FORCE_NEW_VERSION=1 to append a new version when the secret already exists
# (requires the matching *_VALUE to be set).
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-project-f36245f6-ac10-4013-a26}"
FORCE_NEW_VERSION="${FORCE_NEW_VERSION:-0}"

gcloud config set project "${PROJECT_ID}" >/dev/null

PROJ_NUM="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
COMPUTE_SA="${PROJ_NUM}-compute@developer.gserviceaccount.com"
API_SA="${COMPUTE_SA}"
if gcloud iam service-accounts describe "kliqboost-api-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project="${PROJECT_ID}" &>/dev/null; then
  API_SA="kliqboost-api-sa@${PROJECT_ID}.iam.gserviceaccount.com"
fi
API_SA="${KLIQBOOST_API_SA:-${API_SA}}"
>&2 echo "Using API service account for Secret Accessor: ${API_SA}"

_upsert_secret() {
  local id="$1"
  local env_name="$2"
  local val
  val="$(printenv "${env_name}" 2>/dev/null || true)"

  if gcloud secrets describe "${id}" --project="${PROJECT_ID}" &>/dev/null; then
    if [[ "${FORCE_NEW_VERSION}" == "1" ]]; then
      if [[ -z "${val}" ]]; then
        >&2 echo "FORCE_NEW_VERSION=1 requires ${env_name} to be set."
        exit 1
      fi
      >&2 echo "Adding new version to existing secret: ${id}"
      printf '%s' "${val}" | gcloud secrets versions add "${id}" --project="${PROJECT_ID}" --data-file=-
    else
      >&2 echo "Secret exists (skip): ${id}"
    fi
    return 0
  fi

  if [[ -z "${val}" ]]; then
    >&2 echo "Missing secret ${id} and ${env_name} is unset. Export ${env_name} and re-run."
    exit 1
  fi
  >&2 echo "Creating secret: ${id}"
  printf '%s' "${val}" | gcloud secrets create "${id}" \
    --project="${PROJECT_ID}" \
    --replication-policy="automatic" \
    --data-file=-
}

_upsert_secret "DATABASE_URL" "DATABASE_URL_VALUE"
_upsert_secret "API_JWT_SECRET" "API_JWT_SECRET_VALUE"
_upsert_secret "SYNC_KEY" "SYNC_KEY_VALUE"
_upsert_secret "REDIS_URL" "REDIS_URL_VALUE"

# Multi-channel auto-responder secrets (WA / Messenger / IG / LLM brain)
_upsert_secret "BASETEN_API_KEY" "BASETEN_API_KEY_VALUE"
_upsert_secret "WA_VERIFY_TOKEN" "WA_VERIFY_TOKEN_VALUE"
_upsert_secret "WA_APP_SECRET" "WA_APP_SECRET_VALUE"
_upsert_secret "WA_PHONE_NUMBER_ID" "WA_PHONE_NUMBER_ID_VALUE"
_upsert_secret "WA_ACCESS_TOKEN" "WA_ACCESS_TOKEN_VALUE"
_upsert_secret "MESSENGER_VERIFY_TOKEN" "MESSENGER_VERIFY_TOKEN_VALUE"
_upsert_secret "MESSENGER_PAGE_TOKEN" "MESSENGER_PAGE_TOKEN_VALUE"
_upsert_secret "META_APP_SECRET" "META_APP_SECRET_VALUE"
_upsert_secret "IG_PAGE_TOKEN" "IG_PAGE_TOKEN_VALUE"

API_SECRETS=(
  DATABASE_URL API_JWT_SECRET SYNC_KEY REDIS_URL
  BASETEN_API_KEY
  WA_VERIFY_TOKEN WA_APP_SECRET WA_PHONE_NUMBER_ID WA_ACCESS_TOKEN
  MESSENGER_VERIFY_TOKEN MESSENGER_PAGE_TOKEN META_APP_SECRET
  IG_PAGE_TOKEN
)

for SEC in "${API_SECRETS[@]}"; do
  gcloud secrets add-iam-policy-binding "${SEC}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${API_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet
done

>&2 echo "Done. ${API_SA} can read all API secrets (${#API_SECRETS[@]} total)."
>&2 echo "Next: bash infra/gcp/deploy-cloud-run.sh"
