# Client Portal — QA Checklist

All tests performed logged in as the named client.
Switch between Alice / Bob / Carol to verify per-user isolation.
Seed data must be loaded first (`python -m app.seed_qa`).

---

## 1. Login

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Alice login | Visit `/login`, enter `alice@clienttest.test` / `ClientPass123!` | Redirects to `/dashboard` | |
| Bob login | Repeat with Bob credentials | Same flow; Bob's data is separate from Alice's | |
| Carol login | Repeat with Carol credentials | Same flow; Carol sees empty/new-account state | |
| Wrong password | Enter incorrect password | Toast: "Invalid credentials"; no data exposed | |
| Session persistence | Login, close tab, reopen app | Session restored (or graceful re-login) | |

---

## 2. Dashboard

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Account status cards | Log in as Alice → open `/dashboard` | Cards show account count, wallet balance ($500), active campaigns | |
| Wallet balance | Check wallet card for Alice | Shows **$500** | |
| Low-balance alert | Log in as Bob → open dashboard | Low-balance alert/banner visible | |
| Empty state | Log in as Carol → open dashboard | "No accounts yet" or onboarding prompt — no blank/erroring sections | |
| Campaign spend | Check campaigns spend widget | Spend figures shown; no NaN | |

---

## 3. Accounts List

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| List loads | Navigate to `/accounts` | Alice's ad accounts visible | |
| Carol empty state | Log in as Carol → `/accounts` | Empty state message, not an error | |
| Account detail | Click on an account row | Detail view with account name, status, spend | |

---

## 4. Ads Manager

### 4a. Basic Display

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Campaigns tab | Navigate to `/ads` → Campaigns tab | Campaign rows listed | |
| Ad Sets tab | Click "Ad Sets" tab | Ad set rows listed under campaign hierarchy | |
| Ads tab | Click "Ads" tab | Individual ad rows listed | |

### 4b. Status Toggles (test every toggle)

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Campaign toggle ON→OFF | Find an active campaign, click its status toggle | Toggle visually flips to inactive; row updates (note: Meta sync may be stubbed — see KNOWN-ISSUES) | |
| Campaign toggle OFF→ON | Click same toggle again | Returns to active state | |
| Ad Set toggle ON→OFF | Expand a campaign → toggle an ad set | Ad set status updates | |
| Ad Set toggle OFF→ON | Toggle back | Returns to active | |
| Ad toggle ON→OFF | Expand ad set → toggle an individual ad | Ad status updates | |
| Ad toggle OFF→ON | Toggle back | Returns to active | |

### 4c. Bulk Actions

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Select multiple | Check 2+ campaign checkboxes | Bulk action toolbar appears | |
| Enable Selected | Select 2 paused campaigns → "Enable Selected" | Both switch to active | |
| Pause Selected | Select 2 active campaigns → "Pause Selected" | Both switch to paused | |
| Delete Selected | Select 1 campaign → "Delete Selected" → confirm | Campaign removed from list; confirmation modal shown first | |

### 4d. Date Range Filter

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Date picker opens | Click date range picker | Calendar widget appears | |
| Select last 7 days | Choose "Last 7 days" preset | Spend/impression data refreshes for that range | |
| Custom range | Select a custom start/end date | Data filtered accordingly | |

---

## 5. Wallet

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Balance display | Navigate to `/wallet` | Shows correct balance (Alice: $500) | |
| Transaction history | Scroll down | List of past transactions visible with date, amount, type | |
| Empty history (Carol) | Log in as Carol → `/wallet` | Empty state, not an error | |

---

## 6. Top-Up

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Select standard tier | Navigate to `/wallet/topup` → select a pre-set tier (e.g., $100) | Tier highlights; total/commission preview appears | |
| Commission preview timing | After selecting tier | Preview appears within ~300 ms | |
| Select premium tier | Select the premium tier option | UI updates with premium pricing/bonus | |
| Select custom tier | Select "Custom" → enter a custom amount | Custom amount field enabled; preview updates | |
| Trigger error | Submit deposit with invalid/empty details | Error toast shown; form not cleared | |
| No double-submit | Click Pay twice quickly | Second click disabled; single transaction created | |

---

## 7. Billing

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Invoices list | Navigate to `/billing/invoices` | Invoice rows visible for Alice | |
| Receipt download | Click receipt icon on an invoice | PDF/receipt opens or downloads | |
| Carol empty state | Log in as Carol → `/billing/invoices` | Empty state, no error | |

---

## 8. Tickets

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Create ticket | Navigate to `/tickets` → "+ New Ticket" → fill subject + body → Submit | Ticket appears in list with "Open" status | |
| Reply | Click open ticket → type reply → Send | Reply appended to thread | |
| View status | Check ticket status badge | Correctly shows Open / In Progress / Closed | |

---

## 9. Support Chat

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Open chat | Click chat widget / navigate to `/chat` | Chat window opens; existing messages load | |
| Send message | Type "Hello QA test" → Send | Message appears in thread | |
| Reconnect on network drop | Open chat, disable network 5 s, re-enable | Reconnection banner shows, then chat resumes without page reload | |

---

## 10. Settings

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Change password — happy path | Navigate to `/settings` → Change Password → enter current `ClientPass123!` → new `NewPass456!` → confirm → Save | Success toast; log out; log back in with new password → works | |
| Change password — wrong current | Enter wrong current password | Error: "Current password incorrect" | |
| Notification preferences toggle | Toggle email notifications OFF → Save → reload page | Toggle still shows OFF after reload (persistence verified) | |
| Toggle back ON | Toggle email notifications ON → Save → reload | Toggle shows ON after reload | |

---

## 11. Affiliate

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Referral code visible | Navigate to `/affiliate` | Unique referral code/link shown for Alice | |
| Copy button | Click Copy | Link copied to clipboard | |
| Commission summary | Check commission stats | Shows total earned / pending; no NaN | |

---

## 12. Integrations

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Integrations page loads | Navigate to `/integrations` | Page renders; available integrations listed or empty state | |
| Connect Meta (if UI present) | Click "Connect Facebook/Meta" | OAuth flow initiates or stub message shown | |
