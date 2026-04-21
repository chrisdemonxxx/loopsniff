# A/B Test 01: Pain Point vs Benefit-Focused Copy

## Test ID: AB-01
## Variable: Primary ad copy angle
## Hypothesis: Pain-point copy outperforms benefit copy for media buyers (who are actively frustrated by bans)
## Duration: 4 days minimum
## Min Sample: 2,000 impressions per variant

---

## Test Setup

### Variant A — PAIN POINT (Control)
```yaml
ad_title: "Agency Ad Accounts"
ad_text: "Tired of account bans? Get verified agency ad accounts for Google, Meta & Taboola. Unlimited spend. No restrictions. Start today →"
url_to_promote: "https://t.me/kliqboost_bot"
cpm_in_ton: 0.5
initial_budget_ton: 25
daily_views_limit: 1
ad_identifier: "AB01-PAIN-A"
```
**Character count**: 132/160

### Variant B — BENEFIT FOCUSED
```yaml
ad_title: "Scale Your Ads"
ad_text: "Scale to $100K+/month without account limits. Premium agency accounts for Google, Meta, TikTok. 500+ agencies trust us. Join →"
url_to_promote: "https://t.me/kliqboost_bot"
cpm_in_ton: 0.5
initial_budget_ton: 25
daily_views_limit: 1
ad_identifier: "AB01-BENEFIT-B"
```
**Character count**: 126/160

### Variant C — QUESTION HOOK
```yaml
ad_title: "Need Ad Accounts?"
ad_text: "Need fresh ad accounts that don't get banned? We supply verified agency accounts for all major platforms. Details inside →"
url_to_promote: "https://t.me/kliqboost_bot"
cpm_in_ton: 0.5
initial_budget_ton: 25
daily_views_limit: 1
ad_identifier: "AB01-QUESTION-C"
```
**Character count**: 121/160

---

## Target Channels (same for all variants)
Use channels from `adset_01_core_media_buyers.md` — run all 3 variants on the same channel set for fair comparison.

## Success Metrics

| Metric | Winner Criteria |
|--------|----------------|
| Primary: **CTR** | >20% relative difference between variants |
| Secondary: **Cost per Join** | Lower is better |
| Tertiary: **Bot interaction rate** | Higher is better |

## Decision Rules
- After 4 days: Kill variant with lowest CTR
- After 7 days: Declare winner if >20% CTR difference at 90% confidence
- Winner becomes new Control for next test round

## Expected Results
Based on industry data, pain-point copy typically outperforms benefit copy by 15-25% CTR in media buying niches where frustration (account bans) is a daily reality.
