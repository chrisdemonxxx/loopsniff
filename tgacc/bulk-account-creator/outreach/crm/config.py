"""CRM sync configuration — credentials and settings."""

import os

GOOGLE_CREDS_PATH = os.environ.get(
    "GOOGLE_CREDS_PATH",
    "",
)

NOTION_TOKEN = os.environ.get(
    "NOTION_TOKEN",
    "",
)

NOTION_DB_ID = os.environ.get(
    "NOTION_DB_ID",
    "",
)

SPREADSHEET_NAME = "AdFlux CRM - Leads"

# Pre-existing spreadsheet ID (bypasses Drive API for creation).
# Set via env var if the Drive API is not enabled on the GCP project.
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")

SERVICE_ACCOUNT_EMAIL = (
    "id-adflux-crm@robotic-casing-478106-p7.iam.gserviceaccount.com"
)

OUTREACH_DB_PATH = os.environ.get(
    "OUTREACH_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "outreach.db"),
)

SHEET_HEADERS = [
    "Username",
    "Source",
    "Status",
    "BANT Score",
    "Budget",
    "Platform",
    "Niche",
    "Timeline",
    "First Contact",
    "Last Contact",
    "Messages Sent",
    "Replies",
    "Notes",
]
