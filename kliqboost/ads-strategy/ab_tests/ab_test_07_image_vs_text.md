# A/B Test 07: Image Ad vs Text-Only

## Test ID: AB-07
## Variable: Whether to include a photo/image in the ad
## Hypothesis: Image ads get higher CTR but may feel less native in Telegram
## Duration: 5 days minimum
## Min Sample: 3,000 impressions per variant

---

## Test Setup

### Variant A — TEXT ONLY (Native Feel)
```yaml
ad_title: "Agency Ad Accounts"
ad_text: "Tired of account bans? Get verified agency ad accounts for Google, Meta & Taboola. Unlimited spend. No restrictions. Start today →"
show_picture: false
ad_identifier: "AB07-TEXT-A"
```

### Variant B — WITH IMAGE (Visual Impact)
```yaml
ad_title: "Agency Ad Accounts"
ad_text: "Tired of account bans? Get verified agency ad accounts for Google, Meta & Taboola. Unlimited spend. No restrictions. Start today →"
show_picture: true
# Use creative: creative_01_account_dashboard or creative_03_platform_logos
ad_identifier: "AB07-IMAGE-B"
```

---

## Image Creative Options to Test

1. **Account Dashboard Mockup** — Shows a clean dashboard with green status indicators
2. **Platform Logo Grid** — Google + Meta + TikTok + Taboola logos in a grid
3. **Trust Badges** — "Verified ✓" + "500+ Agencies" + "24h Setup"
4. **Stats Infographic** — "$50M+ in managed ad spend" visual

See `ad_creatives/images/` for full specifications.

## Decision Framework
- If image variant CTR > text variant by 15%+ → always use images
- If similar CTR but image costs more (higher CPM) → use text for efficiency
- If image variant gets more bot interactions → images for conversion-focused ads
- Consider: image ads may get different moderation treatment
