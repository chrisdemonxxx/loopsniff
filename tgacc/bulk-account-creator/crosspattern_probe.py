#!/usr/bin/env python3
"""
Cross-Pattern TG Account Creator — SMS-Man Edition (v2)

Key fixes from SMS-Man guidance:
1. Uses Android Official API creds (api_id=6) — matches mobile app registration
2. Server IP is US (23.234.70.200) — US numbers are country-matched by default
3. Explicit SMS code request via Telethon
4. Rejects recycled numbers (SentCodeTypeApp) and gets refund
5. Conservative pacing to avoid re-triggering BAD_RATE
"""
import asyncio
import aiohttp
import json
import os
import sys
import time
import random
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
from telethon import TelegramClient
from telethon.tl.functions.auth import SignUpRequest
from telethon.errors import (
    PhoneNumberBannedError, FloodWaitError, PhoneNumberInvalidError
)

logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")

load_dotenv()
TOKEN = os.getenv("SMS_MAN_API_KEY")
# Android Official credentials — mimics real mobile app registration
ANDROID_API_ID = 6
ANDROID_API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"
BASE = "https://api.sms-man.com/control"
SESSIONS = Path("sessions")
SESSIONS.mkdir(exist_ok=True)

FIRST_NAMES = ["Alex","Jordan","Sam","Morgan","Chris","Taylor","Mike","David",
    "James","Robert","Daniel","Mark","Max","Nick","Tom","Ryan","Jack","Luke",
    "Andrew","Eric","Ben","Adam","Kevin","Sean","Matt","Will","Leo","Ian",
    "Sophie","Emma","Olivia","Ava","Mia","Isabella","Zoe","Lily","Chloe","Grace"]
LAST_NAMES = ["M","K","S","R","T","W","B","D","J","L","P","C","H","N","G","F",
    "V","Z","A","E"]

# Service pools — cheapest per country (non-TG services)
# Server IP is US, so US numbers have natural country match
COMBOS = [
    # USA $8.88 — best country match (our IP is US)
    {"cid": 5, "country": "USA", "app_id": 1694, "service": "Firebase", "cost": 8.88},
    {"cid": 5, "country": "USA", "app_id": 247, "service": "Locanto", "cost": 8.88},
    {"cid": 5, "country": "USA", "app_id": 3036, "service": "Neteller", "cost": 8.88},
    {"cid": 5, "country": "USA", "app_id": 3265, "service": "OKX", "cost": 8.88},
    {"cid": 5, "country": "USA", "app_id": 1584, "service": "microsoftazure", "cost": 8.88},
    {"cid": 5, "country": "USA", "app_id": 3634, "service": "Deliveroo", "cost": 8.88},
    # Nigeria $2.75 — cheaper but IP mismatch
    {"cid": 19, "country": "Nigeria", "app_id": 767, "service": "BEBOO", "cost": 2.75},
    {"cid": 19, "country": "Nigeria", "app_id": 4197, "service": "CallApp", "cost": 2.75},
    {"cid": 19, "country": "Nigeria", "app_id": 4926, "service": "AdaKami", "cost": 2.75},
    # Colombia $2.75 — cheaper but IP mismatch
    {"cid": 114, "country": "Colombia", "app_id": 4167, "service": "GlowRoad", "cost": 2.75},
    {"cid": 114, "country": "Colombia", "app_id": 4823, "service": "arenaplus", "cost": 2.75},
]

stats = {"probes": 0, "recycled": 0, "fresh": 0, "banned": 0, "created": 0, 
         "no_numbers": 0, "errors": 0, "sms_timeout": 0, "flood": 0, "spent": 0.0,
         "reject_ok": 0, "reject_fail": 0}

# Conservative pacing to avoid BAD_RATE re-trigger
DELAY_BETWEEN_PROBES = 8   # seconds between number requests
DELAY_AFTER_REJECT = 5     # seconds after rejecting a number
MAX_REJECTS_PER_COMBO = 5  # stop combo after N consecutive rejects


async def sms_get_number(http, country_id, app_id):
    async with http.get(f"{BASE}/get-number",
        params={"token": TOKEN, "country_id": country_id, "application_id": app_id}) as r:
        d = await r.json(content_type=None)
        if "error_code" in d:
            return None
        return d if "number" in d else None

async def sms_reject(http, req_id):
    """Reject number and get refund. Returns True if refunded."""
    try:
        await asyncio.sleep(3)  # Small delay before reject to look natural
        async with http.get(f"{BASE}/set-status",
            params={"token": TOKEN, "request_id": req_id, "status": "reject"}) as r:
            d = await r.json(content_type=None)
            txt = str(d).lower()
            if "early_cancel" in txt:
                stats["reject_fail"] += 1
                return False
            stats["reject_ok"] += 1
            return True
    except:
        stats["reject_fail"] += 1
        return False

