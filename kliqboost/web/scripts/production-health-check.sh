#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-https://kliqboost-api.onrender.com}"
ADMIN_URL="${ADMIN_URL:-https://kliqboost-admin.onrender.com}"
PORTAL_URL="${PORTAL_URL:-https://kliqboost-portal.onrender.com}"
WEBSITE_URL="${WEBSITE_URL:-https://kliqboost-website.onrender.com}"

PASS=0
FAIL=0

check_http() {
  local name="$1"
  local url="$2"
  local expected="${3:-200}"
  local code
  code="$(curl -s -o /tmp/kb_health_resp.txt -w "%{http_code}" "$url" || echo "000")"
  if [[ "$code" == "$expected" ]] || [[ "$code" =~ ^30[1278]$ ]]; then
    echo "  ✅ $name ($code)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name expected $expected got $code"
    FAIL=$((FAIL + 1))
  fi
}

echo "▶ Public service checks"
check_http "API health" "$API_URL/health"
check_http "API docs" "$API_URL/docs"
check_http "Admin portal" "$ADMIN_URL"
check_http "Client portal" "$PORTAL_URL"
check_http "Website" "$WEBSITE_URL"

echo
echo "▶ Auth check"
LOGIN_CODE="$(curl -s -o /tmp/kb_login_resp.json -w "%{http_code}" -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"superadmin@kliqboost.store","password":"SuperAdmin2026!"}')"
if [[ "$LOGIN_CODE" == "200" ]]; then
  echo "  ✅ Admin login API (200)"
  PASS=$((PASS + 1))
else
  echo "  ❌ Admin login API expected 200 got $LOGIN_CODE"
  FAIL=$((FAIL + 1))
fi

echo
echo "RESULT: $PASS passed / $FAIL failed"
[[ "$FAIL" -eq 0 ]]
