# A/B Test 06: CPM Bid Optimization

## Test ID: AB-06
## Variable: CPM bid level in TON
## Hypothesis: There's a sweet spot where increasing bid improves placement quality without overpaying
## Duration: 5 days minimum
## Min Sample: 3,000 impressions per variant

---

## Test Setup

### Variant A — Low Bid (Floor)
```yaml
cpm_in_ton: 0.2
ad_identifier: "AB06-LOWBID-A"
initial_budget_ton: 20
```
**Expected**: Fewer impressions, lower-quality placements, lowest cost

### Variant B — Medium Bid (Sweet Spot)
```yaml
cpm_in_ton: 0.5
ad_identifier: "AB06-MEDBID-B"
initial_budget_ton: 20
```
**Expected**: Good impression volume, decent placement quality

### Variant C — High Bid (Premium)
```yaml
cpm_in_ton: 1.0
ad_identifier: "AB06-HIGHBID-C"
initial_budget_ton: 20
```
**Expected**: Maximum impressions, best placement positions, highest cost

### Variant D — Aggressive Bid
```yaml
cpm_in_ton: 2.0
ad_identifier: "AB06-AGGBID-D"
initial_budget_ton: 20
```
**Expected**: Premium placements, may outbid all competition

---

## Metrics

| Bid Level | Est. CPM (TON) | Est. Impressions/day | CTR Impact |
|-----------|----------------|---------------------|------------|
| 0.2 TON | ~$0.70 | 2,000-5,000 | Baseline |
| 0.5 TON | ~$1.75 | 5,000-15,000 | +10-20% |
| 1.0 TON | ~$3.50 | 15,000-30,000 | +15-25% |
| 2.0 TON | ~$7.00 | 30,000-50,000 | +5-15% (diminishing) |

## Decision: Find the Efficiency Curve
```
Optimal CPM = Bid that maximizes (Impressions × CTR) / Cost

Plot: Effective Cost per Click at each bid level
Choose: Lowest eCPC that delivers sufficient daily volume
```

## Notes
- TON price fluctuates — monitor TON/USD rate daily
- Start with 0.5 TON and adjust based on impression delivery
- Telegram uses second-price auction — you often pay less than your bid
- Higher bids don't always mean proportionally more impressions
