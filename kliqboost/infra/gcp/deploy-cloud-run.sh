#!/usr/bin/env bash
set -euo pipefail

# Default project: Cloud Run is usable here (replace via PROJECT_ID for prod).
PROJECT_ID="${PROJECT_ID:-project-f36245f6-ac10-4013-a26}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-kliqboost}"
BOT_REPO="${BOT_REPO:-kliqboost}"
TAG="${TAG:-$(date +%Y%m%d-%H%M%S)}"
# Cloud SQL connection name, e.g. myproj:us-central1:myinstance — leave empty if none.
DB_INSTANCE="${DB_INSTANCE:-}"
# Serverless VPC connector (optional). Leave empty for API↔Cloud SQL via built-in connector.
VPC_CONNECTOR="${VPC_CONNECTOR:-}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Browser and worker-facing API URL. Default to the mapped custom domain so
# NEXT_PUBLIC_API_URL / API_BASE_URL are not raw *.run.app hosts (Safe Browsing
# and link reputation). For DNS bootstrap only: export PUBLIC_API_URL to the
# gcloud "status.url" value until api.kliqboost.store is live.
PUBLIC_API_URL="${PUBLIC_API_URL:-https://api.kliqboost.store}"
# User-facing origins for 301 away from default *.a.run.app hosts (Safe Browsing).
PUBLIC_SITE_URL="${PUBLIC_SITE_URL:-https://kliqboost.store}"
# Admin panel: intentionally NOT on a guessable subdomain. Set ADMIN_PUBLIC_HOST +
# ADMIN_PUBLIC_PATH (matching the admin middleware ADMIN_REQUIRED_PATH_PREFIX) to expose
# it publicly. If unset, no NEXTAUTH_URL override is applied and the admin runs on its
# internal Cloud Run URL — middleware still 404s anything outside the path prefix.
ADMIN_PUBLIC_HOST="${ADMIN_PUBLIC_HOST:-}"
ADMIN_PUBLIC_PATH="${ADMIN_PUBLIC_PATH:-}"
if [[ -n "${ADMIN_PUBLIC_HOST}" && -n "${ADMIN_PUBLIC_PATH}" ]]; then
  PUBLIC_ADMIN_URL="https://${ADMIN_PUBLIC_HOST}${ADMIN_PUBLIC_PATH}"
else
  PUBLIC_ADMIN_URL=""
fi
PUBLIC_PORTAL_URL="${PUBLIC_PORTAL_URL:-https://portal.kliqboost.store}"

gcloud config set project "${PROJECT_ID}" >/dev/null
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet >/dev/null

# Fail fast if Cloud Run API is blocked (e.g. CONSUMER_SUSPENDED) or IAM is insufficient.
if ! out="$(gcloud run services list --region "${REGION}" --project "${PROJECT_ID}" --limit=1 2>&1)"; then
  >&2 echo "❌ Cloud Run preflight failed — not proceeding with builds."
  >&2 echo "$out"
  >&2 echo ""
  >&2 echo "If you see CONSUMER_SUSPENDED: the project cannot use Cloud Run until Google/billing restores it (GCP Console → Support, or Billing)."
  >&2 echo "If you see Cloud Build bucket / serviceusage errors: grant roles (e.g. Service Usage Consumer, Cloud Build Editor) on the project."
  exit 1
fi

# Avoid long Cloud Build runs when Secret Manager is not populated (typical first-deploy failure).
_missing=0
for SEC in DATABASE_URL API_JWT_SECRET SYNC_KEY REDIS_URL; do
  if ! gcloud secrets describe "${SEC}" --project="${PROJECT_ID}" &>/dev/null; then
    >&2 echo "❌ Missing Secret Manager secret: ${SEC}"
    _missing=1
  fi
