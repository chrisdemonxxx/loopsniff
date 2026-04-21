# 🤖 AI Auto-Responder Funnel — Complete Guide

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  TG Ad      │────▶│  Channel     │────▶│  Qualification  │
│  (click)    │     │  (social     │     │  Bot (Bot API)  │
│             │     │   proof)     │     │  - Inline KB    │
└─────────────┘     └──────────────┘     │  - BANT score   │
      │                                   │  - Lead capture │
      │         ┌──────────────────┐     └────────┬────────┘
      └────────▶│  Bot Direct Link │──────────────┘
                │  t.me/Bot?start  │              │
                └──────────────────┘              │ SQLite handoff
                                                  ▼
                                    ┌─────────────────────┐
                                    │  AI Userbot         │
                                    │  (Telethon/MTProto) │
                                    │  - Ollama Cloud LLM │
                                    │  - RAG context      │
                                    │  - BANT scoring     │
                                    │  - Human-like DMs   │
                                    │  - Rate limiting    │
                                    │  - Presence mgmt    │
                                    └─────────┬───────────┘
                                              │
                                    ┌─────────▼───────────┐
                                    │  Admin Notifications│
                                    │  (Hot lead alerts)  │
                                    └─────────────────────┘
```

## How It Works

### Layer 1: Telegram Ads → Channel
- Ad links to your channel (t.me/your_channel)
- Channel provides social proof: case studies, pricing, testimonials
- Pinned post directs users to the qualification bot
- See: `channel_strategy.md`

### Layer 2: Qualification Bot (Bot API)
- User starts the bot → welcome message + inline keyboards
- 3-step qualification: Platform → Budget → Timeline
- BANT scoring determines lead quality:
  - **Hot (≥75)**: Immediate handoff to userbot
  - **Warm (50-74)**: Handoff with more context
  - **Cool (<50)**: Bot nurtures with pricing/case studies
- File: `qualification_bot.py`

### Layer 3: AI Userbot (MTProto)
- Real Telegram account (not a bot — no bot label)
- Picks up qualified leads from shared SQLite database
- Generates human-like opening DM using LLM
- Handles entire conversation: qualify → present → close → payment
- Uses RAG for product knowledge + lead profile context
- File: `ai_responder.py`

---

## Quick Start

### 1. Prerequisites
```bash
# Python 3.11+
pip install -r requirements.txt

# Copy and edit config
cp config.example.env .env
nano .env
```

### 2. Configure `.env`
Essential values to set:
```bash
BOT_TOKEN=...          # From @BotFather
OLLAMA_API_KEY=...     # From ollama.com
USERBOT_PHONE=...      # Your TG phone number
PROXY_HOST=...         # Residential proxy
PROXY_PASSWORD=...     # Proxy auth
ADMIN_CHAT_ID=...      # Your TG user ID
```

### 3. Authenticate the Userbot
```bash
python ai_responder.py --auth
# Enter the OTP code sent to your phone
```

### 4. Test Everything
```bash
# Test userbot connection + RAG
python ai_responder.py --test

# Start qualification bot (terminal 1)
python qualification_bot.py

