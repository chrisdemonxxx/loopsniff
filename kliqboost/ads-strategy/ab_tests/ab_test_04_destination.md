# A/B Test 04: Channel vs Bot Destination

## Test ID: AB-04
## Variable: Where the ad sends users (channel join vs bot interaction)
## Hypothesis: Bot destination captures more qualified leads; channel destination gets more raw joins
## Duration: 7 days minimum (needs conversion data)
## Min Sample: 3,000 impressions per variant

---

## Test Setup

### Variant A — CHANNEL DESTINATION
```yaml
ad_title: "Agency Ad Accounts"
ad_text: "Tired of account bans? Get verified agency ad accounts for Google, Meta & Taboola. Unlimited spend. Join our channel →"
url_to_promote: "https://t.me/kliqboost_bot"
cpm_in_ton: 0.5
initial_budget_ton: 40
daily_views_limit: 1
ad_identifier: "AB04-CHANNEL-A"
```
**Funnel**: Ad → Channel Join → Content nurturing → Bot/DM → Lead

### Variant B — BOT DESTINATION
```yaml
ad_title: "Agency Ad Accounts"
ad_text: "Tired of account bans? Get verified agency ad accounts for Google, Meta & Taboola. Unlimited spend. Get instant pricing →"
url_to_promote: "https://t.me/kliqboost_bot"
cpm_in_ton: 0.5
initial_budget_ton: 40
daily_views_limit: 1
ad_identifier: "AB04-BOT-B"
```
**Funnel**: Ad → Bot interaction → Qualification questions → Lead

---

## Metrics Comparison

| Metric | Channel Destination | Bot Destination |
|--------|-------------------|-----------------|
| Expected CTR | Higher (0.5%+) | Lower (0.3%+) |
| Join/Interaction Rate | High | Moderate |
| Lead Quality | Lower (unqualified joins) | Higher (pre-qualified) |
| Lead Volume | Higher | Lower |
| Cost per Qualified Lead | $40-$80 | $20-$50 |

## Decision Framework
```
IF bot_cpl < channel_cpl × 0.75:
    → Use bot as primary destination
ELIF channel_volume > bot_volume × 2:
    → Use channel for volume, bot for high-intent ad sets
ELSE:
    → Split: Channel for awareness ad sets, Bot for high-intent
```

## Notes
- Run this test AFTER determining winning copy (AB-01)
- Use the AB-01 winning copy for both variants here
- Track full-funnel: impressions → clicks → joins/interactions → qualified leads → sales
