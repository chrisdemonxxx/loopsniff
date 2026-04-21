# A/B Test 03: CTA Variations

## Test ID: AB-03
## Variable: Call-to-action text and destination framing
## Hypothesis: Action-oriented CTAs ("Apply Now") outperform passive CTAs ("Learn More") for high-intent audiences
## Duration: 4 days minimum
## Min Sample: 1,500 impressions per variant

---

## Test Setup (same body copy, different CTA)

**Base copy**: "Premium agency ad accounts for Google, Meta & Taboola. Unlimited spend. No restrictions."

### Variant A — SOFT CTA
```yaml
ad_text: "Premium agency ad accounts for Google, Meta & Taboola. Unlimited spend. No restrictions. Learn more →"
ad_identifier: "AB03-SOFT-A"
```

### Variant B — ACTION CTA
```yaml
ad_text: "Premium agency ad accounts for Google, Meta & Taboola. Unlimited spend. No restrictions. Apply now →"
ad_identifier: "AB03-ACTION-B"
```

### Variant C — COMMUNITY CTA
```yaml
ad_text: "Premium agency ad accounts for Google, Meta & Taboola. Unlimited spend. No restrictions. Join our channel →"
ad_identifier: "AB03-COMMUNITY-C"
```

### Variant D — DM CTA
```yaml
ad_text: "Premium agency ad accounts for Google, Meta & Taboola. Unlimited spend. No restrictions. DM us for pricing →"
ad_identifier: "AB03-DM-D"
```

---

## Common Settings
```yaml
ad_title: "Agency Ad Accounts"
url_to_promote: "https://t.me/kliqboost_bot"
cpm_in_ton: 0.5
initial_budget_ton: 15
daily_views_limit: 1
```

## Decision Rules
- Primary metric: Click-through rate
- Secondary metric: Post-click conversion (join rate or bot interaction)
- A CTA with high CTR but low conversion is worse than moderate CTR + high conversion
