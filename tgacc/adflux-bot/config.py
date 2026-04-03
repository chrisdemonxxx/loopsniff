import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@Adflux_Admin")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@addfluxmedia_bot")

# AdFlux API
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8099")
API_TOKEN = os.getenv("API_TOKEN", "")
