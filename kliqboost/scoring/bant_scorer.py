"""BANT scoring engine — Budget, Ads-platform, Niche, Timeline.

Scores leads on a 0-100 scale so the outreach engine can prioritise
follow-ups and route hot leads to admin.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Score tables
# ---------------------------------------------------------------------------

BUDGET_SCORES: Dict[str, int] = {
    "$50k+": 30,
    "$10k-$50k": 25,
    "$5k-$10k": 20,
    "$1k-$5k": 15,
    "< $1k": 5,
    "unknown": 10,
}

PLATFORM_SCORES: Dict[str, int] = {
    "google": 25,
    "meta": 22,
    "tiktok": 22,
    "bing": 20,
    "taboola": 20,
    "outbrain": 20,
    "snapchat": 18,
    "twitter": 18,
    "mediago": 18,
    "multiple": 25,
    "unknown": 10,
}

NICHE_SCORES: Dict[str, int] = {
    "crypto": 15,
    "finance": 15,
    "gambling": 15,
    "nutra": 12,
    "trading": 12,
    "dating": 12,
    "tech_support": 12,
    "sweepstakes": 10,
    "ecommerce": 8,
    "other": 5,
    "unknown": 5,
}

TIMELINE_SCORES: Dict[str, int] = {
    "asap": 30,
    "this_week": 25,
    "this_month": 15,
    "exploring": 5,
    "unknown": 10,
}

# ---------------------------------------------------------------------------
# Text-analysis helpers
# ---------------------------------------------------------------------------

_BUDGET_PATTERNS: list[tuple[re.Pattern, str]] = [
    # $50k+
    (re.compile(r"\$\s*50\s*k|\$\s*50[\s,]*000|50k\+?|100k|200k|50\s*тыс|100\s*тыс", re.I), "$50k+"),
    # $10k-$50k
    (re.compile(
        r"\$\s*[1-4]\d\s*k|\$\s*[1-4]\d[\s,]*000|(?:1[0-9]|2[0-9]|3[0-9]|4[0-9])k"
        r"|20k|30k|40k|15k|25k|35k|45k"
        r"|20\s*тыс|30\s*тыс|40\s*тыс", re.I
    ), "$10k-$50k"),
    # $5k-$10k
    (re.compile(
        r"\$\s*[5-9]\s*k|\$\s*[5-9][\s,]*000|[5-9]k"
        r"|\d{4,}/\s*day|\d{4,}\s*/\s*день"
        r"|5\s*тыс|6\s*тыс|7\s*тыс|8\s*тыс|9\s*тыс", re.I
    ), "$5k-$10k"),
    # $1k-$5k
    (re.compile(
        r"\$\s*[1-4]\s*k|\$\s*[1-4][\s,]*000|[1-4]k"
        r"|\d{3,4}\s*/\s*day|\d{3,4}\s*/\s*день"
        r"|1\s*тыс|2\s*тыс|3\s*тыс|4\s*тыс"
        r"|1000\b|2000\b|3000\b|4000\b|5000\b", re.I
    ), "$1k-$5k"),
    # < $1k
    (re.compile(
        r"\$\s*\d{2,3}(?!\d)|few hundred|small budget"
        r"|маленький бюджет|немного", re.I
    ), "< $1k"),
]

_PLATFORM_KEYWORDS: dict[str, list[str]] = {
    "google": [
        "google", "google ads", "adwords", "gads", "pmax", "performance max",
        "gg ", "gg\n", "bsod", "гугл", "гугл адс", "адвордс",
        "гг ", "гг\n", "agency account", "agency acc", "mcc",
        "гугл аккаунт", "гугл акк",
    ],
    "meta": [
        "meta", "facebook", "fb ads", "instagram", "ig ads", "fb ",
        "fb\n", "фб", "фейсбук", "инста", "инстаграм", "мета",
        "bm ", "bm\n", "business manager", "бм ",
    ],
    "tiktok": [
        "tiktok", "tik tok", "tt ads", "tt ", "tt\n",
        "тикток", "тик ток", "тт ",
    ],
    "bing": [
        "bing", "microsoft ads", "bing ads",
        "бинг", "майкрософт",
    ],
    "taboola": ["taboola", "табула"],
    "outbrain": ["outbrain", "аутбрейн"],
    "mediago": ["mediago", "media go", "медиаго"],
    "snapchat": ["snapchat", "snap ads", "снэпчат"],
    "twitter": ["twitter", "x ads", "твиттер"],
}

_NICHE_KEYWORDS: dict[str, list[str]] = {
    "crypto": [
        "crypto", "bitcoin", "btc", "defi", "web3", "nft",
        "крипто", "биткоин", "криптовалют",
    ],
    "finance": [
        "finance", "forex", "stocks", "insurance", "loans", "fintech",
        "финанс", "форекс", "страхов", "кредит",
    ],
    "nutra": [
        "nutra", "health", "supplement", "weight loss", "diet",
        "нутра", "здоровье", "похуде", "добавк",
    ],
    "gambling": [
        "gambling", "casino", "betting", "slots", "poker", "bet ",
        "гемблинг", "казино", "ставки", "покер", "слоты", "букмекер",
    ],
    "trading": [
        "trading", "binary", "options", "cfd",
        "трейдинг", "бинарные", "опционы",
    ],
    "sweepstakes": [
        "sweepstakes", "sweeps", "giveaway", "contest",
        "свипстейк", "розыгрыш",
    ],
    "dating": [
        "dating", "adult", "18+",
        "дейтинг", "знакомств",
    ],
    "ecommerce": [
        "ecommerce", "e-commerce", "shopify", "dropship", "store",
        "екоммерс", "дропшип", "магазин",
    ],
    "tech_support": [
        "tech support", "techsupport", "call center", "pop up",
        "тех поддержк", "колл центр",
    ],
}

_URGENCY_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(
        r"\basap\b|right now|immediately|urgent|today|\bnow\b"
        r"|looking to buy|need .{0,10}(now|asap|today|urgently)"
        r"|срочно|прямо сейчас|сегодня|немедленно"
        r"|готов купить|нужн.{0,5}сейчас", re.I
    ), "asap"),
    (re.compile(
        r"this week|next few days|in a couple days|ready to buy|want to buy"
        r"|looking for|на этой неделе|хочу купить|готов заказ", re.I
    ), "this_week"),
    (re.compile(
        r"this month|next week|soon|shortly|interested"
        r"|на следующей|скоро|интересует|в этом месяце", re.I
    ), "this_month"),
    (re.compile(
        r"exploring|just looking|researching|maybe|later"
        r"|просто смотрю|может быть|потом|позже", re.I
    ), "exploring"),
]

# Negative / disqualification signals
_NEGATIVE_SIGNALS = re.compile(
    r"\bnot interested\b|\bstop\b|\bunsubscribe\b|\bno thanks\b"
    r"|\bleave me alone\b|\bspam\b"
    r"|не интересует|отстань|не надо|стоп|отписаться",
    re.I,
)

# Buying intent signals — boost score when detected
_BUYING_INTENT = re.compile(
    r"\bneed\b|\bwant\b|\blooking for\b|\bgot\s*\?\b|\bhave\s*\?\b"
    r"|\bsell\b|\bbuy\b|\bpurchas\w*\b|\bcop\b|\bgrab\b|\bscoop\b"
    r"|\bhow much\b|\bpric\w*\b|\bcost\b|\brate\b"
    r"|\baccounts?\b|\baccs?\b"
    r"|\bнужн\w*\b|\bкупить\b|\bпродаёшь\b|\bпродаешь\b|\bесть\b"
    r"|\bсколько\b|\bцена\b|\bстоимость\b|\bаккаунт\w*\b|\bакк\w*\b",
    re.I,
)


def _tier_from_score(score: int) -> str:
    if score >= 75:
        return "hot"
    if score >= 50:
        return "warm"
    if score >= 25:
        return "cool"
    return "cold"


# ---------------------------------------------------------------------------
# BANTScorer
# ---------------------------------------------------------------------------


class BANTScorer:
    """Score leads on a 0-100 scale using BANT criteria."""

    BUDGET_SCORES = BUDGET_SCORES
    PLATFORM_SCORES = PLATFORM_SCORES
    NICHE_SCORES = NICHE_SCORES
    TIMELINE_SCORES = TIMELINE_SCORES

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(
        self,
        budget: Optional[str] = None,
        platform: Optional[str] = None,
        niche: Optional[str] = None,
        timeline: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculate BANT score from explicit category keys.

        Returns ``{total, breakdown, tier}`` where *tier* is one of
        ``hot | warm | cool | cold``.
        """
        b = self.BUDGET_SCORES.get(budget, self.BUDGET_SCORES["unknown"]) if budget else self.BUDGET_SCORES["unknown"]
        a = self.PLATFORM_SCORES.get(platform, self.PLATFORM_SCORES["unknown"]) if platform else self.PLATFORM_SCORES["unknown"]
        n = self.NICHE_SCORES.get(niche, self.NICHE_SCORES["unknown"]) if niche else self.NICHE_SCORES["unknown"]
        t = self.TIMELINE_SCORES.get(timeline, self.TIMELINE_SCORES["unknown"]) if timeline else self.TIMELINE_SCORES["unknown"]

        total = b + a + n + t
        breakdown = {
            "budget": {"value": budget or "unknown", "score": b},
            "platform": {"value": platform or "unknown", "score": a},
            "niche": {"value": niche or "unknown", "score": n},
            "timeline": {"value": timeline or "unknown", "score": t},
        }

        result = {"total": total, "breakdown": breakdown, "tier": _tier_from_score(total)}
        log.debug("BANT score: %s → %d (%s)", breakdown, total, result["tier"])
        return result

    # ------------------------------------------------------------------

    def score_from_text(self, message_text: str) -> Dict[str, Any]:
        """Extract BANT signals from a single free-text message and score."""
        budget = self._detect_budget(message_text)
        platform = self._detect_platform(message_text)
        niche = self._detect_niche(message_text)
        timeline = self._detect_timeline(message_text)

        result = self.score(budget=budget, platform=platform, niche=niche, timeline=timeline)
        result["negative"] = bool(_NEGATIVE_SIGNALS.search(message_text))
        result["extracted"] = {
            "budget": budget,
            "platform": platform,
            "niche": niche,
            "timeline": timeline,
        }
        return result

    # ------------------------------------------------------------------

    def score_from_conversation(self, messages: List[str]) -> Dict[str, Any]:
        """Aggregate BANT signals across an entire conversation history.

        Each element in *messages* is the text body of a single message
        (from the lead, **not** from our side).  The best signal for each
        dimension wins.
        """
        best_budget: Optional[str] = None
        best_platform: Optional[str] = None
        best_niche: Optional[str] = None
        best_timeline: Optional[str] = None
        has_negative = False
        has_buying_intent = False

        for text in messages:
            b = self._detect_budget(text)
            p = self._detect_platform(text)
            n = self._detect_niche(text)
            t = self._detect_timeline(text)

            if b and self.BUDGET_SCORES.get(b, 0) > self.BUDGET_SCORES.get(best_budget, 0):
                best_budget = b
            if p and self.PLATFORM_SCORES.get(p, 0) > self.PLATFORM_SCORES.get(best_platform, 0):
                best_platform = p
            if n and self.NICHE_SCORES.get(n, 0) > self.NICHE_SCORES.get(best_niche, 0):
                best_niche = n
            if t and self.TIMELINE_SCORES.get(t, 0) > self.TIMELINE_SCORES.get(best_timeline, 0):
                best_timeline = t
            if _NEGATIVE_SIGNALS.search(text):
                has_negative = True
            if _BUYING_INTENT.search(text):
                has_buying_intent = True

        result = self.score(
            budget=best_budget,
            platform=best_platform,
            niche=best_niche,
            timeline=best_timeline,
        )
        # Buying intent bonus: +10 if they're actively asking to buy/price
        if has_buying_intent:
            result["total"] = min(result["total"] + 10, 100)
            result["tier"] = _tier_from_score(result["total"])
        result["negative"] = has_negative
        result["buying_intent"] = has_buying_intent
        result["extracted"] = {
            "budget": best_budget,
            "platform": best_platform,
            "niche": best_niche,
            "timeline": best_timeline,
        }
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_budget(text: str) -> Optional[str]:
        for pattern, label in _BUDGET_PATTERNS:
            if pattern.search(text):
                return label
        return None

    @staticmethod
    def _detect_platform(text: str) -> Optional[str]:
        lower = text.lower()
        found: list[str] = []
        for key, keywords in _PLATFORM_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                found.append(key)
        if len(found) > 1:
            return "multiple"
        if found:
            return found[0]
        return None

    @staticmethod
    def _detect_niche(text: str) -> Optional[str]:
        lower = text.lower()
        for key, keywords in _NICHE_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return key
        return None

    @staticmethod
    def _detect_timeline(text: str) -> Optional[str]:
        for pattern, label in _URGENCY_PATTERNS:
            if pattern.search(text):
                return label
        return None
