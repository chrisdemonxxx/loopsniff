"""
Telegram Web Signup Automation
Drives web.telegram.org via Playwright over CDP (Roxy Browser).
"""
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser
from loguru import logger


class TelegramSignup:
    """Automates the Telegram Web signup / login flow."""

    URL = "https://web.telegram.org/a/"

    def __init__(self, cdp_endpoint: str):
        """
        Args:
            cdp_endpoint: WebSocket URL for Chrome DevTools Protocol
                          (e.g. ``ws://127.0.0.1:9222``).
        """
        self.cdp_endpoint = cdp_endpoint
        self._pw = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    # -- lifecycle ------------------------------------------------------------

    async def connect(self) -> Page:
        """Connect to the running Roxy browser via CDP and return a Page."""
        self._pw = await async_playwright().__aenter__()
        self._browser = await self._pw.chromium.connect_over_cdp(self.cdp_endpoint)

        # Reuse existing context / page if available
        ctx = self._browser.contexts[0] if self._browser.contexts else await self._browser.new_context()
        self._page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        logger.info("Connected to Roxy CDP: {}", self.cdp_endpoint)
        return self._page

    async def disconnect(self):
        if self._browser:
            # Don't close the browser – Roxy manages its lifecycle
            self._browser = None
        if self._pw:
            await self._pw.__aexit__(None, None, None)
            self._pw = None

    # -- navigation -----------------------------------------------------------

    async def open_telegram(self, timeout: int = 30_000):
        """Navigate to Telegram Web and wait for the auth screen."""
        page = self._page
        await page.goto(self.URL, wait_until="domcontentloaded", timeout=timeout)
        logger.info("Navigated to Telegram Web")

        # Wait for either the auth screen or an already-logged-in state
        try:
            await page.wait_for_selector(
                "#auth-qr-form, .phone-input, input[type='tel'], .chat-list",
                timeout=timeout,
            )
        except Exception:
            logger.warning("Auth screen selector not found, page may have changed")

    # -- phone entry ----------------------------------------------------------

    async def enter_phone(self, phone: str, country_code: str = "1"):
        """Enter phone number on the login screen.

        Handles clicking "Log in by phone" if QR code is shown first.
        """
        page = self._page

        # If QR code screen is showing, click "Log in by phone Number"
        phone_btn = page.locator("text=Log in by phone Number")
        if await phone_btn.count() > 0:
            await phone_btn.first.click()
            await page.wait_for_timeout(1500)

        # Look for the phone input
        phone_input = page.locator("input[type='tel']").first
        await phone_input.wait_for(state="visible", timeout=10_000)

        # Clear any pre-filled value and type the number
        await phone_input.click()
        await phone_input.fill("")
        await page.wait_for_timeout(300)

        # Type the full number (with country code if not already prefixed)
        full_number = phone if phone.startswith("+") else f"+{country_code}{phone}"
        await phone_input.fill(full_number)
        await page.wait_for_timeout(500)

        logger.info("Entered phone: {}", full_number)

        # Click "Next" / submit
        next_btn = page.locator("button:has-text('Next'), button[type='submit']").first
        await next_btn.click()
        await page.wait_for_timeout(3000)

    # -- code entry -----------------------------------------------------------

    async def enter_code(self, code: str):
        """Enter the SMS verification code."""
        page = self._page

        # Telegram Web shows individual digit inputs or a single code field
        code_input = page.locator("input#sign-in-code, input[inputmode='numeric']").first
        try:
            await code_input.wait_for(state="visible", timeout=15_000)
            await code_input.fill(code)
        except Exception:
            # Fallback: type digits one by one (some versions use separate inputs)
            logger.info("Trying digit-by-digit code entry")
            for digit in code:
                await page.keyboard.press(digit)
                await page.wait_for_timeout(200)

        logger.info("Entered verification code")
        await page.wait_for_timeout(3000)

    # -- 2FA password (optional) ----------------------------------------------

    async def enter_2fa_password(self, password: str):
        """Enter 2FA cloud password if prompted."""
        page = self._page
        pwd_input = page.locator("input[type='password']").first
        try:
            await pwd_input.wait_for(state="visible", timeout=5_000)
            await pwd_input.fill(password)
            submit = page.locator("button:has-text('Submit'), button[type='submit']").first
            await submit.click()
            await page.wait_for_timeout(3000)
            logger.info("Entered 2FA password")
        except Exception:
            logger.debug("No 2FA prompt detected")

    # -- new account profile setup --------------------------------------------

    async def complete_profile(self, first_name: str, last_name: str = ""):
        """Fill profile info for new accounts (if Telegram asks)."""
        page = self._page

        name_input = page.locator("input#registration-first-name, input[name='first-name']").first
        try:
            await name_input.wait_for(state="visible", timeout=5_000)
            await name_input.fill(first_name)

            if last_name:
                last_input = page.locator("input#registration-last-name, input[name='last-name']").first
                await last_input.fill(last_name)

            submit = page.locator("button:has-text('Start Messaging'), button[type='submit']").first
            await submit.click()
            await page.wait_for_timeout(3000)
            logger.info("Profile completed: {} {}", first_name, last_name)
        except Exception:
            logger.debug("No profile setup screen (existing account)")

    # -- verification ---------------------------------------------------------

    async def is_logged_in(self, timeout: int = 10_000) -> bool:
        """Check whether we reached the main chat screen."""
        page = self._page
        try:
            await page.wait_for_selector(
                ".chat-list, #LeftColumn, .Transition__slide--active",
                timeout=timeout,
            )
            logger.info("✓ Logged in successfully")
            return True
        except Exception:
            logger.warning("Login verification timed out")
            return False

    # -- high-level flow ------------------------------------------------------

    async def signup_flow(
        self,
        phone: str,
        code: str,
        first_name: str = "User",
        last_name: str = "",
        password_2fa: str = "",
        country_code: str = "1",
    ) -> bool:
        """Run the complete signup / login flow.

        Returns True if login succeeds.
        """
        await self.open_telegram()
        await self.enter_phone(phone, country_code)
        await self.enter_code(code)

        if password_2fa:
            await self.enter_2fa_password(password_2fa)

        await self.complete_profile(first_name, last_name)
        return await self.is_logged_in()

    async def wait_for_code_prompt(self, timeout: int = 30_000) -> bool:
        """After entering the phone, wait until Telegram shows the code input.

        Useful in interactive mode: caller enters phone, waits for SMS,
        then calls ``enter_code``.
        """
        page = self._page
        try:
            await page.wait_for_selector(
                "input#sign-in-code, input[inputmode='numeric'], .code-input",
                timeout=timeout,
            )
            return True
        except Exception:
            return False
