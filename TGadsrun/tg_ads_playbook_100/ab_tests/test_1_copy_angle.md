# A/B Test 1: Niche Angle — BSOD vs Crypto vs Gambling vs Multi
## THE critical test for $100 budget

**Priority**: 🔴 HIGHEST — Run this Day 1
**Duration**: Days 1–5
**Budget**: $70 total ($17.50 per variant)
**Statistical rigor**: Need 5,000+ impressions per variant minimum

---

## Test Design

| Element | Details |
|---------|---------|
| Variable | Ad niche/vertical (which buyers respond) |
| Control | None — 4-way comparison |
| Constant | Same channels, same CPM, same destination, same budget |
| Metric | Primary: CTR. Secondary: Bot DMs |

## Variants

### Variant A: BSOD / Tech Support
```
Title: Аккаунты для техподдержки
Text:  Льёте трафик на техподдержку? Агентские аккаунты Google и Bing без банов. Свежие, без лимитов. Забирайте →
ID:    NICHE-BSOD-01-RU
Image: 01_bsod_tech_support.png
```
**Hypothesis**: BSOD/tech support is the highest-ban vertical — biggest pain = highest urgency.

### Variant B: Crypto / DeFi
```
Title: Аккаунты для крипто
Text:  Крипто-кампании блокируют? Агентские аккаунты для бирж, DeFi, токенов. Google, Meta, TikTok. Без ограничений. Начать →
ID:    NICHE-CRYPTO-01-RU
Image: 02_crypto_defi.png
```
**Hypothesis**: Crypto is hot vertical with massive ad spend — high relevance in RU channels.

### Variant C: Gambling / iGaming
```
Title: Аккаунты для гемблинга
Text:  Рекламу казино банят? Агентские аккаунты для казино, букмекеров и слотов. Google, Meta. Без ограничений. Подробнее →
ID:    NICHE-GAMB-01-RU
Image: 03_gambling_igaming.png
```
**Hypothesis**: Gambling buyers are the biggest spenders — highest LTV potential.

### Variant D: Multi-Vertical (All Niches)
```
Title: Любая вертикаль. Любая площадка.
Text:  BSOD, крипто, гемблинг, e-com, нутра — аккаунты для любой ниши. Google, Meta, TikTok. Без банов. Доступ →
ID:    NICHE-MULTI-01-RU
Image: 07_multi_vertical.png
```
**Hypothesis**: Catch-all appeals to buyers across all verticals — broadest reach.

---

## Configuration (all 4 identical except copy + image)

```yaml
# Same for all 4 ads:
url_to_promote: "https://t.me/kliqboostmedia_bot"
cpm_in_ton: 0.5
initial_budget_ton: 5.0
daily_views_limit: 1
show_picture: true
target_channels:
  - https://t.me/adsninjas
  - https://t.me/traffic_ultras
  - https://t.me/kupets_traf
  - https://t.me/alex_traffic_google_ads
  - https://t.me/traffic_ultras_news
  - https://t.me/shomedia
  - https://t.me/cpaconqueror
```

---

## Results Tracking Table

Fill this in daily:

### Day 1
| Variant | Impressions | Clicks | CTR | Bot DMs | Spend (TON) |
|---------|------------|--------|-----|---------|-------------|
| A: BSOD | | | | | |
| B: Crypto | | | | | |
| C: Gambling | | | | | |
| D: Multi | | | | | |

### Day 2
| Variant | Impressions | Clicks | CTR | Bot DMs | Spend (TON) |
|---------|------------|--------|-----|---------|-------------|
| A: BSOD | | | | | |
| B: Crypto | | | | | |
| C: Gambling | | | | | |
| D: Multi | | | | | |

### Day 3 — FIRST KILL CHECK
| Variant | Impressions | Clicks | CTR | Bot DMs | Spend (TON) | Action |
|---------|------------|--------|-----|---------|-------------|--------|
| A: BSOD | | | | | | KEEP / KILL |
| B: Crypto | | | | | | KEEP / KILL |
| C: Gambling | | | | | | KEEP / KILL |
| D: Multi | | | | | | KEEP / KILL |

**Day 3 Rule**: If any variant has CTR < 0.15% AND 3,000+ impressions → KILL IT.

### Day 5 — DECLARE WINNER
| Variant | Total Impr | Total Clicks | Avg CTR | Total Bot DMs | Total Spend | VERDICT |
|---------|-----------|-------------|---------|--------------|-------------|---------|
| A: BSOD | | | | | | |
| B: Crypto | | | | | | |
| C: Gambling | | | | | | |
| D: Multi | | | | | | |

**Winner**: The variant with highest CTR AND at least 1 bot DM.
If tie on CTR → pick the one with more bot DMs.
If tie on both → pick Gambling (historically highest LTV in media buying).

---

## What to Do With Results

```
WINNER FOUND (CTR > 0.3%):
├── Clone winning niche copy → Ad Set B (Affiliate channels)
├── Double winner's budget (add 5 TON)
├── Kill worst 2 performers
├── Launch challenger from same niche (e.g., NICHE-BSOD-02-RU)
└── Move to A/B Test 2: Audience

NO CLEAR WINNER (all 0.15-0.30%):
├── Keep top 2 niches, kill bottom 2
├── Launch Agency Premium copy (NICHE-AGENCY-01-RU) as challenger
├── Give 3 more days
└── If still no winner by Day 8 → test with E-com or Finance niche

ALL FAILED (all < 0.15%):
├── Pause everything
├── Check: Are channels delivering? (if <500 impr, raise CPM)
├── Check: Are images being shown? (try text-only variants)
├── Try completely different approach: NICHE-AGENCY-01-RU (premium brand)
└── Consider pivoting to direct channel post buys
```
