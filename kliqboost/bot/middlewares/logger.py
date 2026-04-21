"""Middleware that logs every incoming message AND outgoing response to SQLite."""

import functools
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from db.conversations import log_message

log = logging.getLogger(__name__)


def _wrap_answer(original_fn, user_id: int, username, first_name):
    """Wrap message.answer / message.reply to also log outgoing text."""

    @functools.wraps(original_fn)
    async def wrapper(*args, **kwargs):
        result = await original_fn(*args, **kwargs)
        # Extract the text that was sent
        text = args[0] if args else kwargs.get("text")
        if text and user_id:
            try:
                await log_message(user_id, username, first_name, "out", text)
            except Exception as exc:
                log.debug("Failed to log outgoing message: %s", exc)
        return result

    return wrapper


class ConversationLoggerMiddleware(BaseMiddleware):
    """Logs incoming user messages and outgoing bot responses."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        user = event.from_user
        if not user:
            return await handler(event, data)

        uid = user.id
        uname = user.username
        fname = user.first_name

        # Log incoming message
        if event.text:
            await log_message(uid, uname, fname, "in", event.text)

        # Wrap answer/reply to log outgoing messages (bypass Pydantic frozen model)
        object.__setattr__(event, "answer", _wrap_answer(event.answer, uid, uname, fname))
        object.__setattr__(event, "reply", _wrap_answer(event.reply, uid, uname, fname))

        result = await handler(event, data)
        return result


class CallbackLoggerMiddleware(BaseMiddleware):
    """Logs callback query interactions (button presses and resulting edits)."""

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user = event.from_user
        if not user:
            return await handler(event, data)

        uid = user.id
        uname = user.username
        fname = user.first_name

        # Log the button press as incoming
        if event.data:
            await log_message(uid, uname, fname, "in", f"[button] {event.data}")

        # Wrap edit_text and answer on the message to log outgoing edits
        if event.message and hasattr(event.message, "edit_text"):
            original_edit = event.message.edit_text

            @functools.wraps(original_edit)
            async def logged_edit(*args, **kwargs):
                result = await original_edit(*args, **kwargs)
                text = args[0] if args else kwargs.get("text")
                if text:
                    try:
                        await log_message(uid, uname, fname, "out", text)
                    except Exception as exc:
                        log.debug("Failed to log edited message: %s", exc)
                return result

            object.__setattr__(event.message, "edit_text", logged_edit)

        result = await handler(event, data)
        return result
