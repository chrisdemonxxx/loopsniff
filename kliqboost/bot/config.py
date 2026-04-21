import os
from dotenv import load_dotenv

load_dotenv(override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@Kliqboost_Admin")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@kliqboost_bot")

# Kliqboost API
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8099")
API_TOKEN = os.getenv("API_TOKEN", "")

# Ollama Cloud LLM
OLLAMA_CLOUD_URL = os.getenv("OLLAMA_CLOUD_URL", "https://api.ollamacloud.com/v1")
OLLAMA_CLOUD_API_KEY = os.getenv("OLLAMA_CLOUD_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
