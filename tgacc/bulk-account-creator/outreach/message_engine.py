"""Hybrid LLM + Spintax message generation engine.

Pre-generates cryptographically unique outreach messages in bulk before a
campaign starts, then serves them one-by-one during send.  Falls back to
the Spintax engine when the LLM pool runs low.

Every message is SHA-256 fingerprinted and stored in SQLite so no two
outgoing DMs ever share the same content hash — defeating Telegram's
content-hashing spam detection.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import aiohttp
import aiosqlite

from . import config

log = logging.getLogger(__name__)

# ── LLM configuration (mirrors ai_responder.py) ────────────────────────────

OLLAMA_URL = "https://ollama.com/v1/chat/completions"
OLLAMA_API_KEY = os.getenv(
    "OLLAMA_API_KEY",
    "baeb6fd660e34f15bab48271e676cf74.UHEnKkigGk5x3N_M4TEXLx4t",
)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2:1t")

DB = str(config.DB_PATH)

# ── Data types ──────────────────────────────────────────────────────────────


@dataclass
class GeneratedMessage:
    """A single pre-generated outreach message."""

    text: str
    hash: str  # SHA-256 hex digest
    source: str  # "llm" or "spintax"
    campaign_id: str = ""


# ── Schema for the message pool table ───────────────────────────────────────

_POOL_SCHEMA = """\
CREATE TABLE IF NOT EXISTS message_pool (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id  TEXT    NOT NULL,
    text         TEXT    NOT NULL,
    hash         TEXT    UNIQUE NOT NULL,
    source       TEXT    DEFAULT 'llm',
    used         INTEGER DEFAULT 0,
    used_at      TEXT,
    target_user_id INTEGER,
    session_phone  TEXT,
    created_at   TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_message_pool_campaign
    ON message_pool(campaign_id, used);
"""

# ── Engine ──────────────────────────────────────────────────────────────────


class MessageEngine:
    """Hybrid LLM + Spintax message generation engine."""

    def __init__(
        self,
        db_path: str | None = None,
        ollama_url: str | None = None,
        ollama_model: str | None = None,
    ) -> None:
        self.db_path = db_path or DB
        self.ollama_url = ollama_url or OLLAMA_URL
        self.ollama_model = ollama_model or OLLAMA_MODEL
        self._sent_hashes: set[str] = set()
        self._message_pool: list[GeneratedMessage] = []
        self._pool_index: int = 0

    # ── DB bootstrap ────────────────────────────────────────────────────

    async def init_db(self) -> None:
        """Create the ``message_pool`` table if it does not exist."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.executescript(_POOL_SCHEMA)
            await conn.commit()
        log.info("message_pool table ready at %s", self.db_path)

    # ── LLM batch pre-generation ────────────────────────────────────────

    async def pre_generate_llm_batch(
        self,
        campaign_id: str,
        niche: str,
        count: int = 500,
        style: str = "casual",
        max_chars: int = 200,
        language: str = "en",
    ) -> dict:
        """Pre-generate *count* unique messages via Ollama LLM.

        Called **before** the campaign starts.  Each LLM call asks for 10
        unique messages so we make roughly ``count / 10`` API calls.

        Returns ``{generated, duplicates_skipped, errors}``.
        """
        batch_size = 10

        system_prompt = (
            f"You are a cold outreach message generator. Generate {batch_size} "
            f"completely unique, casual Telegram DM messages for {niche} outreach. "
            f"Each message must be:\n"
            f"- Under {max_chars} characters\n"
            f"- Casual and human-like (use natural language, occasional emoji, "
            f"informal tone)\n"
            f"- Different structure/opening/proposition from every other message\n"
            f"- NOT look like spam or automated text\n"
            f"- In {language} language\n"
            f"- Style: {style}\n\n"
            f"Output ONLY a JSON array of strings. No explanations. No markdown.\n"
            f'Example: ["Hey! Saw your posts about crypto, pretty cool stuff '
            f'🔥 Mind if I share something?", ...]'
        )

        generated = 0
        duplicates = 0
        errors = 0
        total_batches = count // batch_size + (1 if count % batch_size else 0)

        for batch_num in range(total_batches):
            if generated >= count:
                break

            try:
                raw = await self._call_llm(system_prompt)
                if not raw:
                    errors += 1
                    continue

                parsed = self._parse_llm_response(raw)

                for text in parsed:
                    if generated >= count:
                        break

                    text = text.strip()
                    if not text or len(text) > int(max_chars * 1.5):
                        continue

                    msg_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

                    if msg_hash in self._sent_hashes:
                        duplicates += 1
                        continue

                    self._sent_hashes.add(msg_hash)
                    await self._save_message(campaign_id, text, msg_hash, "llm")
                    generated += 1

                log.info(
                    "LLM batch %d/%d: +%d messages (total %d/%d)",
                    batch_num + 1,
                    total_batches,
                    len(parsed),
                    generated,
                    count,
                )

                await asyncio.sleep(1.0)

            except Exception as exc:
                log.error("LLM batch %d failed: %s", batch_num + 1, exc)
                errors += 1
                await asyncio.sleep(2.0)

        result = {
            "generated": generated,
            "duplicates_skipped": duplicates,
            "errors": errors,
        }
        log.info("LLM pre-generation complete: %s", result)
        return result

    # ── Spintax batch pre-generation ────────────────────────────────────

    async def pre_generate_spintax_batch(
        self,
        campaign_id: str,
        template: str,
        count: int = 500,
    ) -> dict:
        """Pre-generate messages using the Spintax engine (fallback).

        Returns ``{generated, duplicates_skipped}`` (or ``error`` key on
        template validation failure).
        """
        from .spintax import SpintaxEngine

        engine = SpintaxEngine()

        valid, error = engine.validate_template(template)
        if not valid:
            log.error("Invalid spintax template: %s", error)
            return {"generated": 0, "duplicates_skipped": 0, "error": error}

        generated = 0
        duplicates = 0

        for _ in range(count):
            result = engine.spin(template)

            if result.hash in self._sent_hashes:
                duplicates += 1
                continue

            self._sent_hashes.add(result.hash)
            await self._save_message(
                campaign_id, result.text, result.hash, "spintax"
            )
            generated += 1

        return {"generated": generated, "duplicates_skipped": duplicates}

    # ── Pool consumption ────────────────────────────────────────────────

    async def load_pool(self, campaign_id: str) -> None:
        """Load unused messages from DB into memory for fast access."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT text, hash, source FROM message_pool "
                "WHERE campaign_id = ? AND used = 0 "
                "ORDER BY id",
                (campaign_id,),
            )
            rows = await cur.fetchall()

        self._message_pool = [
            GeneratedMessage(
                text=r["text"],
                hash=r["hash"],
                source=r["source"],
                campaign_id=campaign_id,
            )
            for r in rows
        ]
        self._pool_index = 0

        # Rebuild the hash set from all messages (used + unused)
        async with aiosqlite.connect(self.db_path) as conn:
            cur = await conn.execute(
                "SELECT hash FROM message_pool WHERE campaign_id = ?",
                (campaign_id,),
            )
            rows = await cur.fetchall()
        for r in rows:
            self._sent_hashes.add(r[0])

        log.info(
            "Loaded %d unused messages for campaign %s",
            len(self._message_pool),
            campaign_id,
        )

    async def get_unique_message(
        self, campaign_id: str
    ) -> Optional[GeneratedMessage]:
        """Return the next unused message and mark it as used.

        Returns ``None`` when the pool is exhausted.
        """
        if self._pool_index >= len(self._message_pool):
            return None

        msg = self._message_pool[self._pool_index]
        self._pool_index += 1

        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "UPDATE message_pool SET used = 1, used_at = ? WHERE hash = ?",
                (now, msg.hash),
            )
            await conn.commit()

        self._sent_hashes.add(msg.hash)
        return msg

    async def get_pool_stats(self, campaign_id: str) -> dict:
        """Return pool statistics for *campaign_id*."""
        async with aiosqlite.connect(self.db_path) as conn:
            cur = await conn.execute(
                "SELECT COUNT(*) FROM message_pool WHERE campaign_id = ?",
                (campaign_id,),
            )
            total = (await cur.fetchone())[0]

            cur = await conn.execute(
                "SELECT COUNT(*) FROM message_pool "
                "WHERE campaign_id = ? AND used = 1",
                (campaign_id,),
            )
            used = (await cur.fetchone())[0]

            cur = await conn.execute(
                "SELECT source, COUNT(*) FROM message_pool "
                "WHERE campaign_id = ? GROUP BY source",
                (campaign_id,),
            )
            breakdown = {r[0]: r[1] for r in await cur.fetchall()}

        return {
            "total": total,
            "used": used,
            "remaining": total - used,
            "source_breakdown": breakdown,
        }

    # ── Uniqueness helpers ──────────────────────────────────────────────

    def verify_uniqueness(self, text: str) -> bool:
        """Return ``True`` if *text* has never been sent before."""
        msg_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return msg_hash not in self._sent_hashes

    def mark_sent(self, msg_hash: str) -> None:
        """Record a hash as sent (redundant safety after DB mark)."""
        self._sent_hashes.add(msg_hash)

    # ── Ollama Cloud client (mirrors ai_responder._ollama_chat) ─────────

    async def _call_llm(self, prompt: str) -> str:
        """Send a chat-completion request to Ollama Cloud."""
        payload = {
            "model": self.ollama_model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Generate the messages now."},
            ],
            "temperature": 0.9,
            "max_tokens": 2000,
        }
        headers = {
            "Authorization": f"Bearer {OLLAMA_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.ollama_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        log.error("Ollama API error (%d): %s", resp.status, body)
                        return ""
                    data = await resp.json()
                    return (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
        except Exception as exc:
            log.error("Ollama request failed: %s", exc)
            return ""

    # ── LLM response parsing ───────────────────────────────────────────

    @staticmethod
    def _parse_llm_response(response: str) -> list[str]:
        """Parse a JSON array from the LLM response.

        Handles markdown code fences and falls back to line-by-line
        extraction when the JSON is malformed.
        """
        text = response.strip()

        # Strip markdown code block wrappers
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            if text.startswith("json"):
                text = text[4:].strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(m) for m in parsed if m]
            return []
        except json.JSONDecodeError:
            log.warning("Failed to parse LLM JSON; falling back to line split")
            lines = [
                line.strip().strip('"').strip("'").strip(",")
                for line in text.split("\n")
            ]
            return [line for line in lines if line and len(line) > 10]

    # ── DB persistence ─────────────────────────────────────────────────

    async def _save_message(
        self, campaign_id: str, text: str, hash_val: str, source: str
    ) -> None:
        """Persist a generated message to the pool table."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO message_pool "
                "(campaign_id, text, hash, source) VALUES (?, ?, ?, ?)",
                (campaign_id, text, hash_val, source),
            )
            await conn.commit()


