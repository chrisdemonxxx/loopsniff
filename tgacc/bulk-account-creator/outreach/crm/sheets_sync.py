"""Google Sheets sync for outreach leads using gspread + google-auth."""

from __future__ import annotations

import json
import requests as _requests

import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request as AuthRequest

from .config import GOOGLE_CREDS_PATH, SPREADSHEET_NAME, SPREADSHEET_ID, SHEET_HEADERS, SERVICE_ACCOUNT_EMAIL


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_ENABLE_URLS = (
    "https://console.developers.google.com/apis/api/drive.googleapis.com/overview",
    "https://console.developers.google.com/apis/api/sheets.googleapis.com/overview",
)


class SheetsSync:
    """Sync outreach leads to a Google Sheets spreadsheet."""

    def __init__(self) -> None:
        self._creds = Credentials.from_service_account_file(
            GOOGLE_CREDS_PATH, scopes=SCOPES
        )
        self.gc = gspread.authorize(self._creds)
        self._sheet: gspread.Spreadsheet | None = None
        self._ws: gspread.Worksheet | None = None

    # ------------------------------------------------------------------
    # Sheet lifecycle
    # ------------------------------------------------------------------

    def _create_via_sheets_api(self) -> gspread.Spreadsheet:
        """Create a spreadsheet via Sheets API v4 (bypasses Drive API)."""
        self._creds.refresh(AuthRequest())
        headers = {
            "Authorization": f"Bearer {self._creds.token}",
            "Content-Type": "application/json",
        }
        body = {
            "properties": {"title": SPREADSHEET_NAME},
            "sheets": [
                {
                    "properties": {"title": "Sheet1"},
                    "data": [{"startRow": 0, "startColumn": 0,
                              "rowData": [{"values": [
                                  {"userEnteredValue": {"stringValue": h}}
                                  for h in SHEET_HEADERS
                              ]}]}],
                }
            ],
        }
        resp = _requests.post(
            "https://sheets.googleapis.com/v4/spreadsheets",
            headers=headers,
            json=body,
        )
        if resp.status_code == 403:
            raise _api_not_enabled_error(resp.text)
        resp.raise_for_status()
        sid = resp.json()["spreadsheetId"]
        return self.gc.open_by_key(sid)

    def ensure_sheet(self) -> gspread.Worksheet:
        """Create or open the CRM spreadsheet and return the first worksheet."""
        if SPREADSHEET_ID:
            # Pre-existing spreadsheet — only needs Sheets API (not Drive)
            self._sheet = self.gc.open_by_key(SPREADSHEET_ID)
        else:
            try:
                self._sheet = self.gc.open(SPREADSHEET_NAME)
            except gspread.exceptions.APIError as exc:
                if "has not been used in project" in str(exc) or "PERMISSION_DENIED" in str(exc):
                    self._sheet = self._create_via_sheets_api()
                else:
                    raise
            except gspread.SpreadsheetNotFound:
                try:
                    self._sheet = self.gc.create(SPREADSHEET_NAME)
                except gspread.exceptions.APIError:
                    self._sheet = self._create_via_sheets_api()

        self._ws = self._sheet.sheet1

        existing = self._ws.row_values(1)
        if existing != SHEET_HEADERS:
            self._ws.update("A1", [SHEET_HEADERS])

        return self._ws

    # ------------------------------------------------------------------
    # Lead sync
    # ------------------------------------------------------------------

    def _lead_to_row(self, lead: dict) -> list:
        """Convert a lead dict to a spreadsheet row matching SHEET_HEADERS."""
        return [
            str(lead.get("username", "")),
            str(lead.get("source", "")),
            str(lead.get("status", "")),
            lead.get("bant_score", 0) or 0,
            str(lead.get("budget", lead.get("budget_tier", "")) or ""),
            str(lead.get("platform", "") or ""),
            str(lead.get("niche", "") or ""),
            str(lead.get("timeline", "") or ""),
            str(lead.get("first_contact", lead.get("contacted_at", "")) or ""),
            str(lead.get("last_contact", "") or ""),
            lead.get("messages_sent", 0) or 0,
            lead.get("replies", lead.get("reply_count", 0)) or 0,
            str(lead.get("notes", "") or ""),
        ]

    def _find_row_by_username(self, username: str) -> int | None:
        """Return the 1-based row index for *username*, or None."""
        ws = self._ws or self.ensure_sheet()
        try:
            cell = ws.find(username, in_column=1)
            return cell.row if cell else None
        except gspread.exceptions.CellNotFound:
            return None

    def sync_lead(self, lead_data: dict) -> None:
        """Upsert a single lead row by username."""
        ws = self._ws or self.ensure_sheet()
        row = self._lead_to_row(lead_data)
        existing_row = self._find_row_by_username(lead_data["username"])
        if existing_row:
            ws.update(f"A{existing_row}", [row])
        else:
            ws.append_row(row, value_input_option="USER_ENTERED")

    def sync_all(self, leads: list[dict]) -> int:
        """Bulk-sync a list of leads. Returns count of synced rows."""
        ws = self._ws or self.ensure_sheet()

        # Build a map of existing usernames → row numbers
        all_values = ws.get_all_values()
        username_rows: dict[str, int] = {}
        for idx, r in enumerate(all_values[1:], start=2):  # skip header
            if r:
                username_rows[r[0]] = idx

        updates: list[dict] = []
        appends: list[list] = []

        for lead in leads:
            row = self._lead_to_row(lead)
            existing_idx = username_rows.get(lead["username"])
            if existing_idx:
                updates.append({"range": f"A{existing_idx}:M{existing_idx}", "values": [row]})
            else:
                appends.append(row)

        if updates:
            ws.batch_update(updates, value_input_option="USER_ENTERED")
        if appends:
            ws.append_rows(appends, value_input_option="USER_ENTERED")

        return len(updates) + len(appends)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_hot_leads(self) -> list[dict]:
        """Return leads whose BANT score is ≥ 75."""
        ws = self._ws or self.ensure_sheet()
        rows = ws.get_all_records()
        return [r for r in rows if int(r.get("BANT Score", 0) or 0) >= 75]


def _api_not_enabled_error(detail: str = "") -> RuntimeError:
    """Return a clear error explaining how to enable the required APIs."""
    with open(GOOGLE_CREDS_PATH) as f:
        project = json.load(f).get("project_id", "UNKNOWN")
    return RuntimeError(
        f"Google Sheets/Drive APIs are not enabled on project '{project}'.\n"
        "Enable them at:\n"
        f"  {_ENABLE_URLS[0]}?project={project}\n"
        f"  {_ENABLE_URLS[1]}?project={project}\n"
        "Then retry."
    )
