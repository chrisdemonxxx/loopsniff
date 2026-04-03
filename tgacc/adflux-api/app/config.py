from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres@localhost:5432/adflux"
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    NOWPAY_API_KEY: str = ""
    NOWPAY_IPN_SECRET: str = ""

    OLLAMA_CLOUD_KEY: str = ""
    OLLAMA_CLOUD_URL: str = "https://api.ollamacloud.com/v1"
    OLLAMA_MODEL: str = "llama3.1:8b"

    TG_BOT_TOKEN: str = "8707230750:AAHkEFpQIxk1H9JsHu8IQ6jagWp8Qlh8-G4"
    TG_ALERT_CHAT_ID: str = "8365840792"

    NTFY_TOPIC: str = "adflux-alerts"
    NTFY_URL: str = "https://ntfy.sh"

    TWILIO_SID: str = ""
    TWILIO_TOKEN: str = ""
    TWILIO_FROM: str = ""
    ALERT_PHONE: str = ""

    SENDGRID_API_KEY: str = ""
    ALERT_EMAIL_FROM: str = "alerts@adflux.store"
    ALERT_EMAIL_TO: str = "admin@adflux.store"

    WHATSAPP_FROM: str = ""
    WHATSAPP_TO: str = ""

    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    BANK_NAME: str = "AdFlux Holdings Ltd"
    BANK_ACCOUNT_NUMBER: str = ""
    BANK_SWIFT_BIC: str = ""

    OUTREACH_DB_PATH: str = "/home/cjs/tgacc/bulk-account-creator/outreach/data/outreach.db"

    FACEBOOK_APP_ID: str = ""
    FACEBOOK_APP_SECRET: str = ""
    FACEBOOK_REDIRECT_URI: str = "http://localhost:8099/facebook/callback"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
