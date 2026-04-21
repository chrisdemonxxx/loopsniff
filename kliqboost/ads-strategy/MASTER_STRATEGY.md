# MASTER STRATEGY — Telegram Ads for Agency Ad Account Supply

## Complete Campaign Architecture with A/B Testing Framework

---

## Executive Summary

This strategy package provides a **complete, ready-to-launch Telegram Ads campaign** for an agency ad account supplier business. It includes 6 ad sets targeting different audience verticals, 8 structured A/B tests, 45+ ad copy variants (English, Russian, Ukrainian), 4 SVG visual creatives, tiered targeting lists from 1,065 scraped channels, and a 3-phase budget plan with ROI calculator.

The strategy is built on data from **1,065 channels** scraped via Telemetrio, scored and segmented across 20+ verticals. Top channels have been organized into 3 tiers by relevance score (70+, 60-69, 50-59).

### Key Numbers at Scale (Month 2+)
- **Budget**: 1,500 TON/month (~$5,250)
- **Impressions**: 3,000,000
- **Qualified Leads**: ~262/month
- **New Clients**: ~26/month
- **Projected ROAS**: 25:1

---

## Campaign Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TELEGRAM ADS CAMPAIGN                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  AD SETS (6 Vertical Segments)                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│  │ Core MB  │ │ Affiliate│ │ Gambling │                    │
│  │   40%    │ │   20%    │ │   15%    │                    │
│  └──────────┘ └──────────┘ └──────────┘                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│  │ E-com/   │ │ Platform │ │  Broad   │                    │
│  │ Nutra 10%│ │ Spec 10% │ │ Aware 5% │                    │
│  └──────────┘ └──────────┘ └──────────┘                    │
│                                                             │
│  A/B TESTS (8 Concurrent Tests)                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │Pain vs   │ │Social    │ │CTA       │ │Channel   │      │
│  │Benefit   │ │Proof     │ │Variants  │ │vs Bot    │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │Frequency │ │CPM Bid   │ │Image vs  │ │Language  │      │
│  │Cap       │ │Optimize  │ │Text      │ │RU vs EN  │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│                                                             │
│  COPY LIBRARY (45+ variants across 6 categories)           │
│  Pain Point(8) | Benefit(8) | Social Proof(7)              │
│  Urgency(7)    | Question(8)| Russian/Ukrainian(12)        │
│                                                             │
│  VISUAL CREATIVES (4 SVG designs)                           │
│  Dashboard | Trust Badges | Platform Logos | Stats          │
│                                                             │
│  TARGETING (3 tiers from 1,065 channels)                    │
│  Tier 1: 15 channels (score 70+) — 50K+ reach              │
│  Tier 2: 17 channels (score 60-69) — 40K+ reach            │
│  Tier 3: 5 channels (score 50-59) — 30K+ reach             │
│                                                             │
│  BUDGET (3 phases)                                          │
│  Phase 1: 210 TON / 14 days (Discovery)                    │
│  Phase 2: 420 TON / 14 days (Validation)                   │
│  Phase 3: 1500 TON / 30 days (Scale)                       │
│                                                             │
│  DESTINATION                                                │
│  ┌──────────┐        ┌──────────┐        ┌──────────┐      │
│  │ Channel  │───────▶│  Bot     │───────▶│  Sales   │      │
│  │  Join    │        │ Qualify  │        │  Team    │      │
│  └──────────┘        └──────────┘        └──────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Order

### Week 1: Launch Foundation
1. Set up Telegram channel with 20+ posts
2. Build qualification bot (or use ManyChat)
3. Fund ads.telegram.org with 210 TON ($735)
4. Launch Ad Set 01 (Core Media Buyers) with 4 copy variants
5. Start A/B Test 01 (Pain vs Benefit)

### Week 2: Expand & Optimize
6. Launch Ad Set 02 (Affiliate/CPA)
7. Kill bottom 50% of Phase 1 ads
8. Launch 3 new challenger copies
9. Start A/B Test 03 (CTA Variations)

### Week 3-4: Validate
10. Launch Ad Set 03 (Gambling/Betting)
11. Start A/B Test 04 (Channel vs Bot destination)
12. Start A/B Test 07 (Image vs Text)
13. Increase budget on winning ad sets
14. Begin direct channel outreach to top 10 admins

### Month 2: Scale
15. Launch remaining ad sets (04, 05, 06)
16. Run A/B Tests 05, 06, 08
17. Establish weekly creative refresh cadence
18. Target 20+ qualified leads/month
19. Negotiate 3-5 direct channel partnerships

---

## Platform Interface Quick Reference

From the Telegram Ads "Create Your Ad" screenshot:

