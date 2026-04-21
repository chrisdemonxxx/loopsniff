# Known Issues — QA Do-Not-File List

Items in this file are **deliberate design decisions or known deferred work**.
QA team: do **NOT** file bug tickets for these. Reference this document when triaging.

---

## 1. Meta Graph API in Stub Mode

**Symptom:** Campaign/ad-set/ad status toggles update the Kliqboost database but changes do **not** propagate to the real Meta Marketing API.

**Reason:** `META_API_LIVE=false` in Render environment. This is intentional for QA — it prevents accidental spend on real ad accounts.

**Impact:** All toggle and bulk-action tests are valid (they test our persistence layer). Impressions/spend reported in the UI are seeded/mock values.

**Resolution path:** Set `META_API_LIVE=true` in Render dashboard when going live with real advertiser accounts.

---

## 2. Login Rate Limiter — In-Memory Only

**Symptom:** Brute-force login rate limiting may behave inconsistently across Render restarts or if Render scales to >1 instance.

**Reason:** The rate limiter state is stored in process memory (`defaultdict` in `app/auth/routes.py`), not in Redis or a shared store.

**Impact:** A fresh Render deploy resets lockout counters. On free tier (single instance) this is mostly fine; on paid plans with horizontal scaling, lockout would only apply per-replica.

**Resolution path:** Migrate rate-limit state to Redis before production at scale.

---

## 3. Outreach DB — File-Based SQLite

**Symptom:** Outreach campaigns, leads, and sequence features may return empty results or 500 errors on Render.

**Reason:** `OUTREACH_DB_PATH` defaults to a local filesystem path (`/home/cjs/tgacc/bulk-account-creator/...`). Render ephemeral filesystem does not persist this file across deploys.

**Impact:** Outreach section is non-functional in deployed environments unless a persistent disk is attached and the path updated.

**Resolution path:** Either attach Render Disk to the API service and set `OUTREACH_DB_PATH` to a path on that disk, or migrate outreach data to PostgreSQL.

---

## 4. RAG / AI Chat Fallback

**Symptom:** AI assistant in chat replies with a generic canned message ("I'm unable to assist right now…") instead of context-aware responses.

**Reason:** `OLLAMA_CLOUD_KEY` is not set in the Render environment. The AI service catches the auth failure and returns the fallback string.

**Impact:** AI chat is non-functional until the key is configured. All other chat features (send/receive, history, escalation) work normally.

**Resolution path:** Obtain an Ollama Cloud key and set `OLLAMA_CLOUD_KEY` + `OLLAMA_CLOUD_URL` in the Render env dashboard for `kliqboost-api`.

---

## 5. Email Deliverability — `.test` TLD

**Symptom:** Verification emails, password reset emails, and alert emails are not received by test accounts.

**Reason:** All QA seed credentials use the `.test` TLD (e.g., `alice@clienttest.test`), which is reserved and not routable on the public internet. SMTP servers reject delivery.

**Impact:** Cannot test email flows end-to-end with QA credentials.

**Workarounds:**
- Use admin panel "Force Verify" action on a user to bypass email verification.
- Reset password directly via DB: `UPDATE client_users SET email_verified=true WHERE email='alice@clienttest.test';`
- For reset-password flow testing, use a real email address in a separate test user created manually.

---

## 6. Chat History Tab — Work In Progress

**Symptom:** "Chat History" tab (or equivalent archived-conversations view) may be missing, empty, or show a placeholder.

**Status:** Feature is in development; not yet implemented in this release.

**Do not file:** Missing history tab, blank history view.

---

## 7. Team Management — Partial Implementation

**Symptom:** Invite Team Member flow may not send emails or may show a stub confirmation.

**Status:** Email delivery for team invites depends on SendGrid being configured (`SENDGRID_API_KEY` set in Render). Without it, the invite is written to the DB but no email is dispatched.

**Do not file:** "Invite email not received" as a bug — this is a configuration gap, not a code bug.

---

## 8. Render Free-Tier Cold Starts

**Symptom:** First request after ~15 minutes of inactivity returns HTTP 502 or times out.

**Reason:** Render free-tier services spin down when idle.

**Do not file:** 502 or "service unavailable" on first load after idle period. Wait 30 seconds and retry.

---

## 9. CORS on WebSocket (Chat)

**Symptom:** Chat WebSocket may fail to connect from `localhost:3000` or `localhost:3001` in local dev if the API CORS config does not include those origins.

**Reason:** `CORS_ALLOW_ORIGINS` in render.yaml is set to Render production URLs only. Local dev requires `.env` override.

**Do not file** as a production bug — only affects local development environment.
