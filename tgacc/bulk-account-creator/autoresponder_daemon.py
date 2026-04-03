#!/usr/bin/env python3
"""Always-on AI autoresponder daemon.

Connects all active outreach accounts and keeps them listening for incoming
messages. Each message triggers the AI responder (RAG + Ollama Cloud) which
generates a natural sales reply.

Usage:
    python autoresponder_daemon.py              # run all active accounts
    python autoresponder_daemon.py --limit 5    # limit to N accounts
    python autoresponder_daemon.py --test       # connect 1 account, print status, exit
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import signal
import sys
from datetime import datetime

# Ensure sibling projects are importable
sys.path.insert(0, "/home/cjs/tgacc/adflux-rag")

from outreach import config, db
from outreach.dispatcher import OutreachDispatcher
from outreach.warming_engine import WarmingEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("autoresponder")


async def run_warmup_cycle(clients: list, stop_event: asyncio.Event) -> None:
    """Background coroutine: run one warming pass per day using connected clients."""
    engine = WarmingEngine()
    log.info("🔥 Warmup background task started (runs once then sleeps 24h)")

    while not stop_event.is_set():
        warmed = 0
        skipped = 0
        failed = 0
        unhealthy = 0

        for client, account in clients:
            if stop_event.is_set():
                break
            try:
                import aiosqlite
                async with aiosqlite.connect(str(config.DB_PATH), timeout=30) as conn:
                    cur = await conn.execute(
                        """SELECT COALESCE(MAX(day), 0) FROM warming_log
                           WHERE phone = ? AND (groups_joined > 0 OR messages_sent > 0
                                 OR channels_read > 0 OR reactions > 0)""",
                        (account.phone,),
                    )
                    row = await cur.fetchone()
                    real_day = row[0] if row and row[0] else 0

                if real_day >= config.WARMING_DAYS:
                    skipped += 1
                    continue

                next_day = real_day + 1
                log.info("🔥 Warming %s: day %d/%d", account.phone, next_day, config.WARMING_DAYS)
                result = await engine.warm_account(account.phone, next_day, client=client)

                if result.get("skipped"):
                    log.warning("🔥 Skipped %s: %s", account.phone, result["skipped"])
                    unhealthy += 1
                    continue

                total = sum(result.get(k, 0) for k in ("groups_joined", "messages_sent", "channels_read", "reactions"))
                log.info("🔥 Warmed %s day %d: %d activities", account.phone, next_day, total)
                warmed += 1
            except Exception as exc:
                log.error("🔥 Warmup failed for %s: %s", account.phone, exc)
                failed += 1

            # Stagger between accounts
            await asyncio.sleep(random.uniform(30, 90))

        log.info("🔥 Warmup cycle complete: %d warmed, %d skipped (done), %d unhealthy, %d failed",
                 warmed, skipped, unhealthy, failed)

        # Sleep until next cycle (~24h with some jitter)
        sleep_secs = 24 * 3600 + random.uniform(-1800, 1800)
        log.info("🔥 Next warmup cycle in %.1f hours", sleep_secs / 3600)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=sleep_secs)
            break  # stop_event was set
        except asyncio.TimeoutError:
            pass  # time to run again


async def main(limit: int | None = None, test: bool = False) -> None:
    await db.init_db()

    dispatcher = OutreachDispatcher()
    accounts = await db.get_accounts()
    active = [a for a in accounts if a.status == "active"]

    if limit:
        active = active[:limit]

    if not active:
        log.error("No active accounts found")
        return

    log.info("Connecting %d accounts for AI autoresponder...", len(active))

    clients = []
    connected = 0

    for account in active:
        try:
            client = await asyncio.wait_for(
                dispatcher.sm.get_client(account.phone), timeout=30
            )
            if not await asyncio.wait_for(
                client.is_user_authorized(), timeout=15
            ):
                log.warning("Account %s not authorized — skipping", account.phone)
                await client.disconnect()
                continue

            await dispatcher.setup_reply_handler(client, account)
            clients.append((client, account))
            connected += 1
            log.info("✅ Connected: %s", account.phone)
        except asyncio.TimeoutError:
            log.error("⏰ Timeout connecting %s — skipping", account.phone)
        except Exception as exc:
            log.error("❌ Failed to connect %s: %s", account.phone, exc)

    log.info(
        "AI Autoresponder LIVE — %d/%d accounts connected, listening for messages...",
        connected,
        len(active),
    )

    if test:
        log.info("Test mode — disconnecting after verification")
        for client, _ in clients:
            await client.disconnect()
        return

    # Keep alive until interrupted
    stop_event = asyncio.Event()

    def _signal_handler():
        log.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    # Start warmup background task using connected clients
    warmup_task = asyncio.create_task(run_warmup_cycle(clients, stop_event))

    await stop_event.wait()

    # Cancel warmup task
    warmup_task.cancel()
    try:
        await warmup_task
    except asyncio.CancelledError:
        pass

    log.info("Disconnecting %d clients...", len(clients))
    for client, _ in clients:
        try:
            await client.disconnect()
        except Exception:
            pass
    log.info("Autoresponder daemon stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AdFlux AI Autoresponder Daemon")
    parser.add_argument("--limit", type=int, help="Limit number of accounts")
    parser.add_argument("--test", action="store_true", help="Connect and verify, then exit")
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit, test=args.test))
