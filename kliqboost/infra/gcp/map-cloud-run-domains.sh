#!/usr/bin/env bash
# Create Cloud Run domain mappings (after deploy). DNS at registrar must allow adding Google records.
# Hostinger: use the resourceRecords from `gcloud beta run domain-mappings describe` output (usually CNAME to ghs.googlehosted.com).
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-project-f36245f6-ac10-4013-a26}"
REGION="${REGION:-us-central1}"

gcloud config set project "${PROJECT_ID}" >/dev/null

try_map() {
  local svc="$1"
  local dom="$2"
  local out
  set +e
  out="$(gcloud beta run domain-mappings create \
    --service="${svc}" \
    --domain="${dom}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --quiet 2>&1)"
  local code=$?
  set -e
  if [[ "${code}" -eq 0 ]]; then
    >&2 echo "created: ${dom} -> ${svc}"
    return 0
  fi
  if echo "${out}" | grep -qiE 'already exists|Already exists|409|Conflict'; then
    >&2 echo "exists: ${dom} -> ${svc}"
    return 0
  fi
  >&2 echo "${out}"
  return "${code}"
}

try_map kliqboost-api api.kliqboost.store
try_map kliqboost-website kliqboost.store
try_map kliqboost-website www.kliqboost.store
try_map kliqboost-client portal.kliqboost.store

# Admin panel is intentionally NOT given a guessable subdomain (e.g. admin.*, kb-admin.*).
# Ops can opt-in to a public host by exporting BOTH:
#   ADMIN_PUBLIC_HOST  — fully-qualified hostname (e.g. console-7f3a.kliqboost.store)
#   ADMIN_PUBLIC_PATH  — required obfuscation prefix served by the admin middleware
#                        (e.g. /_internal/console-7f3a). Required so a bare host probe 404s.
# If either is empty, NO domain mapping is created and the admin is reachable only via the
# internal Cloud Run service URL inside the GCP project.
ADMIN_PUBLIC_HOST="${ADMIN_PUBLIC_HOST:-}"
ADMIN_PUBLIC_PATH="${ADMIN_PUBLIC_PATH:-}"
if [[ -n "${ADMIN_PUBLIC_HOST}" && -n "${ADMIN_PUBLIC_PATH}" ]]; then
  >&2 echo "admin: mapping ${ADMIN_PUBLIC_HOST} (path-gated at ${ADMIN_PUBLIC_PATH})"
  try_map kliqboost-admin "${ADMIN_PUBLIC_HOST}"
else
  >&2 echo "admin: skipping public domain mapping (ADMIN_PUBLIC_HOST / ADMIN_PUBLIC_PATH not set)"
fi

try_map kliqboost-website bisonclick.agency
try_map kliqboost-website www.bisonclick.agency
try_map kliqboost-website bisonclick.shop
try_map kliqboost-website www.bisonclick.shop

set +e
try_map kliqboost-bot bot.kliqboost.store || >&2 echo "Note: bot custom domain may be unsupported for workers; ignore if failed."
try_map kliqboost-autoresponder auto.kliqboost.store || >&2 echo "Note: autoresponder custom domain may be unsupported; ignore if failed."
set -e

>&2 echo ""
gcloud beta run domain-mappings list --region="${REGION}" --project="${PROJECT_ID}" --format='table(metadata.name,status.resourceRecords)'
