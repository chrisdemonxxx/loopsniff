# Telegram Ads Strategy — Complete Campaign Package

## Business: Agency Ad Account Supplier
## Platform: ads.telegram.org (Official Telegram Ads)
## Payment: TON Cryptocurrency
## Created: 2026-04-06

---

## Directory Structure

```
tg_ads_strategy/
├── README.md                          ← This file (master strategy overview)
├── MASTER_STRATEGY.md                 ← Full strategy document with rationale
├── ad_sets/
│   ├── adset_01_core_media_buyers.md  ← Tier 1: Core media buying channels
│   ├── adset_02_affiliate_cpa.md      ← Tier 2: Affiliate/CPA channels
│   ├── adset_03_gambling_betting.md   ← Tier 3: Gambling/iGaming channels
│   ├── adset_04_ecommerce_nutra.md    ← Tier 4: E-comm & Nutra channels
│   ├── adset_05_platform_specific.md  ← Tier 5: FB/Google/TikTok Ads channels
│   └── adset_06_broad_awareness.md    ← Tier 6: Broad reach awareness
├── ab_tests/
│   ├── ab_test_01_pain_vs_benefit.md  ← Copy angle test
│   ├── ab_test_02_social_proof.md     ← Trust signal test
│   ├── ab_test_03_cta_variations.md   ← CTA button test
│   ├── ab_test_04_destination.md      ← Channel vs Bot destination test
│   ├── ab_test_05_frequency_cap.md    ← 1x vs 2x daily views test
│   ├── ab_test_06_cpm_bid.md          ← Bid optimization test
│   ├── ab_test_07_image_vs_text.md    ← Image ad vs text-only test
│   └── ab_test_08_language.md         ← RU vs EN copy test
├── ad_creatives/
│   ├── copy_variants/
│   │   ├── pain_point_copies.md       ← Pain-point focused ad copies
│   │   ├── benefit_copies.md          ← Benefit-focused ad copies
│   │   ├── social_proof_copies.md     ← Social proof ad copies
│   │   ├── urgency_copies.md          ← Urgency/scarcity ad copies
│   │   ├── question_hook_copies.md    ← Question hook ad copies
│   │   └── russian_copies.md          ← Russian-language ad copies
│   └── images/
│       ├── image_specs.md             ← Image specifications & guidelines
│       ├── creative_01_account_dashboard.svg  ← Dashboard mockup creative
│       ├── creative_02_trust_badges.svg       ← Trust/verification badges
│       ├── creative_03_platform_logos.svg      ← Platform logo grid
│       └── creative_04_stats_infographic.svg   ← Performance stats visual
├── targeting_lists/
│   ├── tier1_channels.csv             ← High-intent channels (score 70+)
│   ├── tier2_channels.csv             ← Medium-intent channels (score 60-69)
│   ├── tier3_channels.csv             ← Broader reach channels (score 50-59)
│   └── excluded_countries.md          ← Country exclusion notes
└── budgets/
    ├── phase1_discovery.md            ← Week 1-2 budget plan
    ├── phase2_validation.md           ← Week 3-4 budget plan
    ├── phase3_scale.md                ← Month 2+ budget plan
    └── budget_calculator.py           ← Python script for ROI calculations
```

## Quick Start

1. Read `MASTER_STRATEGY.md` for the full strategic rationale
2. Start with `ad_sets/adset_01_core_media_buyers.md` — this is your highest-ROI ad set
3. Launch A/B tests from `ab_tests/ab_test_01_pain_vs_benefit.md` first
4. Use creatives from `ad_creatives/copy_variants/` — pick 4-6 to start
5. Follow budget phases in `budgets/phase1_discovery.md`
6. Target channels from `targeting_lists/tier1_channels.csv`

## Platform Interface Reference (from Screenshot)

The Telegram Ads "Create Your Ad" interface has these fields:

| Field | Max/Options | Notes |
|-------|-------------|-------|
| **Ad title** | ~40 chars | Short, punchy headline |
| **Ad text** | 160 chars max | Main message body |
| **URL to promote** | t.me link only | Channel or bot link |
| **Show picture** | Checkbox | Enable image in ad |
| **Ad photo or video** | Upload | Visual creative |
| **CPM in Ton** | Decimal (min 0.1) | Cost per 1000 impressions |
| **Initial budget in Ton** | Decimal | Total campaign budget |
| **Daily views limit per user** | 1, 2, 3, or 4 | Frequency cap |
| **Initial status** | Active / On Hold | Set On Hold to review before launch |
| **Ad Schedule** | Optional | Time-based delivery |
| **Target** | Search / Bots / Channels | Primary: Channels targeting |
| **Target specific channels** | t.me URLs | Enter channel URLs to target |

### Important Platform Constraints:
- ⛔ Will NOT be shown in: Russian Federation, Ukraine, Israel, Palestine
- ⚠️ Target parameters can't be changed after ad creation
- 💰 Budget is in TON cryptocurrency (≈$3.50/TON as of April 2026)
