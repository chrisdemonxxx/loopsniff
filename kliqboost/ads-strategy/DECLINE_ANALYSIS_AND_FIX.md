# TG Ads Decline Analysis & Fix — Kliqboost Media

## Decline Reason: "Destination Quality" (Section 4.1)

All 4 COMPLIANT ads were declined for **destination quality**, NOT for ad copy content.
This means Telegram's reviewers checked the **bot destination** (`@kliqboost_bot`)
and found issues with the bot itself, not the ad text.

---

## Root Cause Analysis

### Most Likely Causes (in order of probability):

1. **Bot Profile Incomplete in BotFather**
   - Missing or generic "About" text
   - Missing or poor "Description"
   - Missing profile picture
   - Name formatting issues (caps, special chars)

2. **Bot Doesn't Respond Properly on Desktop**
   - TG reviewers test on BOTH mobile AND desktop
   - If bot only works on mobile, it fails review
   - The `/start` command must produce a clean, professional response

3. **Bot Content Mismatch with Ad**
   - Ad says "agency ad accounts" but bot welcome message may not clearly match
   - Bot must immediately deliver on what the ad promises

4. **Bot Appears Low-Quality or Spammy**
   - Excessive emoji in any bot surface
   - ALL CAPS anywhere in bot text
   - Empty menus or broken flows
   - AI chat responding with errors or timeouts

5. **Bot Promotes Prohibited Verticals**
   - Even though ad copy is clean, if the bot's internal text, menus, or AI
     responses mention gambling/nutra/BSOD, the entire destination fails review
   - Internal variable names don't matter — only user-visible text

---

## Action Items to Fix

### 1. BotFather Profile (DO FIRST)

Message @BotFather → `/mybots` → Select `@kliqboost_bot` → Edit Bot:

```
Name: Kliqboost Media
About: Agency advertising accounts for Google, Meta, TikTok and more. Professional service for media buyers.
Description: Kliqboost Media provides agency-level advertising accounts across major platforms including Google Ads, Meta Ads, TikTok, and Taboola. Talk to our assistant to learn about pricing, available platforms, and delivery timelines. Professional support for media buyers and agencies.
```

**Profile Picture**: Must be set. Use a clean, professional logo (no text overlays with CAPS).

### 2. Bot /start Response

Current `/start` response is clean and professional ✅:
```
Kliqboost Media

Agency ad accounts for Google, Meta, TikTok, Taboola and more.

Tell me what you need — platform, budget, timeline — and I'll get you sorted. Ready when you are.
```

This is good. Make sure it renders properly on both mobile AND desktop.

### 3. Test Bot on Desktop Telegram App

- Open Telegram Desktop (NOT web)
- Send `/start` to the bot
- Verify it responds immediately
- Try sending a message and verify AI responds
- Check all menu buttons work

### 4. Ensure Bot is Running and Responsive

The bot must be live and responding when the ad is submitted.
A bot that times out or errors = instant rejection.

### 5. Remove Any Hidden Prohibited Content

Grep through all user-visible bot text for prohibited terms.
Current status: en.py and ru.py are **CLEAN** ✅
- No gambling/casino/betting/slots terms
- No nutra/supplement terms
- No BSOD references
- No "no bans" / "без банов" claims

---

## Test Ad Strategy: Get ONE Approved First

### Step 1: Fix BotFather profile (above)
### Step 2: Verify bot works on mobile + desktop
### Step 3: Submit this SINGLE test ad:

---

## TEST AD — "Canary" (Submit First)

This is the safest possible ad — generic, professional, no niche terms at all.

```yaml
ad_title: "Kliqboost Media"
ad_text: "Агентские рекламные аккаунты для медиабайеров. Google, Meta, Taboola, TikTok. Профессиональный сервис. Подробнее"
url_to_promote: "https://t.me/kliqboost_bot"
show_picture: false          # Text-only is safer for first approval
cpm_in_ton: 0.5
daily_views_limit: 1
```

**Why this will pass:**
- No niche-specific terms (no crypto, no finance, no vertical names)
- No claims (no "высокие лимиты", no social proof numbers)
- No arrows, no excessive formatting
- Russian text matching Russian target channels
- CTA is "Подробнее" (safest CTA word)
- Text-only (no image to trigger additional review)
- ~107 chars (well under 160 limit)

**Target channels for test:**
```
https://t.me/adsninjas
https://t.me/traffic_ultras
```
(Just 2 channels to minimize variables)

### Step 4: Wait for approval (24-48h)

### Step 5: If approved → submit remaining COMPLIANT ads

---

## Updated COMPLIANT Ad Set (Post-Approval)

Once the canary passes, submit these in a batch:

### COMPLIANT-01v2 — Platform-focused
```yaml
ad_title: "Агентские рекламные аккаунты"
ad_text: "Масштабируйте рекламу через агентские аккаунты Google, Meta, TikTok. Высокие лимиты, быстрая выдача. Подробнее"
url_to_promote: "https://t.me/kliqboost_bot"
show_picture: false
cpm_in_ton: 0.5
```
Changes: Removed "Узнать условия" → "Подробнее" (safer CTA)

### COMPLIANT-02v2 — Stability
```yaml
ad_title: "Стабильная реклама без проблем"
ad_text: "Агентские аккаунты Google и Meta с высокими лимитами. Любая вертикаль. Поддержка и замена. Подробнее"
url_to_promote: "https://t.me/kliqboost_bot"
show_picture: false
cpm_in_ton: 0.5
```
No changes needed — this was already clean.

### COMPLIANT-03v2 — Crypto/Finance (safe per 5.7)
```yaml
ad_title: "Аккаунты для крипто и финансов"
ad_text: "Агентские рекламные аккаунты для крипто, финансов и е-ком. Google, Meta, TikTok. Выдача за 2 часа"
url_to_promote: "https://t.me/kliqboost_bot"
show_picture: false
cpm_in_ton: 0.5
```
No changes needed.

### COMPLIANT-04v2 — Brand
```yaml
ad_title: "Kliqboost Media"
ad_text: "Агентские аккаунты для медиабайеров. Google, Meta, Taboola, TikTok. Все вертикали. Выдача за 2 часа"
url_to_promote: "https://t.me/kliqboost_bot"
show_picture: false
cpm_in_ton: 0.5
```
No changes needed.

---

## If Canary Gets Rejected Again

If the test ad STILL gets rejected for "Destination quality":

1. **Try promoting a CHANNEL instead of a bot**
   - Create/use `@kliqboost_media` channel
   - Post 5-10 professional content posts first
   - Submit ad pointing to the channel instead
   - Channels have lower review bar than bots

2. **Check if bot account age is sufficient**
   - Some TG ad features require 30+ day old destinations
   - If bot was just created, wait and try again

3. **Contact Telegram Ads support**
   - support@ads.telegram.org
   - Ask specifically what failed the destination quality check

---

## Summary

The ads were declined because of the **bot destination**, not the ad copy.
Fix the BotFather profile, verify the bot works on desktop, and submit
a single ultra-safe test ad first. Once approved, scale to the full ad set.
