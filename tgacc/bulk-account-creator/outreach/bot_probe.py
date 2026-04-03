"""Competitor bot probe — recursively map a Telegram bot's menu tree."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from telethon import TelegramClient
from telethon.tl.types import (
    ReplyInlineMarkup,
    KeyboardButtonCallback,
    KeyboardButtonUrl,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from .session_manager import SessionManager

log = logging.getLogger(__name__)


class BotProbe:
    """Interact with a Telegram bot and map its menu structure."""

    def __init__(self) -> None:
        self.sm = SessionManager()

    async def probe_bot(
        self,
        bot_username: str,
        phone: str | None = None,
        depth: int = 3,
    ) -> dict:
        """Recursively explore *bot_username* up to *depth* levels.

        Returns a tree structure::

            {
                "bot": "@ProfitLobby1_bot",
                "start_response": "Welcome! ...",
                "buttons": [
                    {
                        "label": "Services",
                        "type": "callback",
                        "response": "...",
                        "children": [ ... ]
                    },
                    ...
                ]
            }
        """
        # Pick a session to use
        if phone is None:
            phones = await self.sm.rotate_sessions()
            if not phones:
                log.error("No sessions available for bot probing")
                return {"error": "no_sessions"}
            phone = phones[0]

        client = await self.sm.get_client(phone)
        try:
            tree = await self._explore(client, bot_username, depth)
        finally:
            await client.disconnect()

        return tree

    async def _explore(
        self, client: TelegramClient, bot_username: str, depth: int
    ) -> dict:
        """Send /start and recursively click inline buttons."""
        tree: dict[str, Any] = {"bot": f"@{bot_username}", "buttons": []}

        try:
            resp = await client.send_message(bot_username, "/start")
            await asyncio.sleep(2)

            # Get the bot's reply
            messages = await client.get_messages(bot_username, limit=2)
            bot_reply = None
            for m in messages:
                if m.out is False:
                    bot_reply = m
                    break

            if bot_reply is None:
                tree["start_response"] = "(no response)"
                return tree

            tree["start_response"] = bot_reply.text or "(media/empty)"

            if depth <= 0:
                return tree

            # Parse inline keyboard
            if isinstance(bot_reply.reply_markup, ReplyInlineMarkup):
                for row in bot_reply.reply_markup.rows:
                    for btn in row.buttons:
                        btn_info = await self._handle_inline_button(
                            client, bot_username, bot_reply, btn, depth - 1
                        )
                        tree["buttons"].append(btn_info)

            # Parse reply keyboard
            elif isinstance(bot_reply.reply_markup, ReplyKeyboardMarkup):
                for row in bot_reply.reply_markup.rows:
                    for btn in row.buttons:
                        if isinstance(btn, KeyboardButton):
                            btn_info = await self._handle_reply_button(
                                client, bot_username, btn.text, depth - 1
                            )
                            tree["buttons"].append(btn_info)

        except Exception as exc:
            tree["error"] = str(exc)
            log.error("Bot probe error for @%s: %s", bot_username, exc)

        return tree

    async def _handle_inline_button(
        self,
        client: TelegramClient,
        bot_username: str,
        message,
        button,
        depth: int,
    ) -> dict:
        """Click an inline button and optionally recurse."""
        info: dict[str, Any] = {"label": button.text, "children": []}

        if isinstance(button, KeyboardButtonUrl):
            info["type"] = "url"
            info["url"] = button.url
            return info

        if isinstance(button, KeyboardButtonCallback):
            info["type"] = "callback"
            info["data"] = button.data.decode("utf-8", errors="replace") if button.data else ""
        else:
            info["type"] = "other"
            return info

        try:
            await message.click(data=button.data)
            await asyncio.sleep(2)

            # Get updated messages
            messages = await client.get_messages(bot_username, limit=2)
            reply = None
            for m in messages:
                if m.out is False:
                    reply = m
                    break

            if reply:
                info["response"] = reply.text or "(media/empty)"

                if depth > 0 and isinstance(reply.reply_markup, ReplyInlineMarkup):
                    for row in reply.reply_markup.rows:
                        for child_btn in row.buttons:
                            child = await self._handle_inline_button(
                                client, bot_username, reply, child_btn, depth - 1
                            )
                            info["children"].append(child)
        except Exception as exc:
            info["error"] = str(exc)

        return info

    async def _handle_reply_button(
        self,
        client: TelegramClient,
        bot_username: str,
        text: str,
        depth: int,
    ) -> dict:
        """Send a reply-keyboard button's text and capture response."""
        info: dict[str, Any] = {"label": text, "type": "reply_keyboard", "children": []}

        try:
            await client.send_message(bot_username, text)
            await asyncio.sleep(2)

            messages = await client.get_messages(bot_username, limit=2)
            reply = None
            for m in messages:
                if m.out is False:
                    reply = m
                    break

            if reply:
                info["response"] = reply.text or "(media/empty)"
        except Exception as exc:
            info["error"] = str(exc)

        return info
