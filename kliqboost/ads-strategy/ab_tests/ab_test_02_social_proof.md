# A/B Test 02: Social Proof Variants

## Test ID: AB-02
## Variable: Type of social proof in ad copy
## Hypothesis: Specific numbers ("500+ agencies") outperform vague trust signals ("trusted by professionals")
## Duration: 4 days minimum
## Min Sample: 2,000 impressions per variant

---

## Test Setup

### Variant A — SPECIFIC NUMBERS
```yaml
ad_title: "500+ Agencies Trust Us"
ad_text: "500+ agencies and media buyers use our premium ad accounts. Google, Meta, Taboola — instant setup, no spend limits. See why →"
url_to_promote: "https://t.me/kliqboost_bot"
cpm_in_ton: 0.5
initial_budget_ton: 25
daily_views_limit: 1
ad_identifier: "AB02-NUMBERS-A"
```

### Variant B — TENURE/HISTORY
```yaml
ad_title: "Since 2020"
ad_text: "Since 2020, we've supplied thousands of verified ad accounts. Google, Meta, TikTok. Zero account issues. Trusted by top agencies →"
url_to_promote: "https://t.me/kliqboost_bot"
cpm_in_ton: 0.5
initial_budget_ton: 25
daily_views_limit: 1
ad_identifier: "AB02-TENURE-B"
```

### Variant C — OUTCOME-BASED
```yaml
ad_title: "Our Clients Scale Fast"
ad_text: "Our clients scale from $10K to $100K/month using our agency accounts. Google & Meta. No bans, no limits. Join our channel →"
url_to_promote: "https://t.me/kliqboost_bot"
cpm_in_ton: 0.5
initial_budget_ton: 25
daily_views_limit: 1
ad_identifier: "AB02-OUTCOME-C"
```

---

## Target Channels
Same as AB-01 — use `adset_01_core_media_buyers.md` channels.

## Decision Rules
- Declare winner after 4-7 days with sufficient sample
- Winning social proof element becomes part of all future copy variants
