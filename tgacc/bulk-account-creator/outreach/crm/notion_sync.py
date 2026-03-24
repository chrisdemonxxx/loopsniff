"""Notion sync for outreach leads using notion-client + httpx."""

from __future__ import annotations

import time
from datetime import datetime

import httpx

from .config import NOTION_TOKEN, NOTION_DB_ID


_MIN_INTERVAL = 0.34  # ≈3 req/sec rate limit
_API_BASE = "https://api.notion.com/v1"
_NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


class NotionSync:
    """Sync outreach leads to a Notion database."""

    def __init__(self) -> None:
        self.db_id = NOTION_DB_ID
        self._last_request: float = 0.0
        self._http = httpx.Client(headers=_NOTION_HEADERS, timeout=30)

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        self._last_request = time.time()

    # ------------------------------------------------------------------
    # Database setup
    # ------------------------------------------------------------------

    def setup_database(self) -> None:
        """Add required properties to the existing Notion database."""
        self._throttle()
        self._http.patch(
            f"{_API_BASE}/databases/{self.db_id}",
            json={
                "properties": {
                "Name": {"title": {}},
                "Source": {
                    "select": {
                        "options": [
                            {"name": "bhw", "color": "blue"},
                            {"name": "aw", "color": "green"},
                            {"name": "hackforums", "color": "orange"},
                            {"name": "exploit", "color": "red"},
                        ]
                    }
                },
                "Status": {
                    "select": {
                        "options": [
                            {"name": "new", "color": "default"},
                            {"name": "contacted", "color": "blue"},
                            {"name": "replied", "color": "green"},
                            {"name": "qualified", "color": "yellow"},
                            {"name": "hot", "color": "red"},
                            {"name": "converted", "color": "purple"},
                            {"name": "dead", "color": "gray"},
                        ]
                    }
                },
                "BANT Score": {"number": {"format": "number"}},
                "Budget": {"rich_text": {}},
                "Platform": {
                    "multi_select": {
                        "options": [
                            {"name": "google", "color": "blue"},
                            {"name": "meta", "color": "green"},
                            {"name": "tiktok", "color": "pink"},
                            {"name": "taboola", "color": "orange"},
                            {"name": "outbrain", "color": "yellow"},
                        ]
                    }
                },
                "Niche": {"rich_text": {}},
                "Timeline": {
                    "select": {
                        "options": [
                            {"name": "asap", "color": "red"},
                            {"name": "1-2 weeks", "color": "orange"},
                            {"name": "1 month", "color": "yellow"},
                            {"name": "no rush", "color": "default"},
                        ]
                    }
                },
                "First Contact": {"date": {}},
                "Last Contact": {"date": {}},
                "Messages Sent": {"number": {"format": "number"}},
                "Replies": {"number": {"format": "number"}},
                "Notes": {"rich_text": {}},
                }
            },
        ).raise_for_status()

    # ------------------------------------------------------------------
    # Property builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_properties(lead: dict) -> dict:
        """Build Notion page properties from a lead dict."""
        props: dict = {
            "Name": {"title": [{"text": {"content": str(lead.get("username", ""))}}]},
        }

        if lead.get("source"):
            props["Source"] = {"select": {"name": str(lead["source"])}}

        if lead.get("status"):
            props["Status"] = {"select": {"name": str(lead["status"])}}

        bant = lead.get("bant_score", 0) or 0
        props["BANT Score"] = {"number": int(bant)}

        budget = lead.get("budget", lead.get("budget_tier", "")) or ""
        if budget:
            props["Budget"] = {"rich_text": [{"text": {"content": str(budget)}}]}

        platform = lead.get("platform", "") or ""
        if platform:
            names = [p.strip() for p in str(platform).split(",") if p.strip()]
            props["Platform"] = {"multi_select": [{"name": n} for n in names]}

        niche = lead.get("niche", "") or ""
        if niche:
            props["Niche"] = {"rich_text": [{"text": {"content": str(niche)}}]}

        timeline = lead.get("timeline", "") or ""
        if timeline:
            props["Timeline"] = {"select": {"name": str(timeline)}}

        first_contact = lead.get("first_contact", lead.get("contacted_at", "")) or ""
        if first_contact:
            props["First Contact"] = {"date": {"start": _to_iso_date(first_contact)}}

        last_contact = lead.get("last_contact", "") or ""
        if last_contact:
            props["Last Contact"] = {"date": {"start": _to_iso_date(last_contact)}}

        msgs = lead.get("messages_sent", 0) or 0
        props["Messages Sent"] = {"number": int(msgs)}

        replies = lead.get("replies", lead.get("reply_count", 0)) or 0
        props["Replies"] = {"number": int(replies)}

        notes = lead.get("notes", "") or ""
        if notes:
            props["Notes"] = {"rich_text": [{"text": {"content": str(notes)[:2000]}}]}

        return props

    # ------------------------------------------------------------------
    # Lead sync
    # ------------------------------------------------------------------

    def _query_database(self, filter_obj: dict | None = None) -> dict:
        """Query the database via the REST API (not in notion-client v3)."""
        self._throttle()
        body: dict = {}
        if filter_obj:
            body["filter"] = filter_obj
        resp = self._http.post(
            f"{_API_BASE}/databases/{self.db_id}/query", json=body
        )
        resp.raise_for_status()
        return resp.json()

    def _find_page_by_username(self, username: str) -> str | None:
        """Query the database for a page whose Name matches *username*."""
        data = self._query_database(
            {"property": "Name", "title": {"equals": username}}
        )
        results = data.get("results", [])
        return results[0]["id"] if results else None

    def sync_lead(self, lead_data: dict) -> str:
        """Upsert a single lead page by username. Returns page id."""
        props = self._build_properties(lead_data)
        page_id = self._find_page_by_username(lead_data["username"])

        if page_id:
            self._throttle()
            self._http.patch(
                f"{_API_BASE}/pages/{page_id}",
                json={"properties": props},
            ).raise_for_status()
            return page_id
        else:
            self._throttle()
            resp = self._http.post(
                f"{_API_BASE}/pages",
                json={
                    "parent": {"database_id": self.db_id},
                    "properties": props,
                },
            )
            resp.raise_for_status()
            return resp.json()["id"]

    def sync_all(self, leads: list[dict]) -> int:
        """Bulk sync with Notion rate limiting (~3 req/sec). Returns count."""
        synced = 0
        for lead in leads:
            self.sync_lead(lead)
            synced += 1
        return synced

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_hot_leads(self) -> list[dict]:
        """Return leads with BANT Score ≥ 75."""
        data = self._query_database(
            {
                "property": "BANT Score",
                "number": {"greater_than_or_equal_to": 75},
            }
        )
        return data.get("results", [])


def _to_iso_date(value: str) -> str:
    """Normalise various date formats to YYYY-MM-DD."""
    if not value:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value[:10]
