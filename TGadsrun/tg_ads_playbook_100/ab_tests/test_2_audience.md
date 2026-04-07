# A/B Test 2: Audience — Media Buyers vs Affiliates
## Validate if winning copy works across segments

**Priority**: 🟡 SECONDARY — Run Day 6+ only
**Duration**: Days 6–14
**Budget**: $50 remaining
**Prerequisite**: Must have a winning copy from Test 1

---

## Test Design

| Element | Details |
|---------|---------|
| Variable | Target audience (channel selection) |
| Control | Ad Set A winner (Core Media Buyers) |
| Treatment | Same copy in Ad Set B (Affiliate/CPA channels) |
| Constant | Same copy, same CPM, same destination |
| Metric | Primary: CTR comparison. Secondary: Bot interaction quality |

## Variants

### Variant A: Core Media Buyers (Control)
```yaml
copy: "[WINNING NICHE COPY FROM TEST 1]"
image: "[WINNING NICHE IMAGE FROM TEST 1]"
target_channels:
  - https://t.me/adsninjas
  - https://t.me/traffic_ultras
  - https://t.me/kupets_traf
  - https://t.me/alex_traffic_google_ads
  - https://t.me/traffic_ultras_news
cpm_in_ton: 0.5
budget_ton: 7.0
ad_identifier: "AUDIENCE-CONTROL"
```

### Variant B: Affiliate/CPA (Treatment)
```yaml
copy: "[SAME WINNING NICHE COPY FROM TEST 1]"
image: "[SAME WINNING NICHE IMAGE FROM TEST 1]"
target_channels:
  - https://t.me/xxxcpa
  - https://t.me/ruslan_affblog
  - https://t.me/zuevaff
  - https://t.me/cpaconqueror
  - https://t.me/trafficultras_navigator
cpm_in_ton: 0.4
budget_ton: 5.0
ad_identifier: "AUDIENCE-TREATMENT"
```

### Variant C: Challenger Creative (Bonus)
```yaml
copy: "[DIFFERENT NICHE from Test 1 — e.g., if BSOD won, try Gambling here]"
image: "[MATCHING NICHE IMAGE]"
target_channels: "[SAME AS VARIANT A]"
cpm_in_ton: 0.5
budget_ton: 2.3
ad_identifier: "AUDIENCE-CHALLENGER"
```

---

## Results Tracking

### Days 6–10
| Variant | Impressions | Clicks | CTR | Bot DMs | Qualified Leads | Spend |
|---------|------------|--------|-----|---------|----------------|-------|
| A: MB Control | | | | | | |
| B: Affiliate | | | | | | |
| C: Challenger | | | | | | |

### Day 10 — Comparison
| Metric | Variant A (MB) | Variant B (Aff) | Difference |
|--------|---------------|-----------------|------------|
| CTR | | | |
| CPC | | | |
| Bot DMs | | | |
| Bot DM rate | | | |
| Lead quality | | | |

---

## Decision Framework

```
B's CTR >= 80% of A's CTR:
├── ✅ Audience validated
├── Both audiences worth targeting at scale
├── Next budget: split 60/40 between MB and Affiliate
└── Can expand to Tier 2 channels in both segments

B's CTR = 50-80% of A's CTR:
├── ⚠️ Weaker but viable
├── Affiliates respond but less strongly
├── Try affiliate-specific copy (AFF-SPECIFIC-01-RU)
└── May need different angle for this audience

B's CTR < 50% of A's CTR:
├── ❌ Audience mismatch
├── Winning copy doesn't resonate with affiliates
├── Stick with Core MB channels exclusively
└── Test different copy angle for affiliates later

Challenger C beats A:
├── 🎉 New winner found
├── Replace A with C as the new control
├── Clone C into affiliate channels
└── Continue optimization cycle
```

---

## Quality Check: Bot Interaction Comparison

Beyond CTR, compare the QUALITY of leads from each audience:

| Quality Signal | Set A (MB) | Set B (Aff) |
|---------------|-----------|-------------|
| % who start bot convo | | |
| Avg BANT score | | |
| % reaching checkout | | |
| Avg order value | | |
| Response language (RU/EN) | | |

This tells you not just who CLICKS but who BUYS.