done
if [[ "${_missing}" -ne 0 ]]; then
  >&2 echo ""
  >&2 echo "Create them with real values, then redeploy:"
  >&2 echo "  export DATABASE_URL_VALUE=... API_JWT_SECRET_VALUE=... SYNC_KEY_VALUE=... REDIS_URL_VALUE=..."
  >&2 echo "  bash infra/gcp/provision-api-secrets.sh"
  exit 1
fi

_missing_workers=0
for SEC in TELEGRAM_BOT_TOKEN ADMIN_CHAT_ID OLLAMA_API_KEY TELEGRAM_API_ID TELEGRAM_API_HASH TG_PHONE TELEGRAM_STRING_SESSION \
  DEAL_ROOM_FALLBACK_INVITE DEAL_ROOM_FALLBACK_INVITE_2 DEAL_ROOM_FALLBACK_INVITE_3 KLIQBOOST_NEXTAUTH_SECRET TG_CLOUD_PASSWORD; do
  if ! gcloud secrets describe "${SEC}" --project="${PROJECT_ID}" &>/dev/null; then
    >&2 echo "❌ Missing Secret Manager secret: ${SEC}"
    _missing_workers=1
  fi
done
if [[ "${_missing_workers}" -ne 0 ]]; then
  >&2 echo ""
  >&2 echo "Create worker + NextAuth secrets:"
  >&2 echo "  bash infra/gcp/provision-worker-secrets.sh"
  >&2 echo "(Export *_VALUE env vars documented in that script.)"
  exit 1
fi

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
API_SA="$(_resolve_sa kliqboost-api-sa)"
BOT_SA="$(_resolve_sa kliqboost-bot-sa)"
USERBOT_SA="$(_resolve_sa kliqboost-userbot-sa)"
WEB_SA="$(_resolve_sa kliqboost-web-sa)"
API_SA="${KLIQBOOST_API_SA:-${API_SA}}"
BOT_SA="${KLIQBOOST_BOT_SA:-${BOT_SA}}"
USERBOT_SA="${KLIQBOOST_USERBOT_SA:-${USERBOT_SA}}"
WEB_SA="${KLIQBOOST_WEB_SA:-${WEB_SA}}"
>&2 echo "Using service accounts: API=${API_SA} BOT=${BOT_SA} USERBOT=${USERBOT_SA} WEB=${WEB_SA}"

build_image() {
  local name="$1"
  local context="$2"
  local config="${3:-}"
  local image="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${name}:${TAG}"
  >&2 echo "▶ Building ${name} from ${context}"
  if [ -n "${config}" ]; then
    gcloud builds submit "${context}" \
      --config "${config}" \
      --substitutions "_IMAGE=${image}" \
      --project "${PROJECT_ID}" >/dev/null
  else
    gcloud builds submit "${context}" --tag "${image}" --project "${PROJECT_ID}" >/dev/null
  fi
  echo "${image}"
}

deploy_service() {
  local service="$1"
  local image="$2"
  local sa="$3"
  local min_instances="$4"
  shift 4
  local -a netargs=()
  if [ -n "${VPC_CONNECTOR}" ]; then
    netargs+=(--vpc-connector "${VPC_CONNECTOR}")
  fi
  if [ -n "${DB_INSTANCE}" ]; then
    netargs+=(--set-cloudsql-instances "${DB_INSTANCE}")
  fi
  gcloud run deploy "${service}" \
    --image "${image}" \
    --region "${REGION}" \
    --platform managed \
    --service-account "${sa}" \
    --allow-unauthenticated \
    --min-instances "${min_instances}" \
    --max-instances 3 \
    --memory 1Gi \
    --cpu 1 \
    --port 8080 \
    "${netargs[@]}" \
    "$@" >/dev/null
  echo "✅ Deployed ${service}"
}

