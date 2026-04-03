"""
Browser-based Telegram Account Registration via Roxy Browser + web.telegram.org

Uses the OFFICIAL Telegram web client, which:
- Uses Telegram's own API credentials (not third-party)
- May handle SMS delivery differently
- Supports registration flow natively
"""
import asyncio
import json
import os
import sys
import time
import random
import aiohttp
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")

load_dotenv()

SMS_MAN_KEY = os.getenv("SMS_MAN_API_KEY")
ROXY_KEY = os.getenv("ROXY_API_KEY", "")
ROXY_HOST = os.getenv("ROXY_API_HOST", "http://127.0.0.1:50000")
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

# Countries to try — cheapest on SMS-Man with working allocations
COUNTRIES = [
    {"name": "Sierra Leone", "code": "sl", "sms_id": 307, "prefix": "+232"},
    {"name": "Zambia", "code": "zm", "sms_id": 377, "prefix": "+260"},
    {"name": "Burundi", "code": "bi", "sms_id": 340, "prefix": "+257"},
    {"name": "Ghana", "code": "gh", "sms_id": 314, "prefix": "+233"},
    {"name": "Indonesia", "code": "id", "sms_id": 6, "prefix": "+62"},
    {"name": "Egypt", "code": "eg", "sms_id": 21, "prefix": "+20"},
    {"name": "Colombia", "code": "co", "sms_id": 114, "prefix": "+57"},
    {"name": "Vietnam", "code": "vn", "sms_id": 10, "prefix": "+84"},
    {"name": "Rwanda", "code": "rw", "sms_id": 339, "prefix": "+250"},
    {"name": "Angola", "code": "ao", "sms_id": 344, "prefix": "+244"},
    {"name": "Tanzania", "code": "tz", "sms_id": 313, "prefix": "+255"},
    {"name": "Tajikistan", "code": "tj", "sms_id": 143, "prefix": "+992"},
]

class SMSMan:
    """Minimal SMS-Man client."""
    BASE = "https://api.sms-man.com/control"

    def __init__(self):
        self.token = SMS_MAN_KEY

    async def get_balance(self):
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{self.BASE}/get-balance", params={"token": self.token}) as r:
                d = await r.json(content_type=None)
                return float(d.get("balance", 0))

    async def get_number(self, country_id: int, app_id: int = 3):
        async with aiohttp.ClientSession() as s:
            params = {"token": self.token, "country_id": country_id, "application_id": app_id}
            async with s.get(f"{self.BASE}/get-number", params=params) as r:
                d = await r.json(content_type=None)
                if "error_code" in d:
                    return None
                return d

    async def get_sms(self, request_id):
        async with aiohttp.ClientSession() as s:
            params = {"token": self.token, "request_id": request_id}
            async with s.get(f"{self.BASE}/get-sms", params=params) as r:
                d = await r.json(content_type=None)
                return d

    async def reject_number(self, request_id):
        async with aiohttp.ClientSession() as s:
            params = {"token": self.token, "request_id": request_id}
            async with s.get(f"{self.BASE}/set-status", params={**params, "status": "reject"}) as r:
                return await r.json(content_type=None)