| Field | Where to Find Value |
|-------|-------------------|
| **Ad title** | `ad_creatives/copy_variants/*.md` — use ad title from ad set files |
| **Ad text** | `ad_creatives/copy_variants/*.md` — all ≤160 chars |
| **URL to promote** | Your t.me channel or bot URL |
| **Show picture** | Check for image tests; uncheck for text-only |
| **Ad photo/video** | `ad_creatives/images/*.svg` — convert to PNG first |
| **CPM in Ton** | `budgets/*.md` — start at 0.5 TON |
| **Initial budget in Ton** | Per ad set files — start at 25-50 TON per ad |
| **Daily views limit** | Start at 1 — test 2 via AB-05 |
| **Initial status** | "On Hold" — review before activating |
| **Target > Channels** | Paste URLs from `targeting_lists/tier1_channels.csv` |
| **Ad identifier** | Use IDs from ad set files (e.g., CORE-MB-PAIN-01) |

### ⚠️ Country Exclusions (Platform-Enforced)
Ads will NOT show in: Russia, Ukraine, Israel, Palestine
→ See `targeting_lists/excluded_countries.md` for impact analysis

---

## File Index

| File | Purpose |
|------|---------|
| `ad_sets/adset_01_core_media_buyers.md` | Highest-priority ad set — launch first |
| `ad_sets/adset_02_affiliate_cpa.md` | Affiliate audience targeting |
| `ad_sets/adset_03_gambling_betting.md` | Gambling/iGaming vertical |
| `ad_sets/adset_04_ecommerce_nutra.md` | E-commerce & Nutra |
| `ad_sets/adset_05_platform_specific.md` | Google/Meta/TikTok-specific |
| `ad_sets/adset_06_broad_awareness.md` | Broad reach / crypto / general |
| `ab_tests/ab_test_01_pain_vs_benefit.md` | Copy angle test (START HERE) |
| `ab_tests/ab_test_02_social_proof.md` | Trust signal test |
| `ab_tests/ab_test_03_cta_variations.md` | CTA button test |
| `ab_tests/ab_test_04_destination.md` | Channel vs Bot test |
| `ab_tests/ab_test_05_frequency_cap.md` | Frequency cap test |
| `ab_tests/ab_test_06_cpm_bid.md` | Bid optimization test |
| `ab_tests/ab_test_07_image_vs_text.md` | Visual creative test |
| `ab_tests/ab_test_08_language.md` | RU vs EN copy test |
| `ad_creatives/copy_variants/pain_point_copies.md` | 8 pain-point copies |
| `ad_creatives/copy_variants/benefit_copies.md` | 8 benefit copies |
| `ad_creatives/copy_variants/social_proof_copies.md` | 7 social proof copies |
| `ad_creatives/copy_variants/urgency_copies.md` | 7 urgency copies |
| `ad_creatives/copy_variants/question_hook_copies.md` | 8 question hook copies |
| `ad_creatives/copy_variants/russian_copies.md` | 12 RU/UK copies |
| `ad_creatives/images/image_specs.md` | Design briefs |
| `ad_creatives/images/creative_01_*.svg` | Dashboard mockup |
| `ad_creatives/images/creative_02_*.svg` | Trust badges |
| `ad_creatives/images/creative_03_*.svg` | Platform logos |
| `ad_creatives/images/creative_04_*.svg` | Stats infographic |
| `targeting_lists/tier1_channels.csv` | 15 high-intent channels |
| `targeting_lists/tier2_channels.csv` | 17 medium-intent channels |
| `targeting_lists/tier3_channels.csv` | 5 broader channels |
| `targeting_lists/excluded_countries.md` | Country exclusion analysis |
| `budgets/phase1_discovery.md` | Weeks 1-2 budget |
| `budgets/phase2_validation.md` | Weeks 3-4 budget |
| `budgets/phase3_scale.md` | Month 2+ budget |
| `budgets/budget_calculator.py` | Python ROI calculator |
| **AI Funnel (Lead Processing)** | |
| `ai_funnel/README.md` | Architecture overview + setup guide |
| `ai_funnel/qualification_bot.py` | Bot API lead qualification (inline keyboards) |
| `ai_funnel/ai_responder.py` | Telethon AI userbot (LLM-powered DMs) |
| `ai_funnel/conversation_manager.py` | RAG integration + BANT scoring |
| `ai_funnel/lead_db.py` | Shared SQLite (leads, conversations, handoffs) |
| `ai_funnel/rate_limiter.py` | Anti-ban rate limiting + typing simulation |
| `ai_funnel/presence_manager.py` | Online/offline scheduling |
| `ai_funnel/system_prompts.py` | LLM prompts (EN/RU) + bot messages |
| `ai_funnel/channel_strategy.md` | Content calendar + channel setup |
| `ai_funnel/safety_guide.md` | Complete anti-ban playbook |
| `ai_funnel/config.example.env` | Environment configuration template |
| `ai_funnel/requirements.txt` | Python dependencies |