# ── CLI convenience ─────────────────────────────────────────────────────────


async def pre_generate_campaign_messages(
    campaign_id: str,
    niche: str,
    count: int = 500,
    spintax_template: str | None = None,
) -> None:
    """Pre-generate messages for a campaign (LLM primary, Spintax fallback)."""
    engine = MessageEngine()
    await engine.init_db()

    result = await engine.pre_generate_llm_batch(campaign_id, niche, count)
    log.info("LLM generation: %s", result)

    if spintax_template:
        remaining = count - result["generated"]
        if remaining > 0:
            spintax_result = await engine.pre_generate_spintax_batch(
                campaign_id, spintax_template, remaining
            )
            log.info("Spintax supplement: %s", spintax_result)

    stats = await engine.get_pool_stats(campaign_id)
    log.info("Message pool stats: %s", stats)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Pre-generate campaign messages (LLM + Spintax)"
    )
    parser.add_argument("--campaign", required=True, help="Campaign ID")
    parser.add_argument("--niche", required=True, help="Target niche")
    parser.add_argument(
        "--count", type=int, default=500, help="Number of messages"
    )
    parser.add_argument(
        "--spintax", default=None, help="Spintax template (fallback)"
    )
    args = parser.parse_args()

    asyncio.run(
        pre_generate_campaign_messages(
            args.campaign, args.niche, args.count, args.spintax
        )
    )