class RoxyManager:
    """Manage Roxy Browser profiles for registration."""

    def __init__(self):
        self.host = ROXY_HOST
        self.workspace_id = None

    async def _request(self, method, path, json_data=None):
        async with aiohttp.ClientSession() as s:
            headers = {"Content-Type": "application/json"}
            if ROXY_KEY:
                headers["Authorization"] = f"Bearer {ROXY_KEY}"
            async with s.request(method, f"{self.host}{path}", json=json_data, headers=headers) as r:
                return await r.json(content_type=None)

    async def get_workspace(self):
        d = await self._request("GET", "/browser/workspace")
        rows = d.get("data", {}).get("rows", [])
        if rows:
            self.workspace_id = rows[0]["id"]
            return self.workspace_id
        raise Exception("No Roxy workspace found")

    async def create_profile(self, name: str, proxy_str: str = None):
        ws = self.workspace_id or await self.get_workspace()
        profile = {
            "workspaceId": ws,
            "windowName": name,
            "os": "Windows",
            "osVersion": "11",
            "fingerInfo": {
                "isLanguageBaseIp": True,
                "language": "en-US",
                "isTimeZone": True,
                "timeZone": "GMT-05:00 America/New_York",
                "canvas": True,
                "webGL": True,
                "audioContext": True,
                "hardwareConcurrent": str(random.choice([4, 8, 12])),
                "deviceMemory": str(random.choice([4, 8])),
                "openWidth": "1280",
                "openHeight": "800",
            },
        }
        if proxy_str:
            parts = proxy_str.split(":")
            profile["proxyInfo"] = {
                "proxyMethod": "custom",
                "proxyCategory": "HTTP",
                "ipType": "IPV4",
                "host": parts[0],
                "port": parts[1],
                "proxyUserName": parts[2] if len(parts) > 2 else "",
                "proxyPassword": ":".join(parts[3:]) if len(parts) > 3 else "",
            }
        else:
            profile["proxyInfo"] = {"proxyMethod": "custom", "proxyCategory": "noproxy"}

        d = await self._request("POST", "/browser/create", profile)
        if d.get("code") != 0:
            raise Exception(f"Create profile failed: {d}")
        profile_data = d.get("data", {})
        dir_id = profile_data.get("dirId") or profile_data.get("id")
        logger.info(f"Created profile: {name} → {dir_id}")
        return dir_id

    async def start_profile(self, dir_id: str):
        ws = self.workspace_id or await self.get_workspace()
        d = await self._request("POST", "/browser/open", {"workspaceId": ws, "dirId": dir_id})
        if d.get("code") != 0:
            raise Exception(f"Start profile failed: {d}")
        info = d.get("data", {})
        debug_port = info.get("debugPort") or info.get("debug_port")
        ws_url = info.get("ws_endpoint") or info.get("wsEndpoint") or info.get("ws")
        if not ws_url and debug_port:
            ws_url = f"ws://127.0.0.1:{debug_port}"
        logger.info(f"Profile started: {dir_id}, CDP: {ws_url or debug_port}")
        return {"ws_endpoint": ws_url, "debug_port": debug_port, **info}

    async def stop_profile(self, dir_id: str):
        ws = self.workspace_id or await self.get_workspace()
        await self._request("POST", "/browser/close", {"workspaceId": ws, "dirId": dir_id})
        logger.info(f"Profile stopped: {dir_id}")

    async def delete_profile(self, dir_id: str):
        ws = self.workspace_id or await self.get_workspace()
        await self._request("POST", "/browser/delete", {"workspaceId": ws, "dirId": dir_id})


