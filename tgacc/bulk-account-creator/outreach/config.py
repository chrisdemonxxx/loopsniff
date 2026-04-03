"""Configuration loader — reads ../.env and exposes all constants."""

import json
import os
import random
import string
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the parent (bulk-account-creator) directory
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

# ── Telegram API ────────────────────────────────────────────────────────────
API_ID: int = int(os.getenv("TELEGRAM_API_ID", "2040"))
API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
DB_PATH = DATA_DIR / "outreach.db"
PROFILE_MAP_PATH = DATA_DIR / "profile_map.json"
DEVICE_PROFILES_PATH = DATA_DIR / "device_profiles.json"

# Ensure directories exist at import time
DATA_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# ── Per-account proxy & device profiles ─────────────────────────────────────
_profile_map: dict = {}
_device_profiles: dict = {}

if PROFILE_MAP_PATH.exists():
    with open(PROFILE_MAP_PATH) as f:
        _profile_map = json.load(f)

if DEVICE_PROFILES_PATH.exists():
    with open(DEVICE_PROFILES_PATH) as f:
        _device_profiles = json.load(f)

# ── Proxy (residential — Proxy-Seller) ──────────────────────────────────────
PROXY_HOST = "res.proxy-seller.com"
PROXY_PORT = 10000
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "avTItX8z32si7P6p")

USE_PROXY: bool = True  # Always use per-account proxies

# ── Mobile Proxy Settings ──────────────────────────────────────────────────
MOBILE_PROXY_HOST: str = os.getenv("MOBILE_PROXY_HOST", "")
MOBILE_PROXY_PORT: int = int(os.getenv("MOBILE_PROXY_PORT", "0"))
MOBILE_PROXY_USER: str = os.getenv("MOBILE_PROXY_USER", "")
MOBILE_PROXY_PASS: str = os.getenv("MOBILE_PROXY_PASS", "")
MOBILE_PROXY_ROTATION_URL: str = os.getenv("MOBILE_PROXY_ROTATION_URL", "")
MOBILE_PROXY_COUNTRY: str = os.getenv("MOBILE_PROXY_COUNTRY", "US")


def _session_key(phone: str) -> str | None:
    """Find the profile_map key for a phone number."""
    clean = phone.replace("+", "").replace(" ", "")
    for key in _profile_map:
        if clean in key or key.endswith(clean):
            return key
    return None


def build_proxy(phone: str | None = None) -> dict | None:
    """Return a proxy dict for a specific phone's assigned sticky session.

    Each account uses its own persistent residential IP from profile_map.json.
    Falls back to a random session if phone not in profile map.
    """
    if phone:
        key = _session_key(phone)
        if key and key in _profile_map:
            proxy_user = _profile_map[key].get("proxy_user", "")
            if proxy_user:
                return {
                    "proxy_type": "http",
                    "addr": PROXY_HOST,
                    "port": PROXY_PORT,
                    "username": proxy_user,
                    "password": PROXY_PASSWORD,
                }

    # Fallback: random session
    session_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return {
        "proxy_type": "http",
        "addr": PROXY_HOST,
        "port": PROXY_PORT,
        "username": f"api004e59f1d44c9a00_c_US_s_{session_id}_ttl_1440m",
        "password": PROXY_PASSWORD,
    }


def get_device_profile(phone: str) -> dict | None:
    """Return device fingerprint for a specific phone from device_profiles.json."""
    clean = phone.replace("+", "").replace(" ", "")
    for key, profile in _device_profiles.items():
        if clean in key or key.endswith(clean):
            return profile
    return None


# ── Safety limits ───────────────────────────────────────────────────────────
FRESH_ACCOUNT_DM_LIMIT = 5       # first week
WARMED_ACCOUNT_DM_LIMIT = 15     # after 14 days
ULTRA_SAFE_DM_LIMIT = 10         # default we actually use
MIN_DELAY_BETWEEN_DMS = 25       # seconds
MAX_DELAY_BETWEEN_DMS = 180      # seconds
WARMING_DAYS = 14
MAX_ACCOUNTS_ACTIVE = 120

# ── Admin notifications ────────────────────────────────────────────────────
ADMIN_BOT_TOKEN = os.getenv(
    "ADMIN_BOT_TOKEN", "8707230750:AAHkEFpQIxk1H9JsHu8IQ6jagWp8Qlh8-G4"
)
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "8365840792")

# ── Misc ────────────────────────────────────────────────────────────────────
SMS_MAN_API_KEY = os.getenv("SMS_MAN_API_KEY", "")
PROXY_SELLER_KEY = os.getenv("PROXY_SELLER_KEY", "")
