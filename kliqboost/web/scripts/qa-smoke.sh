#!/usr/bin/env bash
# Kliqboost API smoke test
# Usage: KLIQBOOST_API_URL=https://... bash scripts/qa-smoke.sh
set -euo pipefail

BASE_URL="${KLIQBOOST_API_URL:-https://kliqboost-api.onrender.com}"
PASS=0
FAIL=0

pass() { echo "  ✅ $1"; PASS=$((PASS+1)); }
fail() { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

step() { echo; echo "▶ $1"; }

assert_status() {
  local label="$1" expected="$2" actual="$3"
  if [ "$actual" = "$expected" ]; then
    pass "$label (HTTP $actual)"
  else
    fail "$label — expected HTTP $expected, got HTTP $actual"
    return 1
  fi
}

# ── Step 1: Health check ──────────────────────────────────────────────────────
step "Health check"
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
assert_status "GET /health" "200" "$HEALTH_STATUS"

# ── Step 2: Admin login ───────────────────────────────────────────────────────
step "Admin login (admin@kliqboost.test)"
ADMIN_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@kliqboost.test","password":"AdminPass123!"}')
ADMIN_STATUS=$(echo "$ADMIN_RESP" | tail -1)
ADMIN_BODY=$(echo "$ADMIN_RESP" | head -1)
assert_status "POST /auth/login (admin)" "200" "$ADMIN_STATUS"

ADMIN_TOKEN=$(echo "$ADMIN_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || echo "")
if [ -z "$ADMIN_TOKEN" ]; then
  fail "Could not extract access_token from admin login response"
  echo "    Response body: $ADMIN_BODY"
else
  pass "Admin access_token extracted"
fi

# ── Step 3: Admin clients list ────────────────────────────────────────────────
step "Admin clients list"
CLIENTS_RESP=$(curl -s -w "\n%{http_code}" "$BASE_URL/clients" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
CLIENTS_STATUS=$(echo "$CLIENTS_RESP" | tail -1)
CLIENTS_BODY=$(echo "$CLIENTS_RESP" | head -1)
assert_status "GET /clients (admin)" "200" "$CLIENTS_STATUS"

CLIENT_COUNT=$(echo "$CLIENTS_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo "0")
if [ "$CLIENT_COUNT" -gt 0 ] 2>/dev/null; then
  pass "Client list non-empty ($CLIENT_COUNT clients)"
else
  fail "Client list is empty or not an array"
fi

# ── Step 4: Client login ──────────────────────────────────────────────────────
step "Client login (alice@clienttest.test)"
CLIENT_RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@clienttest.test","password":"ClientPass123!"}')
CLIENT_STATUS=$(echo "$CLIENT_RESP" | tail -1)
CLIENT_BODY=$(echo "$CLIENT_RESP" | head -1)
assert_status "POST /auth/login (client)" "200" "$CLIENT_STATUS"

CLIENT_TOKEN=$(echo "$CLIENT_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || echo "")
if [ -z "$CLIENT_TOKEN" ]; then
  fail "Could not extract access_token from client login response"
  echo "    Response body: $CLIENT_BODY"
else
  pass "Client access_token extracted"
fi

# ── Step 5: Client wallet / dashboard ────────────────────────────────────────
step "Client wallet dashboard (GET /wallet)"
WALLET_RESP=$(curl -s -w "\n%{http_code}" "$BASE_URL/wallet" \
  -H "Authorization: Bearer $CLIENT_TOKEN")
WALLET_STATUS=$(echo "$WALLET_RESP" | tail -1)
assert_status "GET /wallet (client)" "200" "$WALLET_STATUS"

# ── Summary ───────────────────────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════"
echo "  Smoke test complete: $PASS passed, $FAIL failed"
echo "═══════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
