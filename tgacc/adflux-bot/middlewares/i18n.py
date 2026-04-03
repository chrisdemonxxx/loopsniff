from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from texts import LANG_TEXTS
from db.persistence import get_language, set_language

# In-memory per-user language cache (backed by SQLite via db.persistence)
_user_langs: Dict[int, str] = {}


def get_lang(user_id: int) -> str:
    if user_id not in _user_langs:
        _user_langs[user_id] = get_language(user_id)
    return _user_langs[user_id]


def set_lang(user_id: int, lang: str) -> None:
    _user_langs[user_id] = lang
    set_language(user_id, lang)


def t(user_id: int, key: str, **kwargs: Any) -> str:
    lang = get_lang(user_id)
    text = LANG_TEXTS.get(lang, LANG_TEXTS["en"]).get(key, LANG_TEXTS["en"].get(key, key))
    if kwargs:
        text = text.format(**kwargs)
    return text


class I18nMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            data["lang"] = get_lang(user.id)
            data["t"] = lambda key, **kw: t(user.id, key, **kw)
        return await handler(event, data)