API_IMAGE="$(build_image kliqboost-api "${ROOT_DIR}" "${ROOT_DIR}/cloudbuild.api.yaml")"
BOT_IMAGE="$(build_image kliqboost-bot "${ROOT_DIR}" "${ROOT_DIR}/cloudbuild.bot.yaml")"
USERBOT_IMAGE="$(build_image kliqboost-autoresponder "${ROOT_DIR}" "${ROOT_DIR}/cloudbuild.userbot.yaml")"
WEB_IMAGE="$(build_image kliqboost-website "${ROOT_DIR}/web/kliqboost-website")"
ADMIN_IMAGE="$(build_image kliqboost-admin "${ROOT_DIR}/web/kliqboost-admin-panel")"
CLIENT_IMAGE="$(build_image kliqboost-client "${ROOT_DIR}/web/kliqboost-client-portal")"

# JWT must be env JWT_SECRET (see web/kliqboost-api/app/config.py), not JWT_SECRET_KEY.
deploy_service "kliqboost-api" "${API_IMAGE}" "${API_SA}" 1 \
  --set-env-vars APP_ENV=production \
  --set-secrets DATABASE_URL=DATABASE_URL:latest,JWT_SECRET=API_JWT_SECRET:latest,STATS_SYNC_KEY=SYNC_KEY:latest,REDIS_URL=REDIS_URL:latest,BASETEN_API_KEY=BASETEN_API_KEY:latest,WA_VERIFY_TOKEN=WA_VERIFY_TOKEN:latest,WA_APP_SECRET=WA_APP_SECRET:latest,WA_PHONE_NUMBER_ID=WA_PHONE_NUMBER_ID:latest,WA_ACCESS_TOKEN=WA_ACCESS_TOKEN:latest,MESSENGER_VERIFY_TOKEN=MESSENGER_VERIFY_TOKEN:latest,MESSENGER_PAGE_TOKEN=MESSENGER_PAGE_TOKEN:latest,META_APP_SECRET=META_APP_SECRET:latest,IG_PAGE_TOKEN=IG_PAGE_TOKEN:latest

API_URL="$(gcloud run services describe kliqboost-api --region "${REGION}" --format='value(status.url)')"

deploy_service "kliqboost-bot" "${BOT_IMAGE}" "${BOT_SA}" 1 \
  --set-env-vars API_BASE_URL="${PUBLIC_API_URL}",SECURITY_GUARDRAIL_MODE="${SECURITY_GUARDRAIL_MODE:-enforce_hard}" \
  --set-secrets BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,ADMIN_CHAT_ID=ADMIN_CHAT_ID:latest,STATS_SYNC_KEY=SYNC_KEY:latest,OLLAMA_CLOUD_API_KEY=OLLAMA_API_KEY:latest,DEAL_ROOM_FALLBACK_INVITE=DEAL_ROOM_FALLBACK_INVITE:latest,DEAL_ROOM_FALLBACK_INVITE_2=DEAL_ROOM_FALLBACK_INVITE_2:latest,DEAL_ROOM_FALLBACK_INVITE_3=DEAL_ROOM_FALLBACK_INVITE_3:latest

deploy_service "kliqboost-autoresponder" "${USERBOT_IMAGE}" "${USERBOT_SA}" 1 \
  --set-env-vars API_BASE_URL="${PUBLIC_API_URL}",SECURITY_GUARDRAIL_MODE="${SECURITY_GUARDRAIL_MODE:-enforce_hard}" \
  --set-secrets TG_API_ID=TELEGRAM_API_ID:latest,TG_API_HASH=TELEGRAM_API_HASH:latest,TG_PHONE=TG_PHONE:latest,TELEGRAM_STRING_SESSION=TELEGRAM_STRING_SESSION:latest,TG_CLOUD_PASSWORD=TG_CLOUD_PASSWORD:latest,ADMIN_CHAT_ID=ADMIN_CHAT_ID:latest,ADMIN_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,STATS_SYNC_KEY=SYNC_KEY:latest,OLLAMA_CLOUD_API_KEY=OLLAMA_API_KEY:latest,DEAL_ROOM_FALLBACK_INVITE=DEAL_ROOM_FALLBACK_INVITE:latest,DEAL_ROOM_FALLBACK_INVITE_2=DEAL_ROOM_FALLBACK_INVITE_2:latest,DEAL_ROOM_FALLBACK_INVITE_3=DEAL_ROOM_FALLBACK_INVITE_3:latest

