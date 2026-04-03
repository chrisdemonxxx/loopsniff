#!/usr/bin/env python3
"""
Ban monitor — polls SMS-Man every 5 minutes, prints when ban is lifted.
Run: python3 ban_monitor.py
"""
import asyncio, aiohttp, os, sys, time
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("SMS_MAN_API_KEY")
BASE = "https://api.sms-man.com/control"

async def check():
    async with aiohttp.ClientSession() as http:
        async with http.get(f"{BASE}/get-number", params={
            "token": TOKEN, "country_id": 19, "application_id": 767
        }) as r:
            d = await r.json(content_type=None)
            if "number" in d:
                # Got a number — ban lifted! Reject it.
                async with http.get(f"{BASE}/set-status", params={
                    "token": TOKEN, "request_id": d["request_id"], "status": "reject"
                }) as r2:
                    pass
                return True
            return False

async def main():
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 300  # 5 min default
    print(f"Monitoring SMS-Man ban status every {interval}s...")
    while True:
        ts = time.strftime("%H:%M:%S")
        try:
            ok = await check()
            if ok:
                print(f"\n🎉 [{ts}] BAN LIFTED! Ready to create accounts.")
                # Beep
                print("\a" * 5)
                break
            else:
                print(f"[{ts}] Still banned...", end="\r")
        except Exception as e:
            print(f"[{ts}] Error: {e}")
        await asyncio.sleep(interval)

if __name__ == "__main__":
    asyncio.run(main())
