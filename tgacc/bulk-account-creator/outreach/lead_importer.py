"""Lead importer — parses CSV/JSON, deduplicates, and bulk-inserts leads."""
import csv, io, json, logging
from typing import Optional
from .models import Lead
from . import db

log = logging.getLogger(__name__)

class LeadImporter:
    """Import leads from various formats into the outreach database."""
    
    async def import_from_csv(self, csv_content: str, source: str = "csv_upload", niche: Optional[str] = None, language: str = "en") -> dict:
        """Parse CSV and import leads. Expected columns: username (required), niche, budget_tier, language, notes."""
        reader = csv.DictReader(io.StringIO(csv_content))
        leads = []
        errors = []
        
        for i, row in enumerate(reader):
            username = row.get("username", "").strip().lstrip("@")
            if not username:
                errors.append(f"Row {i+1}: missing username")
                continue
            leads.append(Lead(
                username=username,
                source=source,
                status="new",
                language=row.get("language", language).strip() or language,
                niche=row.get("niche", niche) or niche,
                budget_tier=row.get("budget_tier"),
                notes=row.get("notes", ""),
            ))
        
        return await self._bulk_insert(leads, errors)
    
    async def import_from_json(self, json_data: list[dict], source: str = "json_upload", niche: Optional[str] = None, language: str = "en") -> dict:
        """Import leads from JSON array."""
        leads = []
        errors = []
        
        for i, item in enumerate(json_data):
            username = str(item.get("username", item.get("tg_username", ""))).strip().lstrip("@")
            if not username:
                errors.append(f"Item {i}: missing username")
                continue
            leads.append(Lead(
                username=username,
                source=source,
                status="new",
                language=item.get("language", language) or language,
                niche=item.get("niche", niche) or niche,
                budget_tier=item.get("budget_tier"),
                notes=item.get("notes", ""),
            ))
        
        return await self._bulk_insert(leads, errors)
    
    async def _bulk_insert(self, leads: list[Lead], errors: list[str]) -> dict:
        """Deduplicate and insert leads."""
        # Deduplicate within batch
        seen = set()
        unique = []
        duplicates_in_batch = 0
        for lead in leads:
            if lead.username in seen:
                duplicates_in_batch += 1
                continue
            seen.add(lead.username)
            unique.append(lead)
        
        # Check existing in DB
        existing = await db.get_leads()
        existing_usernames = {l.username for l in existing}
        
        new_leads = [l for l in unique if l.username not in existing_usernames]
        duplicates_in_db = len(unique) - len(new_leads)
        
        # Bulk insert
        inserted = await db.add_leads_bulk(new_leads) if new_leads else 0
        
        result = {
            "total_input": len(leads) + len(errors),
            "imported": inserted,
            "duplicates": duplicates_in_batch + duplicates_in_db,
            "errors": len(errors),
            "error_details": errors[:20],
        }
        log.info("Lead import: %s", result)
        return result
    
    async def import_from_file(self, filepath: str, source: str = "file_upload") -> dict:
        """Import from a file path (auto-detect CSV or JSON)."""
        with open(filepath, "r") as f:
            content = f.read()
        
        content = content.strip()
        if content.startswith("[") or content.startswith("{"):
            data = json.loads(content)
            if isinstance(data, dict):
                data = data.get("leads", [data])
            return await self.import_from_json(data, source=source)
        else:
            return await self.import_from_csv(content, source=source)