async def sms_get_code(http, req_id, timeout=180):
    for i in range(timeout // 5):
        await asyncio.sleep(5)
        try:
            async with http.get(f"{BASE}/get-sms",
                params={"token": TOKEN, "request_id": req_id}) as r:
                d = await r.json(content_type=None)
                code = d.get("sms_code")
                if code:
                    return code
        except:
            pass
        if i % 6 == 0 and i > 0:
            logger.info(f"    Still waiting for SMS... {i*5}s")
    return None

async def sms_balance(http):
    async with http.get(f"{BASE}/get-balance", params={"token": TOKEN}) as r:
        d = await r.json(content_type=None)
        return float(d.get("balance", 0))


def make_client(sess_path):
    """Create Telethon client with Android Official credentials."""
    return TelegramClient(
        sess_path, ANDROID_API_ID, ANDROID_API_HASH,
        device_model="Samsung Galaxy S23",
        system_version="Android 14.0",
        app_version="10.14.5",
        lang_code="en",
        system_lang_code="en-US",
    )


async def probe_one(http, combo, probe_idx):
    """Probe a single number from a service pool."""
    stats["probes"] += 1
    
    num = await sms_get_number(http, combo["cid"], combo["app_id"])
    if not num:
        stats["no_numbers"] += 1
        return None
    
    phone = num["number"]
    req_id = num["request_id"]
    full = f"+{phone}" if not phone.startswith("+") else phone
    
    sess_path = str(SESSIONS / f"tg_{phone}")
    client = make_client(sess_path)
    created = False
    
    try:
        await client.connect()
        result = await client.send_code_request(full)
        code_type = type(result.type).__name__
        next_type = type(result.next_type).__name__ if result.next_type else "None"
        
        logger.info(f"  📱 +{phone}: {code_type} (next={next_type})")
        
        if "Sms" in code_type:
            stats["fresh"] += 1
            stats["spent"] += combo["cost"]
            logger.info(f"  🎉 FRESH! Waiting for SMS code (up to 3 min)...")
            
            code = await sms_get_code(http, req_id, timeout=180)
            if code:
                logger.info(f"  ✅ Code received: {code}")
                try:
                    await client.sign_in(full, code, phone_code_hash=result.phone_code_hash)
                    me = await client.get_me()
                    stats["created"] += 1
                    created = True
                    logger.info(f"  ✅ LOGGED IN: {me.first_name} id={me.id}")
                    return {"status": "ok", "phone": phone, "user_id": me.id, "type": "login"}
                except Exception as e:
                    if "PhoneNumberUnoccupied" in str(type(e).__name__) or "PhoneNumberUnoccupied" in str(e):
                        first = random.choice(FIRST_NAMES)
                        last = random.choice(LAST_NAMES)
                        await client(SignUpRequest(
                            phone_number=full,
                            phone_code_hash=result.phone_code_hash,
                            first_name=first, last_name=last,
                        ))
                        me = await client.get_me()
                        stats["created"] += 1
                        created = True
                        logger.info(f"  🆕 NEW ACCOUNT: {first} {last} id={me.id}")
                        return {"status": "ok", "phone": phone, "user_id": me.id, 
                                "name": f"{first} {last}", "type": "new"}
                    else:
                        logger.error(f"  Sign-in error: {type(e).__name__}: {e}")
                        stats["errors"] += 1
                        return None
            else:
                stats["sms_timeout"] += 1
                logger.warning(f"  ⏰ SMS timeout — number IS fresh but SMS didn't arrive")
                return {"status": "sms_timeout", "phone": phone, 
                        "combo": f"{combo['country']}/{combo['service']}"}
        
        elif "App" in code_type:
            stats["recycled"] += 1
            refunded = await sms_reject(http, req_id)
            logger.info(f"  ♻️  Recycled — {'refunded' if refunded else 'NO REFUND'}")
            return None
        
        elif "Call" in code_type:
            stats["recycled"] += 1
            await sms_reject(http, req_id)
            logger.info(f"  📞 Call-only — rejecting")
            return None
        
        else:
            logger.info(f"  ❓ Unknown type: {code_type}")
            await sms_reject(http, req_id)
            return None
            
    except PhoneNumberBannedError:
        stats["banned"] += 1
        await sms_reject(http, req_id)
        logger.info(f"  🚫 BANNED")
        return None
    except FloodWaitError as e:
        stats["flood"] += 1
        logger.warning(f"  ⏳ FloodWait {e.seconds}s")
        await sms_reject(http, req_id)
        raise
    except PhoneNumberInvalidError:
        stats["errors"] += 1
        await sms_reject(http, req_id)
        logger.info(f"  ❌ Invalid number")
        return None
    except Exception as e:
        stats["errors"] += 1
        await sms_reject(http, req_id)
        logger.error(f"  Error: {type(e).__name__}: {e}")
        return None
    finally:
        try:
            await client.disconnect()
        except:
            pass
        if not created:
            for ext in [".session", ".session-journal"]:
                p = Path(f"{sess_path}{ext}")
                if p.exists():
                    p.unlink()


async def main():
    probes_per_combo = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    
    async with aiohttp.ClientSession() as http:
        bal = await sms_balance(http)
        logger.info(f"Balance: ${bal:.2f}")
        logger.info(f"Using Android API creds (api_id=6) — mimics mobile app registration")
        logger.info(f"Server IP: US — prioritizing US numbers for country match")
        logger.info(f"Testing {len(COMBOS)} combos × {probes_per_combo} probes = {len(COMBOS)*probes_per_combo} total")
        logger.info(f"Pacing: {DELAY_BETWEEN_PROBES}s between probes, {DELAY_AFTER_REJECT}s after reject")
        logger.info("=" * 60)
        
        winners = []
        accounts = []
        
        for combo in COMBOS:
            logger.info(f"\n--- {combo['country']}/{combo['service']} (${combo['cost']}) ---")
            consecutive_rejects = 0
            
            for p in range(probes_per_combo):
                if consecutive_rejects >= MAX_REJECTS_PER_COMBO:
                    logger.info(f"  Skipping — {consecutive_rejects} consecutive rejects")
                    break
                
                tag = f"[{stats['probes']+1}] {combo['country']}/{combo['service']} #{p+1}"
                logger.info(f"{tag}: probing...")
                
                try:
                    result = await probe_one(http, combo, stats['probes'])
                except FloodWaitError as e:
                    wait = min(e.seconds + 10, 600)
                    logger.warning(f"FloodWait — pausing {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                
                if result:
                    if result["status"] == "ok":
                        accounts.append({**result, **combo, "ts": time.strftime("%Y-%m-%d %H:%M:%S")})
                        consecutive_rejects = 0
                        logger.info(f"  📊 Running: {stats['created']} created | {stats['fresh']} fresh | {stats['recycled']} recycled")
                    elif result["status"] == "sms_timeout":
                        winners.append(combo)
                        consecutive_rejects = 0
                else:
                    consecutive_rejects += 1
                
                # Conservative pacing
                await asyncio.sleep(DELAY_BETWEEN_PROBES)
        
        # Save results
        logger.info("\n" + "=" * 60)
        logger.info("FINAL RESULTS")
        logger.info("=" * 60)
        logger.info(f"Probes:     {stats['probes']}")
        logger.info(f"Recycled:   {stats['recycled']} ({stats['recycled']*100//max(stats['probes'],1)}%)")
        logger.info(f"Fresh:      {stats['fresh']} ({stats['fresh']*100//max(stats['probes'],1)}%)")
        logger.info(f"Created:    {stats['created']}")
        logger.info(f"SMS Timeout:{stats['sms_timeout']}")
        logger.info(f"Banned:     {stats['banned']}")
        logger.info(f"No stock:   {stats['no_numbers']}")
        logger.info(f"Errors:     {stats['errors']}")
        logger.info(f"Refunds:    {stats['reject_ok']} ok / {stats['reject_fail']} lost")
        logger.info(f"Spent:      ${stats['spent']:.2f}")
        
        if accounts:
            logger.info(f"\n✅ ACCOUNTS ({len(accounts)}):")
            for a in accounts:
                logger.info(f"  +{a['phone']} — {a.get('name','existing')} (id={a['user_id']}) [{a['country']}]")
        
        if winners:
            unique_winners = {f"{w['country']}/{w['service']}": w for w in winners}
            logger.info(f"\n🏆 WINNING COMBOS ({len(unique_winners)}):")
            for k, w in unique_winners.items():
                logger.info(f"  {k} @ ${w['cost']}")
        
        (SESSIONS / "probe_results.json").write_text(json.dumps({
            "stats": stats,
            "accounts": accounts,
            "winners": list({f"{w['country']}/{w['service']}": w for w in winners}.values()),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2))
        
        bal2 = await sms_balance(http)
        logger.info(f"\nBalance: ${bal:.2f} → ${bal2:.2f} (actual spent ${bal-bal2:.2f})")
        
        # Clean up failed session files
        for f in SESSIONS.glob("tg_*.session*"):
            phone = f.stem.replace("tg_", "").split(".")[0]
            if not any(a["phone"] == phone for a in accounts):
                f.unlink()
                

if __name__ == "__main__":
    asyncio.run(main())
