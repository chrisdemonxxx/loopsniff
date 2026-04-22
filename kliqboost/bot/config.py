import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv(override=False)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@Kliqboost_Admin")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@kliqboost_bot")

# Kliqboost API
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8099")
API_TOKEN = os.getenv("API_TOKEN", "")

# Ollama Cloud LLM — canonical host, matches userbot + api defaults.
OLLAMA_CLOUD_URL = os.getenv("OLLAMA_CLOUD_URL", "https://ollama.com/v1/chat/completions")
OLLAMA_CLOUD_API_KEY = os.getenv("OLLAMA_CLOUD_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2:1t")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")
if ADMIN_CHAT_ID <= 0:
    raise RuntimeError("ADMIN_CHAT_ID is required")

# Guard against the silent "bot never reports" failure mode: in a Render
# worker environment, API_BASE_URL should be a public kliqboost-api URL.
# If it still points at localhost, heartbeats vanish and the admin dashboard
# shows "unknown" forever. Fail loudly instead.
_render_signal = any(
    os.getenv(k) for k in ("RENDER", "RENDER_SERVICE_ID", "RENDER_SERVICE_NAME")
)
if _render_signal and ("localhost" in API_BASE_URL or "127.0.0.1" in API_BASE_URL):
    logging.basicConfig(level=logging.ERROR, stream=sys.stderr)
    logging.error(
        "API_BASE_URL=%s looks like a local dev default, but we appear to be "
        "running on Render. Set API_BASE_URL to https://kliqboost-api.onrender.com "
        "(or your deployed API URL) so heartbeats reach the admin dashboard.",
        API_BASE_URL,
    )
    raise RuntimeError(
        "API_BASE_URL must be a public URL in production (got " + API_BASE_URL + ")"
    )
