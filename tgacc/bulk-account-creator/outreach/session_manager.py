"""Telethon session creation, storage and rotation."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

from telethon import TelegramClient
from telethon.errors import (
    AuthKeyUnregisteredError,
    UserDeactivatedBanError,
    PhoneNumberBannedError,
)

from . import config
from . import db
from .models import Account

log = logging.getLogger(__name__)


class SessionManager:
    """Manage Telethon .session files and provide connected clients."""

    def __init__(self) -> None:
        self.sessions_dir = config.SESSIONS_DIR
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    # ── session file helpers ────────────────────────────────────────────────

    def _session_path(self, phone: str) -> str:
        """Return path (without .session extension) for Telethon."""
        safe = phone.replace("+", "").replace(" ", "")
        # Check for session files with tg_ prefix or exact name
        tg_path = self.sessions_dir / f"tg_{safe}"
        if (tg_path.with_suffix(".session")).exists():
            return str(tg_path)
        plain_path = self.sessions_dir / safe
        if (plain_path.with_suffix(".session")).exists():
            return str(plain_path)
        # Check if phone itself is a name like "dorothy"
        name_path = self.sessions_dir / safe
        if (name_path.with_suffix(".session")).exists():
            return str(name_path)
        # Default: try tg_ prefix first, then plain
        return str(tg_path) if not safe.isdigit() else str(tg_path)

    # ── public API ──────────────────────────────────────────────────────────

    async def create_session(
        self, phone: str, proxy_session_id: str | None = None
    ) -> str:
        """Create a new Telethon session file for *phone*.

        The session is created through the residential proxy gateway.
        Returns the path to the .session file.
        """
        proxy = config.build_proxy(proxy_session_id)
        session_path = self._session_path(phone)

        client = TelegramClient(
            session_path,
            config.API_ID,
            config.API_HASH,
            proxy=proxy,
        )
        try:
            await client.connect()
            if not await client.is_user_authorized():
                log.info("Session for %s requires auth — sending code request", phone)
                await client.send_code_request(phone)
                log.info(
                    "Code sent to %s.  Complete auth manually or via "
                    "`sessions --auth --phone %s`.",
                    phone,
                    phone,
                )
        finally:
            await client.disconnect()

        session_file = session_path + ".session"
        log.info("Session file created: %s", session_file)

        from datetime import datetime

        acct = Account(
            phone=phone,
            session_file=session_file,
            status="fresh",
            created_at=datetime.utcnow(),
        )
        await db.add_account(acct)
        return session_file

    async def get_client(self, phone: str) -> TelegramClient:
        """Return a **connected** TelegramClient for *phone*.

        Uses per-account proxy and device fingerprint from profile maps.
        Caller is responsible for disconnecting when done.
        """
        proxy = config.build_proxy(phone)
        device = config.get_device_profile(phone)
        session_path = self._session_path(phone)

        client_kwargs = dict(
            session=session_path,
            api_id=device.get("api_id", config.API_ID) if device else config.API_ID,
            api_hash=device.get("api_hash", config.API_HASH) if device else config.API_HASH,
            proxy=proxy,
        )
        if device:
            client_kwargs["device_model"] = device.get("device_model", "Unknown")
            client_kwargs["system_version"] = device.get("system_version", "1.0")
            client_kwargs["app_version"] = device.get("app_version", "1.0")
            client_kwargs["lang_code"] = device.get("lang_code", "en")
            client_kwargs["system_lang_code"] = device.get("system_lang_code", "en")

        client = TelegramClient(**client_kwargs)
        await client.connect()
        return client

    async def validate_session(self, phone: str) -> bool:
        """Check whether the session file for *phone* is still valid."""
        try:
            client = await self.get_client(phone)
            try:
                authorized = await client.is_user_authorized()
                if authorized:
                    me = await client.get_me()
                    log.info("Session OK for %s (user_id=%s)", phone, me.id)
                    return True
                log.warning("Session for %s is not authorised", phone)
                return False
            finally:
                await client.disconnect()
        except (AuthKeyUnregisteredError, UserDeactivatedBanError,
                PhoneNumberBannedError) as exc:
            log.error("Session for %s is invalid: %s", phone, exc)
            await db.update_account(phone, status="banned")
            return False
        except Exception as exc:
            log.error("Session validation failed for %s: %s", phone, exc)
            return False

    async def rotate_sessions(self) -> List[str]:
        """Return phones of accounts available for outreach, rotated fairly."""
        accounts = await db.get_accounts()
        available = [
            a.phone
            for a in accounts
            if a.status in ("ready", "active")
            and a.dms_sent_today < config.ULTRA_SAFE_DM_LIMIT
        ]
        # Sort by last_used ascending so least-recently-used goes first
        accounts_map = {a.phone: a for a in accounts}
        available.sort(
            key=lambda p: (accounts_map[p].last_used or "0000")
        )
        return available

    async def list_sessions(self) -> List[dict]:
        """Return metadata for every known session."""
        accounts = await db.get_accounts()
        results = []
        for a in accounts:
            exists = Path(a.session_file).exists() if a.session_file else False
            results.append({
                "phone": a.phone,
                "status": a.status,
                "session_exists": exists,
                "dms_today": a.dms_sent_today,
                "total_dms": a.total_dms_sent,
                "spam_reports": a.spam_reports,
            })
        return results

    async def export_sessions_from_browser(self) -> None:
        """Stub: export auth data from Roxy Browser web.telegram.org sessions.

        The workflow is:
        1. Accounts are created via web.telegram.org inside Roxy Browser
           (anti-detect browser with unique fingerprints per profile).
        2. After signup the browser stores TDLib auth keys in IndexedDB.
        3. This method should:
           a. Read the IndexedDB data from the Roxy profile directory.
           b. Extract the ``auth_key`` blob.
           c. Convert it into a Telethon SQLite .session file by writing
              the key into the ``sessions`` table expected by Telethon.
        4. Save the .session file to SESSIONS_DIR.

        This is non-trivial and depends on the exact Roxy Browser storage
        layout. Implementation is deferred — for now accounts should be
        authenticated directly via ``create_session`` + OTP flow.
        """
        log.warning(
            "export_sessions_from_browser() is a stub. "
            "Authenticate accounts via create_session() + OTP for now."
        )
