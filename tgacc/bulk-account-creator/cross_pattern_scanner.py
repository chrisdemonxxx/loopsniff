"""
Cross-Pattern SMS-Man → Telegram Fresh Number Scanner

Strategy: Order numbers from non-Telegram services (IVI, Nike, Walmart, etc.)
on SMS-Man and test them with Telethon. Numbers from different service pools
may be fresher (never used for TG) even though they're recycled for that service.

Finds winning service×country combos that yield SentCodeTypeSms (fresh for TG).
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

logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")

load_dotenv()

TOKEN = os.getenv("SMS_MAN_API_KEY")
API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
BASE = "https://api.sms-man.com/control"
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

# Top-tier countries to test
COUNTRIES = {
    5: "USA",
    16: "Canada",
    175: "UK",
    86: "Germany",
    118: "France",
    78: "Australia",
    95: "Netherlands",
    116: "Poland",
    68: "Spain",
    57: "Italy",
    # Cheaper countries that might work
    6: "Indonesia",
    10: "Vietnam",
    22: "India",
    114: "Colombia",
    21: "Egypt",
    313: "Tanzania",
    19: "Nigeria",
    41: "Philippines",
}


async def get_cheap_services(session, country_id: int, max_price: float = 1.60):
    """Get all services under max_price for a country."""
    try:
        async with session.get(f"{BASE}/get-prices",
            params={"token": TOKEN, "country_id": country_id}) as r:
            data = await r.json(content_type=None)
            if isinstance(data, dict) and "error_code" not in data:
                cheap = []
                for app_id, info in data.items():
                    if isinstance(info, dict):
                        cost = float(info.get("cost", 999))
                        count = int(info.get("count", 0))
                        name = info.get("application", "")
                        # Skip Telegram itself — those pools are heavily recycled for TG
                        if "telegram" in name.lower():
                            continue
                        if cost <= max_price and count > 0:
                            cheap.append({
                                "app_id": int(app_id),
                                "name": name,
                                "cost": cost,
                                "count": count,
                            })
                # Sort by count (more numbers = better pool)
                cheap.sort(key=lambda x: x["count"], reverse=True)
                return cheap
            return []
    except Exception as e:
        logger.error(f"get_prices error for country {country_id}: {e}")
        return []


async def get_number(session, country_id: int, app_id: int):
    """Get a number from SMS-Man."""
    try:
        async with session.get(f"{BASE}/get-number",
            params={"token": TOKEN, "country_id": country_id, "application_id": app_id}) as r:
            data = await r.json(content_type=None)
            if "number" in data:
                return data
            return None
    except:
        return None


async def reject_number(session, request_id: int):
    """Reject/cancel a number."""
    try:
        async with session.get(f"{BASE}/set-status",
            params={"token": TOKEN, "request_id": request_id, "status": "reject"}) as r:
            return await r.json(content_type=None)
    except:
        return None


async def get_sms_code(session, request_id: int, timeout: int = 180):
    """Poll for SMS code."""
    for i in range(timeout // 5):
        await asyncio.sleep(5)
        try:
            async with session.get(f"{BASE}/get-sms",
                params={"token": TOKEN, "request_id": request_id}) as r:
                data = await r.json(content_type=None)
                code = data.get("sms_code")
                if code:
                    return code
        except:
            pass
    return None


async def probe_number(http_session, country_id: int, country_name: str,
                       app_id: int, app_name: str, probe_num: int):
    """
    Get a number from a service pool and test if it's fresh for Telegram.
    Returns result dict or None.
    """
    from telethon import TelegramClient
    from telethon.tl.functions.auth import SignUpRequest
    
    # Get number
    num_data = await get_number(http_session, country_id, app_id)
    if not num_data:
        return {"status": "no_numbers", "country": country_name, "service": app_name}

    phone = num_data["number"]
    request_id = num_data["request_id"]
    full_phone = f"+{phone}" if not phone.startswith("+") else phone
    
    session_path = f"sessions/probe_{phone}"
    client = TelegramClient(session_path, API_ID, API_HASH)
    
    try:
        await client.connect()
        
        result = await client.send_code_request(full_phone)
        code_type = type(result.type).__name__
        
        if "Sms" in code_type:
            # FRESH NUMBER! Wait for SMS code
            logger.info(f"  🎉 FRESH! {full_phone} ({country_name}/{app_name}) — waiting for SMS...")
            
            code = await get_sms_code(http_session, request_id, timeout=180)
            if code:
                logger.info(f"  ✅ Got code: {code} for {full_phone}")
                try:
                    await client.sign_in(full_phone, code, phone_code_hash=result.phone_code_hash)
                    me = await client.get_me()
                    logger.info(f"  ✅ SIGNED IN: {me.first_name} (id={me.id})")
                    return {
                        "status": "logged_in",
                        "phone": phone, "full_phone": full_phone,
                        "country": country_name, "service": app_name,
                        "user_id": me.id, "first_name": me.first_name,
                    }
                except Exception as sign_err:
                    if "PhoneNumberUnoccupied" in str(sign_err):
                        # Brand new number — sign up!
                        first = random.choice(["Alex","Jordan","Sam","Morgan","Chris","Taylor","Mike","David","James","Robert","Daniel","Mark","Max","Nick","Tom","Ryan","Jack","Luke","Andrew","Eric"])
                        last = random.choice(["M","K","S","R","T","W","B","D","J","L","P","C","H","N"])
                        try:
                            await client(SignUpRequest(
                                phone_number=full_phone,
                                phone_code_hash=result.phone_code_hash,
                                first_name=first,
                                last_name=last,
                            ))
                            me = await client.get_me()
                            logger.info(f"  🆕 CREATED: {me.first_name} {me.last_name} (id={me.id})")
                            return {
                                "status": "created",
                                "phone": phone, "full_phone": full_phone,
                                "country": country_name, "service": app_name,
                                "user_id": me.id, "first_name": first, "last_name": last,
                            }
                        except Exception as signup_err:
                            logger.error(f"  Signup failed: {signup_err}")
                            return {
                                "status": "signup_failed",
                                "phone": phone, "country": country_name,
                                "service": app_name, "error": str(signup_err),
                            }
                    else:
                        logger.error(f"  Sign-in error: {sign_err}")
                        return {
                            "status": "signin_failed",
                            "phone": phone, "country": country_name,
                            "service": app_name, "error": str(sign_err),
                        }
            else:
                logger.warning(f"  ⏰ SMS timeout for {full_phone}")
                return {
                    "status": "sms_timeout",
                    "phone": phone, "country": country_name, "service": app_name,
                }
        
        elif "App" in code_type:
            # Recycled — reject and refund
            await reject_number(http_session, request_id)
            return {
                "status": "recycled",
                "phone": phone, "country": country_name, "service": app_name,
            }
        
        elif "Call" in code_type:
            await reject_number(http_session, request_id)
            return {
                "status": "call_delivery",
                "phone": phone, "country": country_name, "service": app_name,
            }
        
        else:
            await reject_number(http_session, request_id)
            return {
                "status": f"unknown_{code_type}",
                "phone": phone, "country": country_name, "service": app_name,
            }
            
    except Exception as e:
        err = str(e)
        await reject_number(http_session, request_id)
        
        if "banned" in err.lower():
            return {"status": "banned", "phone": phone, "country": country_name, "service": app_name}
        elif "flood" in err.lower():
            return {"status": "flood", "phone": phone, "country": country_name, "service": app_name, "error": err}
        else:
            return {"status": "error", "phone": phone, "country": country_name, "service": app_name, "error": err}
    finally:
        try:
            await client.disconnect()
        except:
            pass
        # Clean up failed session files
        for ext in [".session", ".session-journal"]:
            p = Path(f"{session_path}{ext}")
            if p.exists():
                # Only delete if probe failed (not created/logged_in)
                pass


async def phase1_discover(max_price: float = 1.60):
    """Phase 1: Discover cheap service×country combos."""
    logger.info("=" * 60)
    logger.info("PHASE 1: Discovering cheap service×country combos")
    logger.info(f"Max price: ${max_price}")
    logger.info("=" * 60)
    
    combos = []
    async with aiohttp.ClientSession() as s:
        for country_id, country_name in COUNTRIES.items():
            services = await get_cheap_services(s, country_id, max_price)
            if services:
                # Take top 10 services by availability
                top = services[:10]
                logger.info(f"  {country_name}: {len(services)} services ≤${max_price}, top: {', '.join(x['name'] for x in top[:5])}")
                for svc in top:
                    combos.append({
                        "country_id": country_id,
                        "country": country_name,
                        "app_id": svc["app_id"],
                        "service": svc["name"],
                        "cost": svc["cost"],
                        "count": svc["count"],
                    })
            else:
                logger.info(f"  {country_name}: No services ≤${max_price}")
            await asyncio.sleep(0.3)
    
    logger.info(f"\nTotal combos to test: {len(combos)}")
    return combos


async def phase2_probe(combos: list, probes_per_combo: int = 2):
    """Phase 2: Probe each combo with Telethon to find fresh numbers."""
    logger.info("=" * 60)
    logger.info(f"PHASE 2: Probing {len(combos)} combos ({probes_per_combo} probes each)")
    logger.info("=" * 60)
    
    results = []
    winners = []
    
    async with aiohttp.ClientSession() as s:
        balance_resp = await s.get(f"{BASE}/get-balance", params={"token": TOKEN})
        bal_data = await balance_resp.json(content_type=None)
        logger.info(f"Balance: ${bal_data.get('balance', '?')}")
    
    probe_num = 0
    async with aiohttp.ClientSession() as http:
        for combo in combos:
            for attempt in range(probes_per_combo):
                probe_num += 1
                logger.info(f"[{probe_num}] {combo['country']}/{combo['service']} (${combo['cost']}) #{attempt+1}...")
                
                result = await probe_number(
                    http, combo["country_id"], combo["country"],
                    combo["app_id"], combo["service"], probe_num,
                )
                
                if result:
                    results.append(result)
                    status = result["status"]
                    
                    if status in ("created", "logged_in"):
                        logger.info(f"  🏆 WINNER: {combo['country']}/{combo['service']} → {result['full_phone']}")
                        winners.append({**combo, **result})
                    elif status == "recycled":
                        logger.info(f"  ♻️ Recycled (refunded)")
                    elif status == "banned":
                        logger.info(f"  🚫 Banned number")
                    elif status == "flood":
                        logger.warning(f"  ⏳ FloodWait — pausing 60s...")
                        await asyncio.sleep(60)
                    elif status == "sms_timeout":
                        # Fresh but SMS not received — still a winning combo!
                        logger.info(f"  ⏰ Fresh but SMS timed out — combo still promising")
                        winners.append({**combo, **result, "note": "sms_timeout_but_fresh"})
                    else:
                        logger.info(f"  Status: {status}")
                
                # Brief pause between probes
                await asyncio.sleep(2)
    
    return results, winners


async def phase3_scale(winners: list, target_accounts: int = 100):
    """Phase 3: Scale up winning combos to create bulk accounts."""
    if not winners:
        logger.warning("No winning combos found — nothing to scale")
        return []
    
    logger.info("=" * 60)
    logger.info(f"PHASE 3: Scaling {len(winners)} winning combos → target {target_accounts} accounts")
    logger.info("=" * 60)
    
    # Group winners by combo pattern
    combo_scores = {}
    for w in winners:
        key = f"{w['country']}/{w['service']}"
        if key not in combo_scores:
            combo_scores[key] = {"count": 0, "combo": w}
        combo_scores[key]["count"] += 1
    
    # Sort by success count
    ranked = sorted(combo_scores.items(), key=lambda x: x[1]["count"], reverse=True)
    logger.info("Ranked combos:")
    for key, data in ranked:
        logger.info(f"  {key}: {data['count']} successes @ ${data['combo']['cost']}")
    
    created = []
    accounts_needed = target_accounts
    
    async with aiohttp.ClientSession() as http:
        for key, data in ranked:
            combo = data["combo"]
            probes_to_try = min(accounts_needed * 3, 50)  # ~33% success rate estimate
            
            logger.info(f"\nScaling {key} — trying {probes_to_try} probes...")
            
            for i in range(probes_to_try):
                if len(created) >= target_accounts:
                    break
                
                result = await probe_number(
                    http, combo["country_id"], combo["country"],
                    combo["app_id"], combo["service"], len(created) + 1,
                )
                
                if result and result["status"] in ("created", "logged_in"):
                    created.append(result)
                    logger.info(f"  [{len(created)}/{target_accounts}] ✅ {result['full_phone']}")
                elif result and result["status"] == "flood":
                    logger.warning("  FloodWait — pausing 120s...")
                    await asyncio.sleep(120)
                
                await asyncio.sleep(2)
    
    return created


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, default=0, help="Run specific phase (1=discover, 2=probe, 3=scale, 0=all)")
    parser.add_argument("--max-price", type=float, default=1.60, help="Max price per number")
    parser.add_argument("--probes", type=int, default=2, help="Probes per combo in phase 2")
    parser.add_argument("--target", type=int, default=100, help="Target accounts in phase 3")
    args = parser.parse_args()
    
    results_file = SESSIONS_DIR / "scan_results.json"
    winners_file = SESSIONS_DIR / "winners.json"
    accounts_file = SESSIONS_DIR / "created_accounts.json"
    
    if args.phase in (0, 1):
        combos = await phase1_discover(args.max_price)
        # Save combos
        Path(SESSIONS_DIR / "combos.json").write_text(json.dumps(combos, indent=2))
        logger.info(f"Saved {len(combos)} combos to sessions/combos.json")
    
    if args.phase in (0, 2):
        if args.phase == 2:
            combos = json.loads(Path(SESSIONS_DIR / "combos.json").read_text())
        
        results, winners = await phase2_probe(combos, args.probes)
        
        # Save results
        results_file.write_text(json.dumps(results, indent=2))
        winners_file.write_text(json.dumps(winners, indent=2))
        
        logger.info(f"\n{'='*60}")
        logger.info(f"PHASE 2 RESULTS:")
        logger.info(f"  Total probes: {len(results)}")
        logger.info(f"  Recycled: {sum(1 for r in results if r['status']=='recycled')}")
        logger.info(f"  Fresh (SMS): {sum(1 for r in results if r['status'] in ('created','logged_in','sms_timeout'))}")
        logger.info(f"  Banned: {sum(1 for r in results if r['status']=='banned')}")
        logger.info(f"  Winners: {len(winners)}")
        for w in winners:
            logger.info(f"    {w['country']}/{w['service']} → {w.get('full_phone','?')} [{w['status']}]")
    
    if args.phase in (0, 3):
        if args.phase == 3:
            winners = json.loads(winners_file.read_text())
        
        if winners:
            created = await phase3_scale(winners, args.target)
            
            # Save/append created accounts
            existing = []
            if accounts_file.exists():
                existing = json.loads(accounts_file.read_text())
            existing.extend(created)
            accounts_file.write_text(json.dumps(existing, indent=2))
            
            logger.info(f"\n{'='*60}")
            logger.info(f"FINAL: {len(created)} accounts created, {len(existing)} total")
            for a in created:
                logger.info(f"  {a['full_phone']} ({a['country']}) — {a.get('first_name','')} (id={a.get('user_id','')})")
        else:
            logger.warning("No winners to scale — run phase 2 first")


if __name__ == "__main__":
    asyncio.run(main())
