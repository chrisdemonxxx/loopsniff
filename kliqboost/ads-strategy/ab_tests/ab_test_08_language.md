# A/B Test 08: Language Test (Russian vs English)

## Test ID: AB-08
## Variable: Ad copy language (Russian vs English)
## Hypothesis: Russian copy outperforms in RU-dominant channels; English copy may resonate with international/high-spend buyers
## Duration: 7 days minimum
## Min Sample: 3,000 impressions per variant

---

## Test Setup

### Variant A — ENGLISH COPY
```yaml
ad_title: "Agency Ad Accounts"
ad_text: "Tired of account bans? Get verified agency ad accounts for Google, Meta & Taboola. Unlimited spend. No restrictions. Start today →"
ad_identifier: "AB08-EN-A"
```

### Variant B — RUSSIAN COPY
```yaml
ad_title: "Агентские аккаунты"
ad_text: "Устали от банов? Верифицированные агентские аккаунты для Google, Meta и Taboola. Без лимитов. Без ограничений. Подробнее →"
ad_identifier: "AB08-RU-B"
```

### Variant C — MIXED (RU + EN Keywords)
```yaml
ad_title: "Ad Accounts | Аккаунты"
ad_text: "Agency ad accounts — агентские аккаунты для Google, Meta, Taboola. No bans, без лимитов. 500+ agencies trust us. Join →"
ad_identifier: "AB08-MIXED-C"
```

---

## Target Channels
Split channels by dominant language:

**RU-dominant channels**: adsninjas, traffic_ultras, kupets_traf, shoteam_channel
**Mixed/bilingual channels**: xxxcpa, zuevaff, agency2fa

## Important Context
- 90%+ of scraped channels are RU/UK language
- But many CIS media buyers read English fluently
- English copy may signal "international/premium" quality
- Russian copy builds instant relatability

## Decision Rules
- If RU copy CTR > EN by 30%+ → default to RU for RU channels
- If EN copy gets better lead quality (higher spend clients) → use EN for Diamond targeting
- Mixed copy may work as a compromise but could look unprofessional