async def register_via_browser(sms: SMSMan, roxy: RoxyManager, country: dict, attempt: int):
    """
    Register a Telegram account via web.telegram.org in Roxy Browser.
    
    Flow:
    1. Get number from SMS-Man
    2. Create & start Roxy profile
    3. Navigate to web.telegram.org/a
    4. Enter phone number
    5. Wait for SMS code
    6. Enter code → sign up
    """
    from playwright.async_api import async_playwright

    # Step 1: Get phone number
    logger.info(f"[{attempt}] Getting number from {country['name']}...")
    num_data = await sms.get_number(country["sms_id"])
    if not num_data:
        logger.warning(f"[{attempt}] No numbers available for {country['name']}")
        return None

    phone = num_data["number"]
    request_id = num_data["request_id"]
    full_phone = f"+{phone}" if not phone.startswith("+") else phone
    logger.info(f"[{attempt}] Got number: {full_phone} (req={request_id})")

    profile_id = None
    try:
        # Step 2: Create & start Roxy profile
        profile_name = f"tg-reg-{phone[-6:]}-{attempt}"
        profile_id = await roxy.create_profile(profile_name)
        await asyncio.sleep(2)
        
        cdp_info = await roxy.start_profile(profile_id)
        ws_endpoint = cdp_info.get("ws_endpoint")
        debug_port = cdp_info.get("debug_port")
        
        if not ws_endpoint and not debug_port:
            logger.error(f"[{attempt}] No CDP endpoint returned")
            await sms.reject_number(request_id)
            return None

        await asyncio.sleep(3)  # Wait for browser to fully start

        # Step 3: Connect Playwright
        cdp_url = ws_endpoint or f"http://127.0.0.1:{debug_port}"
        
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
            
            # Step 4: Navigate to web.telegram.org
            logger.info(f"[{attempt}] Navigating to web.telegram.org...")
            await page.goto("https://web.telegram.org/a/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(8)  # Extra wait for SPA to render
            
            # Take screenshot for debugging
            screenshot_path = f"/tmp/tg_reg_{attempt}_01_landing.png"
            await page.screenshot(path=screenshot_path)
            logger.info(f"[{attempt}] Screenshot saved: {screenshot_path}")
            
            # Look for "Log in by phone Number" or similar
            # The web app might show a QR code login first
            # We need to find and click "Log in by phone number" link
            
            # Try to find the phone login option
            phone_login = await page.query_selector('text="Log in by phone Number"')
            if not phone_login:
                phone_login = await page.query_selector('text="LOG IN BY PHONE NUMBER"')
            if not phone_login:
                phone_login = await page.query_selector('[href="#/login"]')
            if not phone_login:
                # Try clicking on any element that mentions "phone"
                phone_login = await page.query_selector('a:has-text("phone")')
            
            if phone_login:
                await phone_login.click()
                await asyncio.sleep(2)
            
            # Screenshot after clicking phone login
            await page.screenshot(path=f"/tmp/tg_reg_{attempt}_02_phone_form.png")
            
            # Find phone input field
            phone_input = await page.query_selector('input[type="tel"]')
            if not phone_input:
                phone_input = await page.query_selector('#sign-in-phone-number')
            if not phone_input:
                phone_input = await page.query_selector('input[placeholder*="phone"]')
            if not phone_input:
                # Try any visible input
                phone_input = await page.query_selector('input:visible')
            
            if not phone_input:
                logger.error(f"[{attempt}] Could not find phone input field")
                await page.screenshot(path=f"/tmp/tg_reg_{attempt}_error_no_input.png")
                await sms.reject_number(request_id)
                return None
            
            # Clear and type phone number
            await phone_input.click()
            await phone_input.fill("")
            await asyncio.sleep(0.5)
            
            # Type the full phone number with country code
            await phone_input.type(full_phone, delay=100)
            await asyncio.sleep(1)
            
            await page.screenshot(path=f"/tmp/tg_reg_{attempt}_03_number_entered.png")
            
            # Click Next/Continue button
            next_btn = await page.query_selector('button:has-text("Next")')
            if not next_btn:
                next_btn = await page.query_selector('button:has-text("NEXT")')
            if not next_btn:
                next_btn = await page.query_selector('.btn-primary')
            if not next_btn:
                # Press Enter
                await phone_input.press("Enter")
            else:
                await next_btn.click()
            
            await asyncio.sleep(3)
            await page.screenshot(path=f"/tmp/tg_reg_{attempt}_04_after_next.png")
            
            # Check if there's a confirmation dialog
            confirm_btn = await page.query_selector('button:has-text("Yes")')
            if confirm_btn:
                await confirm_btn.click()
                await asyncio.sleep(3)
            
            await page.screenshot(path=f"/tmp/tg_reg_{attempt}_05_code_page.png")
            
            # Step 5: Wait for SMS code from SMS-Man
            logger.info(f"[{attempt}] Waiting for SMS code (up to 180s)...")
            code = None
            for poll in range(36):  # 36 * 5 = 180 seconds
                await asyncio.sleep(5)
                sms_data = await sms.get_sms(request_id)
                sms_code = sms_data.get("sms_code")
                if sms_code:
                    code = sms_code
                    logger.info(f"[{attempt}] ✅ SMS code received: {code}")
                    break
                if poll % 6 == 0:
                    logger.info(f"[{attempt}] Still waiting... ({poll * 5}s)")
            
            if not code:
                logger.warning(f"[{attempt}] SMS code not received within 180s")
                await page.screenshot(path=f"/tmp/tg_reg_{attempt}_timeout.png")
                await sms.reject_number(request_id)
                return None
            
            # Step 6: Enter the code
            # The code input might be individual digit inputs or a single field
            code_input = await page.query_selector('input[type="tel"]:visible')
            if not code_input:
                code_input = await page.query_selector('#sign-in-code')
            if not code_input:
                code_input = await page.query_selector('input:visible')
            
            if code_input:
                await code_input.click()
                await code_input.type(code, delay=150)
                await asyncio.sleep(3)
            else:
                # Try typing directly (some UIs auto-focus on code input)
                await page.keyboard.type(code, delay=150)
                await asyncio.sleep(3)
            
            await page.screenshot(path=f"/tmp/tg_reg_{attempt}_06_code_entered.png")
            
            # Check for registration form (name input = fresh account)
            await asyncio.sleep(3)
            name_input = await page.query_selector('input[placeholder*="name" i]')
            if not name_input:
                name_input = await page.query_selector('input[placeholder*="Name" i]')
            
            if name_input:
                # Fresh account! Complete registration
                first_name = random.choice([
                    "Alex", "Jordan", "Sam", "Morgan", "Chris", "Taylor",
                    "Mike", "David", "James", "Robert", "Daniel", "Mark",
                    "Max", "Nick", "Tom", "Ryan", "Jack", "Luke",
                ])
                last_name = random.choice([
                    "M", "K", "S", "R", "T", "W", "B", "D", "J", "L",
                ])
                
                await name_input.fill(first_name)
                last_input = await page.query_selector('input[placeholder*="last" i]')
                if last_input:
                    await last_input.fill(last_name)
                
                # Click sign up/start messaging button
                signup_btn = await page.query_selector('button:has-text("Start")')
                if not signup_btn:
                    signup_btn = await page.query_selector('button:has-text("SIGN UP")')
                if not signup_btn:
                    signup_btn = await page.query_selector('.btn-primary')
                if signup_btn:
                    await signup_btn.click()
                
                await asyncio.sleep(5)
                logger.info(f"[{attempt}] 🆕 NEW ACCOUNT CREATED: {full_phone} as {first_name} {last_name}")
            else:
                # Existing account - we logged in
                logger.info(f"[{attempt}] 🔓 LOGGED INTO EXISTING ACCOUNT: {full_phone}")
            
            await page.screenshot(path=f"/tmp/tg_reg_{attempt}_07_final.png")
            
            # Step 7: Now authenticate with Telethon to get session file
            # The browser logged us in, now we need to get a Telethon session too
            # We can do this by extracting localStorage/cookies or by doing
            # a Telethon sign-in with the same phone and code
            
            logger.info(f"[{attempt}] ✅ SUCCESS — {full_phone}")
            
            # Save result
            result = {
                "phone": phone,
                "full_phone": full_phone,
                "country": country["name"],
                "request_id": request_id,
                "profile_id": profile_id,
                "status": "registered",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            
            # Save to results file
            results_file = SESSIONS_DIR / "browser_results.json"
            results = []
            if results_file.exists():
                results = json.loads(results_file.read_text())
            results.append(result)
            results_file.write_text(json.dumps(results, indent=2))
            
            return result
            
    except Exception as e:
        logger.error(f"[{attempt}] Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await sms.reject_number(request_id)
        except:
            pass
        return None
    finally:
        # Don't stop/delete profile if successful — keep it running
        pass


async def main():
    sms = SMSMan()
    roxy = RoxyManager()
    
    balance = await sms.get_balance()
    logger.info(f"SMS-Man balance: ${balance:.2f}")
    
    await roxy.get_workspace()
    logger.info(f"Roxy workspace: {roxy.workspace_id}")
    
    # Try countries with available numbers
    available = [
        {"name": "Tanzania", "code": "tz", "sms_id": 313, "prefix": "+255"},
        {"name": "Vietnam", "code": "vn", "sms_id": 10, "prefix": "+84"},
        {"name": "Indonesia", "code": "id", "sms_id": 6, "prefix": "+62"},
        {"name": "Colombia", "code": "co", "sms_id": 114, "prefix": "+57"},
    ]
    
    result = None
    for i, country in enumerate(available):
        result = await register_via_browser(sms, roxy, country, attempt=i+1)
        if result:
            break
    
    if result:
        logger.info(f"✅ Registration successful: {result['full_phone']}")
    else:
        logger.warning("Registration failed — check screenshots in /tmp/tg_reg_*")


if __name__ == "__main__":
    asyncio.run(main())
