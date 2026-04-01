"""TData → Telethon .session cold converter.

Converts Telegram Desktop .tdata folders into Telethon SQLite .session files
using opentele. NO network connection is made during conversion — this is
critical to avoid premature session burning.

Device telemetry (device_model, system_version, app_version, etc.) is
extracted from the TData and persisted to device_profiles.json so that
subsequent Telethon connections present the same fingerprint.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

# ── opentele imports ────────────────────────────────────────────────────────
from opentele.td import TDesktop
from opentele.tl import TelegramClient as OpenteleClient
from opentele.api import UseCurrentSession


# ── Result types ────────────────────────────────────────────────────────────

@dataclass
class ConversionResult:
    """Outcome of a single TData → .session conversion."""
    success: bool
    tdata_path: str
    session_path: Optional[str] = None
    phone: Optional[str] = None
    error: Optional[str] = None
    device_profile: Optional[Dict] = None


@dataclass
class BatchResult:
    """Aggregate result of converting a directory of TData folders."""
    total: int = 0
    converted: int = 0
    failed: int = 0
    skipped: int = 0
    results: List[ConversionResult] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (
            f"Total: {self.total} | Converted: {self.converted} | "
            f"Failed: {self.failed} | Skipped: {self.skipped}"
        )


# ── Converter ───────────────────────────────────────────────────────────────

class TDataConverter:
    """Convert TData folders to Telethon .session files offline."""

    def __init__(
        self,
        output_dir: str = "sessions/telethon",
        profiles_path: str = "outreach/data/device_profiles.json",
    ) -> None:
        self.output_dir = Path(output_dir)
        self.profiles_path = Path(profiles_path)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_path.parent.mkdir(parents=True, exist_ok=True)

    # ── public API ──────────────────────────────────────────────────────────

    async def convert_single(self, tdata_path: str) -> ConversionResult:
        """Convert a single .tdata folder to a .session file.

        The conversion is performed entirely offline (cold conversion).
        Device telemetry is extracted and saved to the profiles JSON.
        """
        tdata_path = str(Path(tdata_path).resolve())
        logger.info("Converting TData: {}", tdata_path)

        try:
            tdesktop = self._load_tdesktop(tdata_path)
        except Exception as exc:
            msg = f"Failed to load TData: {exc}"
            logger.error("{} — {}", tdata_path, msg)
            return ConversionResult(success=False, tdata_path=tdata_path, error=msg)

        if not tdesktop.isLoaded():
            msg = "TDesktop reports data not loaded (corrupt or empty)"
            logger.error("{} — {}", tdata_path, msg)
            return ConversionResult(success=False, tdata_path=tdata_path, error=msg)

        accounts = tdesktop.accounts
        if not accounts:
            msg = "No accounts found in TData"
            logger.error("{} — {}", tdata_path, msg)
            return ConversionResult(success=False, tdata_path=tdata_path, error=msg)

        account = accounts[0]

        # Derive a filename from the phone number or the folder name
        phone = self._extract_phone(tdata_path, account)
        safe_phone = phone.replace("+", "").replace(" ", "")
        session_name = f"tg_{safe_phone}" if safe_phone.isdigit() else safe_phone
        session_path = self.output_dir / session_name

        # Skip if session already exists
        if session_path.with_suffix(".session").exists():
            logger.info("Session already exists, skipping: {}", session_path)
            return ConversionResult(
                success=True,
                tdata_path=tdata_path,
                session_path=str(session_path.with_suffix(".session")),
                phone=phone,
                error="skipped — session already exists",
            )

        # Cold-convert via opentele (no network)
        try:
            client = await account.ToTelethon(
                session=str(session_path),
                flag=UseCurrentSession,
            )
            # UseCurrentSession sets auth_key in memory but does NOT flush
            # to the SQLite file. Explicitly save without connecting.
            client.session.save()
            if client.is_connected():
                await client.disconnect()
        except Exception as exc:
            msg = f"opentele conversion failed: {exc}"
            logger.error("{} — {}", tdata_path, msg)
            return ConversionResult(success=False, tdata_path=tdata_path, error=msg)

        session_file = str(session_path) + ".session"
        if not Path(session_file).exists():
            msg = "Conversion produced no .session file"
            logger.error("{} — {}", tdata_path, msg)
            return ConversionResult(success=False, tdata_path=tdata_path, error=msg)

        # Validate the freshly written session
        if not self.validate_session(session_file):
            msg = "Post-conversion validation failed"
            logger.error("{} — {}", tdata_path, msg)
            return ConversionResult(success=False, tdata_path=tdata_path, error=msg)

        # Extract & persist device profile
        profile = self._extract_device_profile(account)
        profile_key = f"tg_{safe_phone}" if safe_phone.isdigit() else safe_phone
        self._save_device_profile(profile_key, profile)

        logger.success("Converted {} → {}", tdata_path, session_file)
        return ConversionResult(
            success=True,
            tdata_path=tdata_path,
            session_path=session_file,
            phone=phone,
            device_profile=profile,
        )

    async def convert_batch(self, tdata_dir: str) -> BatchResult:
        """Convert every TData folder found under *tdata_dir*.

        Each immediate subdirectory is treated as a potential TData source.
        Folders that contain a ``tdata`` sub-folder are unwrapped automatically.
        """
        tdata_dir = Path(tdata_dir).resolve()
        if not tdata_dir.is_dir():
            logger.error("Not a directory: {}", tdata_dir)
            return BatchResult()

        candidates = self._discover_tdata_folders(tdata_dir)
        result = BatchResult(total=len(candidates))
        logger.info("Found {} TData candidate(s) in {}", len(candidates), tdata_dir)

        for idx, candidate in enumerate(candidates, 1):
            logger.info("[{}/{}] Processing {}", idx, result.total, candidate)
            cr = await self.convert_single(str(candidate))
            result.results.append(cr)
            if cr.success and cr.error and "skipped" in cr.error:
                result.skipped += 1
            elif cr.success:
                result.converted += 1
            else:
                result.failed += 1

        logger.info("Batch complete — {}", result.summary)
        return result

    def validate_session(self, session_path: str) -> bool:
        """Validate a .session file's SQLite integrity offline.

        Checks:
        1. File exists and is a valid SQLite database
        2. Contains the ``sessions`` table used by Telethon
        3. The ``sessions`` table has a non-empty ``auth_key`` blob
        """
        session_path = Path(session_path)
        if not session_path.exists():
            logger.warning("Session file does not exist: {}", session_path)
            return False

        try:
            conn = sqlite3.connect(str(session_path))
            cursor = conn.cursor()

            # Check that the sessions table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
            )
            if cursor.fetchone() is None:
                logger.warning("No 'sessions' table in {}", session_path)
                conn.close()
                return False

            # Check for a non-empty auth_key
            cursor.execute("SELECT auth_key FROM sessions LIMIT 1")
            row = cursor.fetchone()
            conn.close()

            if row is None or row[0] is None or len(row[0]) == 0:
                logger.warning("Missing or empty auth_key in {}", session_path)
                return False

            return True
        except sqlite3.DatabaseError as exc:
            logger.warning("SQLite error reading {}: {}", session_path, exc)
            return False

    # ── internals ───────────────────────────────────────────────────────────

    def _load_tdesktop(self, tdata_path: str) -> TDesktop:
        """Load a TDesktop instance, handling nested ``tdata/`` subdirs."""
        p = Path(tdata_path)
        # Some vendors ship the tdata inside a wrapper folder
        inner = p / "tdata"
        if inner.is_dir():
            return TDesktop(str(inner))
        return TDesktop(str(p))

    @staticmethod
    def _extract_phone(tdata_path: str, account) -> str:
        """Best-effort phone number extraction.

        Tries the folder name first (many vendors name folders by phone),
        then falls back to whatever opentele exposes on the account object.
        """
        folder_name = Path(tdata_path).name
        # Strip common prefixes
        cleaned = folder_name.lstrip("+").replace(" ", "")
        if cleaned.isdigit() and len(cleaned) >= 7:
            return cleaned

        # Try parent folder if current is "tdata"
        if folder_name.lower() == "tdata":
            parent = Path(tdata_path).parent.name
            cleaned_parent = parent.lstrip("+").replace(" ", "")
            if cleaned_parent.isdigit() and len(cleaned_parent) >= 7:
                return cleaned_parent

        # Fallback: use authKey hash as identifier
        try:
            auth_key = account.authKey
            if auth_key:
                return f"unknown_{hash(bytes(auth_key.key)) % 10**8:08d}"
        except Exception:
            pass

        return f"unknown_{hash(tdata_path) % 10**8:08d}"

    @staticmethod
    def _extract_device_profile(account) -> Dict:
        """Pull device telemetry from the opentele account object."""
        profile: Dict = {
            "platform": "desktop",
            "api_id": getattr(account, "api_id", 2040),
            "api_hash": getattr(account, "api_hash", "b18441a1ff607e10a989891a5462e627"),
            "device_model": "Desktop",
            "system_version": "Windows 10",
            "app_version": "4.0.0 x64",
            "lang_code": "en",
            "system_lang_code": "en",
        }

        # opentele exposes these on the API object when available
        for attr, key in [
            ("device_model", "device_model"),
            ("system_version", "system_version"),
            ("app_version", "app_version"),
            ("lang_code", "lang_code"),
            ("system_lang_code", "system_lang_code"),
            ("api_id", "api_id"),
            ("api_hash", "api_hash"),
        ]:
            val = getattr(account, attr, None)
            if val is not None:
                profile[key] = val

        # Also try the appConfig if present
        try:
            api = account.api
            if api:
                profile["api_id"] = getattr(api, "api_id", profile["api_id"])
                profile["api_hash"] = getattr(api, "api_hash", profile["api_hash"])
                profile["device_model"] = getattr(api, "device_model", profile["device_model"])
                profile["system_version"] = getattr(api, "system_version", profile["system_version"])
                profile["app_version"] = getattr(api, "app_version", profile["app_version"])
                profile["lang_code"] = getattr(api, "lang_code", profile["lang_code"])
                profile["system_lang_code"] = getattr(api, "system_lang_code", profile["system_lang_code"])
        except Exception:
            pass

        return profile

    def _save_device_profile(self, key: str, profile: Dict) -> None:
        """Merge *profile* into the device_profiles.json file."""
        profiles: Dict = {}
        if self.profiles_path.exists():
            try:
                profiles = json.loads(self.profiles_path.read_text())
            except (json.JSONDecodeError, OSError):
                logger.warning("Could not read existing profiles, starting fresh")

        profiles[key] = profile
        self.profiles_path.write_text(json.dumps(profiles, indent=2) + "\n")
        logger.debug("Saved device profile for {}", key)

    @staticmethod
    def _discover_tdata_folders(root: Path) -> List[Path]:
        """Find all directories under *root* that look like TData sources.

        Recognition heuristics (any match):
        - Directory contains ``key_datas`` or ``key_data``
        - Directory contains a sub-folder named ``tdata`` with the above
        - Directory contains a hex-named subfolder (e.g. ``D877F783D5D3EF8C``)
        """
        candidates: List[Path] = []

        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue

            # Direct tdata folder
            if _looks_like_tdata(entry):
                candidates.append(entry)
                continue

            # Wrapped: entry/tdata/
            inner = entry / "tdata"
            if inner.is_dir() and _looks_like_tdata(inner):
                candidates.append(entry)
                continue

        return candidates


def _looks_like_tdata(path: Path) -> bool:
    """Return True if *path* contains typical TData artefacts."""
    if (path / "key_datas").exists() or (path / "key_data").exists():
        return True
    # Check for hex-named session directories (8+ hex chars)
    for child in path.iterdir():
        if child.is_dir() and len(child.name) >= 8:
            try:
                int(child.name.rstrip("s"), 16)
                return True
            except ValueError:
                continue
    return False
