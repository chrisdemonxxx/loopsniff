# Kliqboost QA Handoff — Quick Start

## Live URLs

| Service | URL |
|---------|-----|
| Admin Panel | https://kliqboost-admin.onrender.com |
| Client Portal | https://kliqboost-portal.onrender.com |
| Website | https://kliqboost-website.onrender.com |
| API | https://kliqboost-api.onrender.com |
| API Health | https://kliqboost-api.onrender.com/health |
| API Docs | https://kliqboost-api.onrender.com/docs |

---

## Test Credentials

| Role | Email | Password | Notes |
|------|-------|----------|-------|
| Admin | admin@kliqboost.test | AdminPass123! | Super-admin, full access |
| Admin (secondary) | manager@kliqboost.test | ManagerPass123! | Limited admin for team-mgmt tests |
| Client — Alice | alice@clienttest.test | ClientPass123! | Seeded wallet $500, active subscription |
| Client — Bob | bob@clienttest.test | ClientPass123! | Low balance, should show alert |
| Client — Carol | carol@clienttest.test | ClientPass123! | New account, empty state |

> **Note:** `.test` TLD addresses do not receive real emails. Use admin "force verify" or reset via DB if testing email flows.

---

## Running the Smoke Test

```bash
# Against production
bash scripts/qa-smoke.sh

# Against a custom URL
KLIQBOOST_API_URL=https://your-staging-api.onrender.com bash scripts/qa-smoke.sh
```

Requires: `curl`, `python3` (stdlib only). Returns exit code 0 on pass, 1 on any failure.

---

## Reseeding the Database

```bash
# Via Render shell (open from Render dashboard → kliqboost-api → Shell)
python -m app.seed_qa

# Locally (requires DATABASE_URL to point at the target DB)
DATABASE_URL=postgresql+asyncpg://... python -m app.seed_qa
```

---

## Filing Bugs

File issues at: **https://github.com/your-org/kliqboost/issues** *(update this URL before handoff)*

Label convention:
- `bug` — unexpected behaviour
- `qa-blocker` — blocks QA sign-off
- `known-issue` — see `QA/KNOWN-ISSUES.md` before filing

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| HTTP 401 on any endpoint | Token expired | Re-login to get a fresh token |
| HTTP 502 / connection refused | Render free-tier cold start | Wait 30 s then retry |
| Login returns "User not found" | DB not seeded | Run `python -m app.seed_qa` |
| Email not received | `.test` TLD bounces | Use admin force-verify or DB reset |
| AI chat falls back to canned message | `OLLAMA_CLOUD_KEY` not set in Render | Set key in Render env dashboard |
| Meta toggles don't reach Facebook | `META_API_LIVE=false` | By design for QA — see KNOWN-ISSUES |