# Start AI responder (terminal 2)
python ai_responder.py
```

### 5. Link to Telegram Ads
In the TG Ads dashboard, set your ad destination to:
- **Channel**: `t.me/your_channel` (recommended — builds social proof first)
- **Bot**: `t.me/your_bot?start=campaign_name` (direct qualification)

---

## File Reference

| File | Purpose |
|------|---------|
| `qualification_bot.py` | Bot API qualification flow with inline keyboards |
| `ai_responder.py` | Telethon userbot with LLM-powered conversations |
| `conversation_manager.py` | LLM context, RAG integration, BANT scoring |
| `lead_db.py` | Shared SQLite database (leads, conversations, handoffs) |
| `rate_limiter.py` | Anti-ban rate limiting + typing simulation |
| `presence_manager.py` | Online/offline scheduling |
| `system_prompts.py` | LLM personality prompts (EN/RU) |
| `config.example.env` | Configuration template |
| `channel_strategy.md` | Content calendar + channel setup guide |
| `safety_guide.md` | Complete anti-ban playbook |
| `requirements.txt` | Python dependencies |

---

## Integration with Existing Infrastructure

This funnel is designed to work alongside the existing Kliqboost systems:

### RAG System (`/home/cjs/kliqboost/rag/`)
- ChromaDB with 208K+ lead profiles and 39 KB docs
- Provides product knowledge and lead context to the LLM
- Set `RAG_PATH` in `.env` to connect

### BANT Scorer (`/home/cjs/kliqboost/scoring/`)
- Budget/Ads-platform/Niche/Timeline scoring (0-100)
- Shared between qualification bot and AI responder
- Set `OUTREACH_PATH` in `.env` to connect

### Admin Autoresponder (`/home/cjs/kliqboost/userbot/admin_autoresponder.py`)
- Existing AI responder for admin account
- This funnel can run alongside it on a different account
- Or replace it with the funnel's `ai_responder.py`

---

## LLM Configuration

### Ollama Cloud (Recommended — Default)
```bash
OLLAMA_URL=https://ollama.com/v1/chat/completions
OLLAMA_MODEL=kimi-k2:1t
OLLAMA_API_KEY=your_key
```
- Free tier available
- Fast responses (2-5s)
- No content restrictions for business conversations
- OpenAI-compatible API

### Local Qwen3.5 via Baseten (Fallback)
```bash
OLLAMA_URL=http://localhost:4000/v1/chat/completions
OLLAMA_MODEL=qwen3.5-397b
OLLAMA_API_KEY=not_needed
```
- Already deployed at localhost:4000
- 397B parameter model (excellent quality)
- Slower (5-15s) but zero API costs
- Full control over the model

### Switching Models
Just update `.env` — the LLM client uses OpenAI-compatible API format,
so any provider that supports `/v1/chat/completions` works:
- OpenAI (GPT-4o)
- Anthropic (via proxy)
- DeepSeek
- Any local model via Ollama/vLLM

---

## Database Schema

Shared SQLite database (`funnel_leads.db`):

```
leads           — every user who enters the funnel
  ├── user_id (PK), username, first_name, language
  ├── source (tg_ad, tg_ad_campaign_name)
  ├── status, joined_channel, bot_qualified, userbot_active
  ├── bant_score, bant_tier, sales_stage
  └── created_at, updated_at

conversations   — full message history
  ├── user_id → leads
  ├── direction (inbound/outbound/system)
  ├── source (bot/userbot)
  └── text, bant_score, stage, ts

lead_memory     — extracted intelligence
  ├── user_id → leads
  ├── platform_interest, niche, budget_range, timeline
  └── pain_points, current_provider, ad_spend_monthly

handoffs        — bot → userbot queue
  ├── user_id → leads
  ├── reason, bot_summary, bant_score
  └── status (pending/picked), created_at, picked_at
```

---

## Monitoring & Metrics

### Bot Stats
```
/stats  (in the bot — admin only)
```

### Log Files
```bash
tail -f funnel.log
```

### Key Metrics
| Metric | Formula | Target |
|--------|---------|--------|
| Ad → Channel | Channel joins / Ad clicks | 30-40% |
| Channel → Bot | Bot starts / Channel joins | 50-60% |
| Bot → Qualified | Qualified / Bot starts | 70-80% |
| Qualified → DM | DM responses / Handoffs | 40-50% |
| DM → Hot Lead | Hot leads / DM conversations | 20-30% |
| Hot → Close | Closed deals / Hot leads | 15-25% |
| **Overall** | **Deals / Ad clicks** | **2-5%** |

---

## Troubleshooting

### Bot not responding
1. Check `BOT_TOKEN` in `.env`
2. Verify bot is running: `ps aux | grep qualification_bot`
3. Check logs: `tail -f funnel.log`

### Userbot not sending DMs
1. Check rate limits: `grep "Rate limit" funnel.log`
2. Verify authentication: `python ai_responder.py --test`
3. Check proxy: `curl --proxy http://user:pass@proxy:port http://ifconfig.me`
4. Check handoff queue: `sqlite3 funnel_leads.db "SELECT * FROM handoffs WHERE status='pending'"`

### LLM returning empty responses
1. Test API: `curl -X POST https://ollama.com/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d '{"model":"kimi-k2:1t","messages":[{"role":"user","content":"hi"}]}'`
2. Check API key in `.env`
3. Try fallback to local Qwen3.5

### Low conversion rates
1. Review system prompts — are they too aggressive/passive?
2. Check BANT scoring — are thresholds correct for your audience?
3. Analyse conversation logs — where do leads drop off?
4. A/B test different qualification flows
5. Update RAG knowledge base with more product info
