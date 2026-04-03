"""DM templates with personalisation for EN and RU."""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from .models import Lead


# ── template data ───────────────────────────────────────────────────────────

TEMPLATES: dict = {
    "en": {
        "initial_v1": {
            "id": "en_init_v1",
            "text": (
                "Hey {name}! 👋 I noticed you're into {niche} campaigns. "
                "We provide whitelisted agency ad accounts for Google, Meta & "
                "more — no bans, unlimited spend. Interested in scaling your "
                "campaigns? 🚀"
            ),
            "tags": ["casual", "direct"],
        },
        "initial_v2": {
            "id": "en_init_v2",
            "text": (
                "Hi {name}, saw your profile on {source_friendly}. We help "
                "media buyers like you get agency ad accounts that don't get "
                "suspended. Currently serving 500+ buyers across finance, "
                "crypto, nutra. Worth a quick chat?"
            ),
            "tags": ["social_proof", "reference"],
        },
        "initial_v3": {
            "id": "en_init_v3",
            "text": (
                "Hey! Quick question — are you currently running {niche} "
                "campaigns? We've got whitelisted agency accounts on "
                "Google/Meta/Taboola with instant setup and ban replacement "
                "guarantee. Let me know if that's useful 🤙"
            ),
            "tags": ["question", "value_prop"],
        },
        "followup_1": {
            "id": "en_fu1",
            "text": (
                "Hey {name}, just following up on my earlier message. "
                "We've helped buyers scale from $1k to $50k+ daily spend "
                "with our agency accounts. Happy to share some case studies "
                "if you're interested 📊"
            ),
            "delay_hours": 48,
            "tags": ["followup", "case_study"],
        },
        "followup_2": {
            "id": "en_fu2",
            "text": (
                "Last ping {name} — we're running a special this month: "
                "first account setup free + priority support. No pressure, "
                "just wanted to make sure you didn't miss it ✌️"
            ),
            "delay_hours": 120,
            "tags": ["followup", "offer", "urgency"],
        },
    },
    "ru": {
        "initial_v1": {
            "id": "ru_init_v1",
            "text": (
                "Привет {name}! 👋 Заметил, что ты работаешь с {niche}. "
                "Мы предоставляем вайтлист агентские рекламные аккаунты "
                "Google, Meta и другие — без банов, без лимитов. Интересно "
                "масштабировать кампании? 🚀"
            ),
            "tags": ["casual", "direct"],
        },
        "initial_v2": {
            "id": "ru_init_v2",
            "text": (
                "Привет {name}, увидел твой профиль на {source_friendly}. "
                "Помогаем медиабаерам получить агентские аккаунты без "
                "блокировок. Уже обслуживаем 500+ байеров в финансах, крипте, "
                "нутре. Стоит обсудить?"
            ),
            "tags": ["social_proof", "reference"],
        },
        "initial_v3": {
            "id": "ru_init_v3",
            "text": (
                "Привет! Быстрый вопрос — ты сейчас запускаешь {niche} "
                "кампании? У нас есть вайтлист агентские аккаунты "
                "Google/Meta/Taboola с моментальной настройкой и гарантией "
                "замены при бане. Напиши, если актуально 🤙"
            ),
            "tags": ["question", "value_prop"],
        },
        "followup_1": {
            "id": "ru_fu1",
            "text": (
                "Привет {name}, напоминаю о себе. Мы помогли байерам "
                "масштабироваться с $1k до $50k+ дневного спенда с нашими "
                "аккаунтами. Могу скинуть кейсы, если интересно 📊"
            ),
            "delay_hours": 48,
            "tags": ["followup", "case_study"],
        },
        "followup_2": {
            "id": "ru_fu2",
            "text": (
                "Последнее сообщение {name} — в этом месяце акция: первый "
                "аккаунт бесплатно + приоритетная поддержка. Без давления, "
                "просто чтобы не пропустил ✌️"
            ),
            "delay_hours": 120,
            "tags": ["followup", "offer", "urgency"],
        },
    },
}


# ── friendly-name maps ──────────────────────────────────────────────────────

SOURCE_FRIENDLY_NAMES: dict[str, str] = {
    "bhw": "BlackHatWorld",
    "aw": "Affiliate World",
    "hackforums": "the forums",
    "exploit": "the community",
}

NICHE_NAMES: dict[str, dict[str, str]] = {
    "en": {
        "finance": "finance",
        "crypto": "crypto",
        "nutra": "nutra/health",
        "trading": "trading",
        "sweepstakes": "sweepstakes",
        "default": "digital advertising",
    },
    "ru": {
        "finance": "финансы",
        "crypto": "крипту",
        "nutra": "нутру/здоровье",
        "trading": "трейдинг",
        "sweepstakes": "свипстейки",
        "default": "рекламу",
    },
}


# ── emoji variation for anti-fingerprinting ─────────────────────────────────

_EMOJI_VARIANTS = {
    "🚀": ["🚀", "🔥", "💪", "📈"],
    "📊": ["📊", "📈", "💡", "🎯"],
    "✌️": ["✌️", "🤝", "👋", "🙌"],
    "🤙": ["🤙", "💬", "📩", "✉️"],
    "👋": ["👋", "✋", "🖐️", "🤚"],
}


# ── engine ──────────────────────────────────────────────────────────────────

class TemplateEngine:
    """Render and select DM templates with personalisation."""

    def render(self, template_id: str, language: str, **context) -> str:
        """Render a template filling placeholders and adding light randomisation."""
        lang_templates = TEMPLATES.get(language, TEMPLATES["en"])
        tpl = None
        for _key, t in lang_templates.items():
            if t["id"] == template_id:
                tpl = t
                break
        if tpl is None:
            raise ValueError(f"Unknown template: {template_id} (lang={language})")

        text = tpl["text"]

        # Fill placeholders
        name = context.get("name", "")
        source_friendly = context.get(
            "source_friendly",
            SOURCE_FRIENDLY_NAMES.get(context.get("source", ""), "the community"),
        )
        niche_map = NICHE_NAMES.get(language, NICHE_NAMES["en"])
        niche = niche_map.get(
            context.get("niche", ""), niche_map["default"]
        )
        text = text.replace("{name}", name)
        text = text.replace("{source_friendly}", source_friendly)
        text = text.replace("{niche}", niche)

        # Light emoji randomisation
        for original, variants in _EMOJI_VARIANTS.items():
            if original in text:
                text = text.replace(original, random.choice(variants))

        return text

    def select_template(self, lead: "Lead", attempt: int = 1) -> Tuple[str, str]:
        """Pick the best template for *lead* and return (template_id, language).

        attempt 1 → random initial_v*
        attempt 2 → followup_1
        attempt 3 → followup_2
        """
        lang = lead.language if lead.language in TEMPLATES else "en"
        lang_templates = TEMPLATES[lang]

        if attempt == 1:
            initials = [
                t["id"]
                for key, t in lang_templates.items()
                if key.startswith("initial_")
            ]
            return random.choice(initials), lang
        elif attempt == 2:
            return lang_templates["followup_1"]["id"], lang
        else:
            return lang_templates["followup_2"]["id"], lang
