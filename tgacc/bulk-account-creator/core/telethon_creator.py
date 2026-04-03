"""
Telethon-based Telegram Account Creator.
Uses the raw Telegram API (via Telethon) for reliable account creation.

Key challenge: SMS-Man numbers are mostly recycled (already have TG accounts).
When a number already has a TG account, Telegram sends the verification code to
the existing Telegram session (SentCodeTypeApp), NOT via SMS. This script handles
this by rapidly screening numbers and only processing ones that get SMS delivery.
"""
import asyncio
import json
import os
import random
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from loguru import logger
from telethon import TelegramClient
from telethon.errors import (
    PhoneNumberBannedError,
    PhoneNumberFloodError,
    PhoneNumberInvalidError,
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
    PhoneNumberOccupiedError,
    AuthRestartError,
)
from telethon.tl.functions.auth import (
    SendCodeRequest,
    SignUpRequest,
    ResendCodeRequest,
)
from telethon.tl.types import CodeSettings
from telethon.sessions import StringSession

from core.sms_client import SMSManClient, SMSManError

FIRST_NAMES = [
    "James", "Robert", "John", "Michael", "David", "William", "Richard",
    "Joseph", "Thomas", "Christopher", "Mary", "Patricia", "Jennifer",
    "Linda", "Barbara", "Elizabeth", "Susan", "Jessica", "Sarah", "Karen",
    "Daniel", "Matthew", "Anthony", "Mark", "Steven", "Andrew",
    "Paul", "Joshua", "Kenneth", "Ashley", "Emily", "Megan", "Hannah",
    "Samantha", "Rachel", "Lauren", "Nicole", "Stephanie",
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley",
]


def random_name() -> str:
    return random.choice(FIRST_NAMES)


