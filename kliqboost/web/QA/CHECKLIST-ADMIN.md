# Admin Panel — QA Checklist

All tests performed in **Chrome latest** (also spot-check Firefox).
Seed data must be loaded before starting (`python -m app.seed_qa`).

---

## 1. Authentication

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Admin login | Visit `/login`, enter `admin@kliqboost.test` / `AdminPass123!` | Redirects to `/dashboard`, no error | |
| Bad password | Submit wrong password | Toast: "Invalid credentials", stays on login | |
| Role enforcement | Log in as Alice (client), manually visit `/admin/clients` | Redirected to `/login` or 403 page — NOT admin data | |
| Logout | Click avatar → Logout | Session cleared, redirected to `/login`; back-button does not restore session | |

---

## 2. Dashboard

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Stats cards load | Open `/dashboard` | Active clients, total revenue, open tickets, active campaigns cards all show non-zero numbers — no "coming soon" text anywhere | |
| Revenue chart renders | Scroll to revenue chart | Chart renders with bars/line; no blank white box | |
| Recent activity feed | Check right sidebar / activity section | Shows recent logins or transactions; not a blank list | |

---

## 3. Clients

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| List loads | Navigate to `/clients` | Table with ≥3 rows (Alice, Bob, Carol) | |
| Filter by name | Type "alice" in search box | Only Alice row visible | |
| View client detail | Click Alice row | Detail page with name, email, wallet balance ($500), subscription status | |
| Notes save | On Alice's detail, add a note "Test note QA" → Save | Note persists after page refresh | |
| Suspend client | Click Suspend on Bob → confirm modal | Bob's status changes to Suspended; confirmation modal appeared first | |
| Reactivate | Click Reactivate on Bob | Status returns to Active | |

---

## 4. Accounts

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Accounts list | Navigate to `/accounts` | Table shows Ad Account rows | |
| Sort by status | Click "Status" column header | Rows reorder; active/inactive grouped | |
| Client name shown | Check "Client" column | Shows "Alice Smith" (or display name), not a raw UUID | |
| Create account | Click "+ New Account", fill form, submit | New row appears in table with correct client association | |
| Edit account | Click edit icon, change spend limit, save | Updated value reflected immediately in table | |

---

## 5. Finance

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Deposits list | Navigate to `/finance/deposits` | Table with at least one pending deposit | |
| Approve deposit | Select a pending deposit → Approve | Status changes to Approved; client wallet balance updates | |
| Reject deposit | Select a pending deposit → Reject (with reason) | Status changes to Rejected | |
| View receipt | Click receipt icon on an approved deposit | Receipt modal or new tab with transaction details | |
| Commission calculation | Check commission column | Shows correct % of deposit amount; matches configured rate in Settings | |

---

## 6. Outreach

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Campaigns list | Navigate to `/outreach/campaigns` | Campaign rows visible (may be empty if outreach DB not available — note in KNOWN-ISSUES) | |
| Leads list | Navigate to `/outreach/leads` | Lead rows or empty-state message | |
| Message templates | Navigate to `/outreach/templates` | Template list with create/edit controls | |

---

## 7. CRM

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Leads pipeline | Navigate to `/crm` | Kanban-style board with stage columns | |
| Move lead between stages | Drag a card from "New" to "Contacted" | Card moves; status persists after refresh | |
| Add note | Open lead detail → add note | Note saved and visible on re-open | |

---

## 8. Tickets

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| View open tickets | Navigate to `/tickets` | List of open tickets visible | |
| Reply to ticket | Open a ticket → type reply → Send | Reply appended; client side would see update | |
| Close ticket | Click "Close" on an open ticket | Status changes to Closed; disappears from open filter | |
| Reassign | Click Reassign → select another admin | Assignee field updates | |

---

## 9. Subscriptions

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Plans list | Navigate to `/subscriptions/plans` | Existing plans listed (e.g., Starter, Pro, Enterprise) | |
| Create plan | Click "+ New Plan", fill name/price/limits | New plan appears in list | |
| Edit plan | Click edit on existing plan → change price | Updated price reflected | |
| Assign plan to client | Open Alice's client profile → Subscription tab → Assign plan | Alice's subscription status updates to new plan | |
| Retry on failure | If a subscription payment is marked failed, click Retry | Retry attempt logged; status updates | |

---

## 10. Settings

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Admin config edit | Navigate to `/settings` → edit a text field → Save | Change persists after refresh | |
| Commission rate | Change commission rate field → Save | New rate reflected in Finance commission column on next deposit | |
| API keys reveal | Click "Reveal" on an API key field | Key visible only after clicking; requires re-auth token check | |
| Daily limit save | Change daily spend limit → Save | Value saved; clients see updated limit in their portal | |

---

## 11. Chat

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| View conversations | Navigate to `/chat` | List of client conversations | |
| Send message | Open Alice's conversation → type message → Send | Message appears in thread | |
| Escalate | Click Escalate on a conversation | Escalation flag set; conversation moved to escalated filter | |

---

## 12. Alerts

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Alerts list | Navigate to `/alerts` | Alert rows visible; Bob should show low-balance alert | |
| Dismiss alert | Click dismiss on an alert | Alert removed from list | |

---

## 13. Team

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Team members list | Navigate to `/team` | Admin users listed; includes `manager@kliqboost.test` | |
| Invite (if implemented) | Click Invite → fill email | Invitation sent or queued | |

---

## 14. Affiliates

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Affiliates list | Navigate to `/affiliates` | Affiliate records or empty state | |
| Commission records | Check commission totals | Numbers display; no NaN or undefined | |

---

## 15. Deposit Config

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| View tiers | Navigate to `/settings/deposit-config` | Deposit tiers listed with min/max amounts | |
| Edit tier | Change a tier value → Save | Persists after refresh; client portal shows updated tier | |

---

## 16. Bot Section

| Feature | Test Steps | Expected Result | Pass/Fail Notes |
|---------|-----------|-----------------|-----------------|
| Bot stats | Navigate to `/bot` or `/bot-stats` | Stats display; no 500 error | |

---

## Seed Data Reference

- **Alice** wallet balance: **$500** | subscription: Active
- **Bob** wallet balance: low (trigger threshold) — should show **low-balance alert** in Alerts section
- **Carol**: fresh account — should show **empty state** on most sections (no accounts, no deposits)
