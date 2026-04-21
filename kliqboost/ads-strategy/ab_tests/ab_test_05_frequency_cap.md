# A/B Test 05: Frequency Cap (Daily Views per User)

## Test ID: AB-05
## Variable: Daily views limit per user (1x vs 2x vs 3x)
## Hypothesis: 2x/day increases conversion without significant fatigue; 3x causes ad blindness
## Duration: 7 days minimum
## Min Sample: 5,000 impressions per variant

---

## Test Setup

### Variant A — 1x per day (Conservative)
```yaml
daily_views_limit: 1
ad_identifier: "AB05-FREQ1-A"
initial_budget_ton: 30
```

### Variant B — 2x per day (Balanced)
```yaml
daily_views_limit: 2
ad_identifier: "AB05-FREQ2-B"
initial_budget_ton: 30
```

### Variant C — 3x per day (Aggressive)
```yaml
daily_views_limit: 3
ad_identifier: "AB05-FREQ3-C"
initial_budget_ton: 30
```

---

## Use same winning copy from AB-01 and same channel targeting.

## Metrics to Watch

| Metric | 1x/day | 2x/day | 3x/day |
|--------|--------|--------|--------|
| Expected CTR | Baseline | +10-20% | -5-15% |
| Impressions volume | Low | Medium | High |
| Fatigue indicator | None | Low | Moderate-High |
| Cost efficiency | Best CPM | Good CPM | Diminishing returns |

## Decision Rules
- Compare CTR trend over 7 days — is it declining?
- If 2x/day maintains CTR >90% of 1x/day after 7 days → switch to 2x
- If 3x/day CTR drops >30% below 1x/day → never use 3x
- Watch for user complaints or channel admin pushback at higher frequencies