class TelethonAccountCreator:
    """Creates Telegram accounts using Telethon (raw API).

    Handles the recycled number problem by checking the code delivery type
    before waiting for SMS. Numbers that return SentCodeTypeApp (recycled)
    are immediately rejected to save time and money.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        sms_client: SMSManClient,
        sessions_dir: str = "sessions",
        proxy: Optional[Dict] = None,
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.sms = sms_client
        self.sessions_dir = sessions_dir
        self.proxy = proxy
        os.makedirs(sessions_dir, exist_ok=True)

    def _get_proxy_tuple(self) -> Optional[tuple]:
        """Convert proxy dict to Telethon proxy tuple."""
        if not self.proxy:
            return None
        import socks
        proxy_type = {
            "socks5": socks.SOCKS5,
            "socks4": socks.SOCKS4,
            "http": socks.HTTP,
        }.get(self.proxy.get("type", "socks5"), socks.SOCKS5)
        return (
            proxy_type,
            self.proxy["host"],
            int(self.proxy["port"]),
            True,
            self.proxy.get("username"),
            self.proxy.get("password"),
        )

    async def _probe_number(
        self, phone: str, session_name: str
    ) -> tuple[Optional[TelegramClient], str, Optional[str]]:
        """Send code request and check delivery type.

        Returns (client, code_type, phone_code_hash).
        If code_type is not SMS-receivable, client is disconnected and None returned.
        """
        proxy = self._get_proxy_tuple()
        client = TelegramClient(
            session_name,
            self.api_id,
            self.api_hash,
            proxy=proxy,
            device_model="Samsung Galaxy S24",
            system_version="Android 14",
            app_version="11.7.4",
            lang_code="en",
            system_lang_code="en-US",
        )
        await client.connect()

        settings = CodeSettings(
            allow_flashcall=False,
            current_number=False,
            allow_app_hash=False,
            allow_missed_call=False,
            allow_firebase=False,
        )

        sent = await client(SendCodeRequest(
            phone_number=phone,
            api_id=self.api_id,
            api_hash=self.api_hash,
            settings=settings,
        ))

        code_type = type(sent.type).__name__
        next_type = type(sent.next_type).__name__ if sent.next_type else None
        hash_ = sent.phone_code_hash

        logger.info("  Code delivery: type={}, next={}, timeout={}", code_type, next_type, sent.timeout)

        # If App type with SMS fallback, try resending
        if code_type == "SentCodeTypeApp" and next_type and "Sms" in next_type:
            logger.info("  Recycled number with SMS fallback, trying resend...")
            try:
                resent = await client(ResendCodeRequest(phone, hash_))
                code_type = type(resent.type).__name__
                hash_ = resent.phone_code_hash
                logger.info("  Resend type: {}", code_type)

                # Try one more resend if still not SMS
                if "Sms" not in code_type:
                    next2 = type(resent.next_type).__name__ if resent.next_type else None
                    if next2 and "Sms" in next2 and resent.timeout:
                        logger.info("  Waiting {}s for next resend...", resent.timeout)
                        await asyncio.sleep(min(resent.timeout, 120))
                        try:
                            resent2 = await client(ResendCodeRequest(phone, hash_))
                            code_type = type(resent2.type).__name__
                            hash_ = resent2.phone_code_hash
                            logger.info("  Resend2 type: {}", code_type)
                        except Exception:
                            pass
            except Exception as e:
                logger.warning("  Resend failed: {}", e)

        return client, code_type, hash_

    async def create_account(
        self,
        country: str = "us",
        country_id: str = "5",
        first_name: Optional[str] = None,
        sms_timeout: int = 300,
        max_probes: int = 10,
    ) -> Dict[str, Any]:
        """Create a single Telegram account.

        Screens numbers for SMS-deliverable code type before waiting.
        Will try up to max_probes numbers to find one that gets SMS delivery.

        Returns result dict with status, phone, session_file, etc.
        """
        result: Dict[str, Any] = {
            "status": "failed",
            "country": country,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "probes_tried": 0,
        }
        sms_request_id = None
        client = None
        phone = None

        try:
            # Probe numbers until we find one with SMS delivery
            for probe_num in range(1, max_probes + 1):
                result["probes_tried"] = probe_num

                # Get phone number
                logger.info("[probe {}/{}] Requesting number (country={})...",
                            probe_num, max_probes, country)
                try:
                    num_data = await self.sms.get_number(country_id, application_id="3")
                except SMSManError as e:
                    logger.warning("[probe {}] SMS-Man error: {}", probe_num, e)
                    await asyncio.sleep(3)
                    continue

                phone = num_data["number"]
                sms_request_id = num_data["request_id"]
                if not phone.startswith("+"):
                    phone = f"+{phone}"

                logger.info("[probe {}] Got: {} (req={})", probe_num, phone, sms_request_id)
                result["phone"] = phone

                session_file = os.path.join(self.sessions_dir, phone.replace("+", ""))

                try:
                    client, code_type, hash_ = await self._probe_number(phone, session_file)
                except PhoneNumberBannedError:
                    logger.warning("[probe {}] Number BANNED, trying next...", probe_num)
                    await self._reject_number(sms_request_id)
                    sms_request_id = None
                    client = None
                    await asyncio.sleep(2)
                    continue

                # Check if SMS-receivable
                if "Sms" in code_type:
                    logger.info("[probe {}] ✓ SMS delivery confirmed!", probe_num)
                    break
                elif "Call" in code_type:
                    logger.info("[probe {}] Call delivery (SMS-Man may not receive). Trying anyway...", probe_num)
                    break  # Worth trying - some SMS services capture call codes
                else:
                    logger.info("[probe {}] {} delivery - not SMS-receivable. Rejecting...",
                                probe_num, code_type)
                    if client:
                        try:
                            await client.disconnect()
                        except Exception:
                            pass
                        client = None
                    # Remove failed session file
                    for ext in ("", ".session"):
                        try:
                            os.remove(session_file + ext)
                        except FileNotFoundError:
                            pass
                    await self._reject_number(sms_request_id)
                    sms_request_id = None
                    await asyncio.sleep(2)
                    continue
            else:
                result["error"] = f"No SMS-deliverable number found in {max_probes} probes"
                return result

            if not client or not sms_request_id:
                result["error"] = "No valid number/client available"
                return result

            result["code_type"] = code_type

            # Wait for SMS code
            logger.info("Waiting for code via SMS-Man (timeout={}s)...", sms_timeout)
            code = await self.sms.wait_for_code(sms_request_id, timeout=sms_timeout, poll_interval=5)
            logger.info("✓ Code received: {}", code)

            # Complete authentication
            name = first_name or random_name()
            try:
                await client.sign_in(phone, code, phone_code_hash=hash_)
                logger.info("✓ Signed in to existing account")
                result["account_type"] = "existing"
            except PhoneNumberOccupiedError:
                logger.info("✓ Signed in (number occupied)")
                result["account_type"] = "existing"
            except SessionPasswordNeededError:
                logger.warning("Account has 2FA password, cannot proceed")
                result["error"] = "2fa_required"
                result["status"] = "2fa_blocked"
                return result
            except Exception as sign_in_err:
                err_msg = str(sign_in_err).lower()
                if "phone_number_unoccupied" in err_msg or "sign up" in err_msg:
                    logger.info("New number - signing up as '{}'...", name)
                    await client(SignUpRequest(
                        phone_number=phone,
                        phone_code_hash=hash_,
                        first_name=name,
                        last_name="",
                    ))
                    logger.info("✓ Account created!")
                    result["account_type"] = "new"
                else:
                    logger.error("Sign-in failed: {}", sign_in_err)
                    result["error"] = str(sign_in_err)
                    return result

            # Verify and save
            me = await client.get_me()
            if me:
                result["user_id"] = me.id
                result["username"] = me.username
                result["first_name"] = me.first_name
                result["session_file"] = session_file + ".session"
                result["status"] = "success"

                string_session = StringSession.save(client.session)
                result["string_session"] = string_session

                logger.info("✓✓✓ Account ready: id={} phone={} name={}",
                            me.id, phone, me.first_name)

                try:
                    await self.sms.set_status(sms_request_id, "close")
                    sms_request_id = None
                except Exception:
                    pass
            else:
                result["error"] = "Could not verify account (get_me returned None)"

        except PhoneNumberBannedError:
            logger.error("Phone number {} is banned", phone)
            result["error"] = "phone_banned"
        except PhoneNumberFloodError:
            logger.error("Too many attempts for phone {}", phone)
            result["error"] = "phone_flood"
        except PhoneNumberInvalidError:
            logger.error("Invalid phone number: {}", phone)
            result["error"] = "phone_invalid"
        except FloodWaitError as e:
            logger.error("Flood wait: {} seconds", e.seconds)
            result["error"] = f"flood_wait_{e.seconds}s"
            result["retry_after"] = e.seconds
        except PhoneCodeExpiredError:
            logger.error("Verification code expired")
            result["error"] = "code_expired"
        except PhoneCodeInvalidError:
            logger.error("Invalid verification code")
            result["error"] = "code_invalid"
        except AuthRestartError:
            logger.error("Auth restart required - retryable")
            result["error"] = "auth_restart"
        except TimeoutError:
            logger.error("SMS code not received within timeout")
            result["error"] = "sms_timeout"
        except SMSManError as e:
            logger.error("SMS-Man error: {}", e)
            result["error"] = f"sms_error: {e}"
        except Exception as e:
            logger.error("Unexpected error: {} ({})", e, type(e).__name__)
            result["error"] = f"{type(e).__name__}: {e}"
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            if result["status"] != "success" and sms_request_id:
                await self._reject_number(sms_request_id)

        return result

    async def _reject_number(self, request_id) -> None:
        """Reject/refund an SMS-Man number."""
        try:
            await self.sms.set_status(request_id, "reject")
            logger.debug("SMS number rejected (refunded)")
        except Exception:
            pass

    async def create_batch(
        self,
        count: int = 5,
        country: str = "us",
        country_id: str = "5",
        delay_between: int = 30,
        sms_timeout: int = 300,
        max_probes_per_account: int = 10,
    ) -> list[Dict[str, Any]]:
        """Create multiple accounts sequentially with delays.

        Args:
            count: Number of accounts to create
            country: Country code
            country_id: SMS-Man country ID
            delay_between: Seconds between account creations
            sms_timeout: Timeout for SMS code reception
            max_probes_per_account: Max numbers to try per account
        """
        results = []
        success_count = 0
        fail_count = 0

        for i in range(count):
            logger.info("━━━ Account {}/{} ━━━", i + 1, count)

            result = await self.create_account(
                country=country,
                country_id=country_id,
                sms_timeout=sms_timeout,
                max_probes=max_probes_per_account,
            )
            results.append(result)

            if result["status"] == "success":
                success_count += 1
                logger.info("✓ Account {}/{} created successfully", i + 1, count)
            else:
                fail_count += 1
                error = result.get("error", "unknown")
                logger.warning("✗ Account {}/{} failed: {}", i + 1, count, error)

                if "flood_wait" in str(error):
                    wait_time = result.get("retry_after", 60)
                    logger.info("Flood wait: sleeping {} seconds...", wait_time)
                    await asyncio.sleep(wait_time)

            if i < count - 1:
                jitter = random.randint(5, 15)
                wait = delay_between + jitter
                logger.info("Waiting {}s before next account...", wait)
                await asyncio.sleep(wait)

        logger.info("━━━ Batch complete: {}/{} succeeded, {} failed ━━━",
                     success_count, count, fail_count)
        return results
