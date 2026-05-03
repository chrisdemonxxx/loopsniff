#!/usr/bin/env bash
# Creates Secret Manager entries for Cloud Run workers + NextAuth (no Render).
# Run after provision-api-secrets.sh (SYNC_KEY must exist).
#
# Required env vars (or secrets already present):
#   TELEGRAM_BOT_TOKEN_VALUE, ADMIN_CHAT_ID_VALUE, OLLAMA_API_KEY_VALUE
#   TELEGRAM_API_ID_VALUE, TELEGRAM_API_HASH_VALUE, TG_PHONE_VALUE, TELEGRAM_STRING_SESSION_VALUE
#   DEAL_ROOM_FALLBACK_INVITE_VALUE, _2, _3 (may be same Telegram invite URL)
#   KLIQBOOST_NEXTAUTH_SECRET_VALUE  (openssl rand -base64 32)
# Optional:
#   TG_CLOUD_PASSWORD_VALUE (Telegram 2FA cloud password; use "-" if unused)
#   KLIQBOOST_*_SA overrides (same as deploy script)
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-project-f36245f6-ac10-4013-a26}"
FORCE_NEW_VERSION="${FORCE_NEW_VERSION:-0}"

gcloud config set project "${PROJECT_ID}" >/dev/null

PROJ_NUM="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
COMPUTE_SA="${PROJ_NUM}-compute@developer.gserviceaccount.com"

_resolve_sa() {
  local name="$1"
  local email="${name}@${PROJECT_ID}.iam.gserviceaccount.com"
  if gcloud iam service-accounts describe "${email}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "${email}"
  else
    echo "${COMPUTE_SA}"
  fi
}

BOT_SA="${KLIQBOOST_BOT_SA:-$(_resolve_sa kliqboost-bot-sa)}"
USERBOT_SA="${KLIQBOOST_USERBOT_SA:-$(_resolve_sa kliqboost-userbot-sa)}"
WEB_SA="${KLIQBOOST_WEB_SA:-$(_resolve_sa kliqboost-web-sa)}"

>&2 echo "Bindings: BOT=${BOT_SA} USERBOT=${USERBOT_SA} WEB=${WEB_SA}"

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
      printf '%s' "${val}" | gcloud secrets versions add "${id}" --project="${PROJECT_ID}" --data-file=-
    else
      >&2 echo "Secret exists (skip): ${id}"
    fi
    return 0
  fi

  if [[ -z "${val}" ]]; then
    >&2 echo "Missing secret ${id}: export ${env_name}=... and re-run."
    exit 1
  fi
  printf '%s' "${val}" | gcloud secrets create "${id}" \
    --project="${PROJECT_ID}" \
    --replication-policy="automatic" \
    --data-file=-
}

_grant() {
  local sec="$1"
  local sa="$2"
  gcloud secrets add-iam-policy-binding "${sec}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${sa}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet &>/dev/null || true
}

_upsert_secret "TELEGRAM_BOT_TOKEN" "TELEGRAM_BOT_TOKEN_VALUE"
_upsert_secret "ADMIN_CHAT_ID" "ADMIN_CHAT_ID_VALUE"
_upsert_secret "OLLAMA_API_KEY" "OLLAMA_API_KEY_VALUE"
_upsert_secret "TELEGRAM_API_ID" "TELEGRAM_API_ID_VALUE"
_upsert_secret "TELEGRAM_API_HASH" "TELEGRAM_API_HASH_VALUE"
_upsert_secret "TG_PHONE" "TG_PHONE_VALUE"
_upsert_secret "TELEGRAM_STRING_SESSION" "TELEGRAM_STRING_SESSION_VALUE"
_upsert_secret "DEAL_ROOM_FALLBACK_INVITE" "DEAL_ROOM_FALLBACK_INVITE_VALUE"
_upsert_secret "DEAL_ROOM_FALLBACK_INVITE_2" "DEAL_ROOM_FALLBACK_INVITE_2_VALUE"
_upsert_secret "DEAL_ROOM_FALLBACK_INVITE_3" "DEAL_ROOM_FALLBACK_INVITE_3_VALUE"
_upsert_secret "KLIQBOOST_NEXTAUTH_SECRET" "KLIQBOOST_NEXTAUTH_SECRET_VALUE"

# Optional Telegram 2FA — placeholder avoids empty optional secret in Cloud Run
if [[ -n "${TG_CLOUD_PASSWORD_VALUE:-}" ]]; then
  _upsert_secret "TG_CLOUD_PASSWORD" "TG_CLOUD_PASSWORD_VALUE"
elif ! gcloud secrets describe "TG_CLOUD_PASSWORD" --project="${PROJECT_ID}" &>/dev/null; then
  printf '%s' "-" | gcloud secrets create "TG_CLOUD_PASSWORD" \
    --project="${PROJECT_ID}" \
    --replication-policy="automatic" \
    --data-file=-
  >&2 echo "Created TG_CLOUD_PASSWORD placeholder (-); replace later if 2FA password is required."
fi

# Ensure SYNC_KEY exists before granting (created by provision-api-secrets.sh)
if ! gcloud secrets describe "SYNC_KEY" --project="${PROJECT_ID}" &>/dev/null; then
  >&2 echo "⚠️ SYNC_KEY not found in Secret Manager. Creating placeholder."
  printf '%s' "kliq-stats-2026-xK9m" | gcloud secrets create "SYNC_KEY" \
    --project="${PROJECT_ID}" \
    --replication-policy="automatic" \
    --data-file=-
fi

for SEC in TELEGRAM_BOT_TOKEN ADMIN_CHAT_ID OLLAMA_API_KEY DEAL_ROOM_FALLBACK_INVITE DEAL_ROOM_FALLBACK_INVITE_2 DEAL_ROOM_FALLBACK_INVITE_3 SYNC_KEY; do
  _grant "${SEC}" "${BOT_SA}"
done

for SEC in TELEGRAM_BOT_TOKEN ADMIN_CHAT_ID OLLAMA_API_KEY TELEGRAM_API_ID TELEGRAM_API_HASH TG_PHONE TELEGRAM_STRING_SESSION DEAL_ROOM_FALLBACK_INVITE DEAL_ROOM_FALLBACK_INVITE_2 DEAL_ROOM_FALLBACK_INVITE_3 SYNC_KEY TG_CLOUD_PASSWORD; do
  _grant "${SEC}" "${USERBOT_SA}"
done

_grant "KLIQBOOST_NEXTAUTH_SECRET" "${WEB_SA}"

>&2 echo "Done. Next: export DB_INSTANCE=... && bash infra/gcp/deploy-cloud-run.sh"