deploy_service "kliqboost-website" "${WEB_IMAGE}" "${WEB_SA}" 0 \
  --set-env-vars NEXT_PUBLIC_API_URL="${PUBLIC_API_URL}",CANONICAL_SITE_ORIGIN="${PUBLIC_SITE_URL}"
# Admin: path-gated. Pass ADMIN_REQUIRED_PATH_PREFIX so middleware 404s probes; only set
# NEXTAUTH_URL / CANONICAL_SITE_ORIGIN when a public host has been chosen.
ADMIN_ENV_VARS="NEXT_PUBLIC_API_URL=${PUBLIC_API_URL},ADMIN_REQUIRED_PATH_PREFIX=${ADMIN_PUBLIC_PATH}"
if [[ -n "${PUBLIC_ADMIN_URL}" ]]; then
  ADMIN_ENV_VARS="${ADMIN_ENV_VARS},CANONICAL_SITE_ORIGIN=${PUBLIC_ADMIN_URL},NEXTAUTH_URL=${PUBLIC_ADMIN_URL}"
fi
deploy_service "kliqboost-admin" "${ADMIN_IMAGE}" "${WEB_SA}" 0 \
  --set-env-vars "${ADMIN_ENV_VARS}" \
  --set-secrets AUTH_SECRET=KLIQBOOST_NEXTAUTH_SECRET:latest
deploy_service "kliqboost-client" "${CLIENT_IMAGE}" "${WEB_SA}" 0 \
  --set-env-vars NEXT_PUBLIC_API_URL="${PUBLIC_API_URL}",CANONICAL_SITE_ORIGIN="${PUBLIC_PORTAL_URL}",NEXTAUTH_URL="${PUBLIC_PORTAL_URL}" \
  --set-secrets AUTH_SECRET=KLIQBOOST_NEXTAUTH_SECRET:latest

echo ""
echo "Cloud Run URLs (internal / debugging only — do not share in user-facing links):"
gcloud run services list --region "${REGION}" --format='table(metadata.name,status.url,status.traffic[0].percent)'
echo ""
echo "Public URLs: site=${PUBLIC_SITE_URL} admin=${PUBLIC_ADMIN_URL:-<internal-only>} portal=${PUBLIC_PORTAL_URL} api=${PUBLIC_API_URL}"

# --- Kliqboost ADK / MCP (optional) ---
# Build MCP images from repo root:
#   docker build -f agents/kliqboost/Dockerfile.mcp --build-arg MCP_MODULE=mcp_payment -t ... .
#   docker build -f agents/kliqboost/Dockerfile.mcp --build-arg MCP_MODULE=mcp_lead -t ... .
#   docker build -f agents/kliqboost/Dockerfile.mcp --build-arg MCP_MODULE=mcp_generate -t ... .
# Deploy Agent Engine (from workstation with ADC):
#   cd agents/kliqboost && adk deploy agent_engine --project="${PROJECT_ID}" --region="${REGION}" kliq_agent
# Then set on kliqboost-bot / kliqboost-autoresponder:
#   USE_ADK=1
#   GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=... GOOGLE_CLOUD_LOCATION=us-central1
#   VERTEX_AGENT_ENGINE_ID=...   # optional; else InMemorySessionService
# Remote MCP URLs (optional; if unset, stdio MCP is used when running adk web locally):
#   KLIQ_MCP_PAYMENT_URL= KLIQ_MCP_LEAD_URL= KLIQ_MCP_GENERATE_URL= KLIQ_MCP_BEARER_TOKEN=
# Pub/Sub bridge (optional):
#   USE_BRIDGE_PUBSUB=1
#   ./infra/gcp/provision_kliq_adk.sh
