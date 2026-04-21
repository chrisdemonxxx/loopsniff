# 🛡️ Anti-Ban Safety Guide — TG Ads AI Funnel

## Why Accounts Get Banned

Telegram aggressively monitors for automated behavior. The #1 rule:

> **Never look like a bot, even though you are one.**

Common ban triggers:
1. **Sending too many messages too fast** — FloodWait → PeerFlood → ban
2. **Initiating conversations with strangers** — reported as spam
3. **Identical message patterns** — detected as automated
4. **Datacenter IPs** — instant flag
5. **24/7 online presence** — no real human is online all the time
6. **New accounts sending DMs** — need 3+ months age

---

## The Funnel Advantage

Our funnel is inherently safer than cold outreach because:

| Approach | Risk | Why |
|----------|------|-----|
| Cold DM outreach | 🔴 High | You initiate → spam reports |
| **Our funnel** | 🟢 Low | They come to us → legitimate conversation |

The user clicks our ad → joins our channel → interacts with our bot → 
our userbot follows up. At every step, **they initiated**.

---

## Account Setup Requirements

### The Userbot Account
- [ ] **Age**: 3+ months old (ideally 6+ months)
- [ ] **Organic history**: Real conversations, group memberships, channels
- [ ] **Complete profile**: Photo, bio, username, 2FA enabled
- [ ] **Phone number**: Active SIM, ideally same country as target audience
- [ ] **2FA**: Enabled with a strong password
- [ ] **Active sessions**: Mobile + desktop (looks natural)

### Proxy Configuration
- [ ] **Type**: Residential or mobile proxy (NEVER datacenter)
- [ ] **Location**: Same country as the phone number
- [ ] **Sticky session**: Same IP for weeks/months (not rotating)
- [ ] **Provider**: Proxy-Seller, BrightData, or similar tier-1

### Device Fingerprint
```python
# Our default — mimics a real iPhone
DEVICE = {
    "device_model": "iPhone 15 Pro Max",
    "system_version": "iOS 17.4",
    "app_version": "11.8.2",
    "lang_code": "en",
    "system_lang_code": "en-US",
}
```
Match the fingerprint to the phone number's country.

---

## Rate Limits (Default Configuration)

### Userbot Reply Limits
| Metric | Limit | Rationale |
|--------|-------|-----------|
| Replies per hour | 8 | ~1 every 7.5 min, well under Telegram's threshold |
| Replies per day | 50 | Leaves headroom for organic use |
| Min reply delay | 5s | Reading + thinking time |
| Max reply delay | 25s | Varies to look natural |
| Typing speed | 3-6 chars/sec | Average human typing speed on mobile |

### Qualification Bot Limits
The Bot API is much more permissive (bots are expected to be automated):
- 30 messages/sec to different users
- 1 message/sec to same user
- No ban risk for bot accounts

### Gradual Warm-up Schedule
```
Week 1:  5 replies/day   (getting started)
Week 2:  15 replies/day  (warming up)
Week 3:  30 replies/day  (normal)
Week 4+: 50 replies/day  (full capacity)
```

Adjust in `.env`:
```bash
MAX_REPLIES_PER_HOUR=8
MAX_REPLIES_PER_DAY=50
```

---

## Active Hours & Presence

### Schedule (Default: America/Los_Angeles)
```
Weekdays:  9 AM — 11 PM (online/offline cycling)
Weekends:  11 AM — 9 PM (reduced hours)
Off-hours: Away message → reply next morning
```

### Online/Offline Pattern
During active hours, the bot cycles:
- Online for 15-45 minutes
- Offline for 5-20 minutes
- Random jitter on start/end times (±15 min)

This prevents the "always online" flag.

---

## Message Safety Rules

### DO ✅
- Reply only to inbound messages (they texted us first)
- Use varied, natural language (the LLM handles this)
- Match the user's language (auto-detected)
- Send short messages (1-3 sentences)
- Use typing indicator before sending
- Wait random delays before replying
- Split long replies into multiple messages

### DON'T ❌
- Never send the same message to multiple people
- Never initiate conversations with strangers
- Never send links in the first message
- Never send more than 3 messages without a reply
- Never use markdown formatting in DMs
- Never reply during off-hours (use away message)
- Never bypass rate limits, even if they seem conservative

---

## Emergency Procedures

### FloodWait Error
If Telegram sends a FloodWait:
1. **Stop all activity immediately**
2. Wait the full duration + 50% extra
3. Reduce rate limits by 50%
4. Gradually increase over 1 week

### Spam Reports
If users report the account:
1. Stop auto-replies for 24 hours
2. Review recent conversations for aggressive behavior
3. Soften the system prompt
4. Resume at 50% rate

### Account Restriction
If Telegram restricts the account:
1. **Do NOT create a new account** — it will be linked
2. Wait the restriction period
3. Use the account manually for 1-2 weeks
4. Only then resume automated responses

---

## Monitoring Checklist

### Daily
- [ ] Check rate limiter stats (should never hit 100%)
- [ ] Review admin notifications for any escalations
- [ ] Verify no FloodWait errors in logs
- [ ] Check funnel stats (conversion rates)

### Weekly
- [ ] Review conversation quality (random sample of 5-10 chats)
- [ ] Check BANT score distribution (healthy: 40% warm+hot)
- [ ] Verify proxy IP hasn't changed
- [ ] Update system prompts if response quality drops

### Monthly
- [ ] Audit full conversation logs
- [ ] A/B test system prompt variations
- [ ] Review and update RAG knowledge base
- [ ] Check Ollama Cloud model updates (newer models may be better)

---

## Simultaneous Chat Capacity

### Ollama Cloud (kimi-k2:1t)
- **Concurrent requests**: Effectively unlimited (cloud-hosted)
- **Response time**: 2-5 seconds per reply
- **Rate limit**: ~60 requests/minute (free tier)
- **Practical capacity**: With our 8/hr reply limit, the LLM is never the bottleneck

### Local Qwen3.5-397B (via Baseten)
- **Concurrent requests**: 1-3 (depends on GPU memory)
- **Response time**: 5-15 seconds
- **Practical capacity**: 20-30 active conversations

### Realistic Throughput
With a single userbot account:
- **Peak**: 8 conversations active simultaneously
- **Daily**: 50 total reply interactions
- **Monthly**: ~1,500 reply interactions

For higher volume, run multiple userbot accounts (each with own phone + proxy).

---

## Legal & Ethical Considerations

1. **Terms of Service**: Automated replies on personal accounts technically violate 
   Telegram's ToS. Use at your own risk. The Bot API layer is fully compliant.

2. **Disclosure**: While the AI doesn't identify as a bot, users who ask directly 
   should not be lied to. The system prompt handles this by deflecting naturally.

3. **Data Privacy**: All conversation data is stored locally in SQLite. No data is 
   sent to third parties except the LLM provider (Ollama Cloud).

4. **Opt-out**: The BANT scorer detects negative intent ("stop", "unsubscribe", 
   "not interested") and immediately stops auto-replying.
