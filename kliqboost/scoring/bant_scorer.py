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
    "taboola": 20,
    "outbrain": 20,
    "mediago": 18,
    "multiple": 25,
    "unknown": 10,
}

NICHE_SCORES: Dict[str, int] = {
    "crypto": 15,
    "finance": 15,
    "nutra": 12,
    "trading": 12,
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
    (re.compile(r"\$\s*50\s*k|\$\s*50[\s,]*000|50k\+?|100k|200k", re.I), "$50k+"),
    (re.compile(r"\$\s*[1-4]\d\s*k|\$\s*[1-4]\d[\s,]*000|(?:1[0-9]|2[0-9]|3[0-9]|4[0-9])k", re.I), "$10k-$50k"),
    (re.compile(r"\$\s*[5-9]\s*k|\$\s*[5-9][\s,]*000|[5-9]k|\d{4,}/\s*day", re.I), "$5k-$10k"),
    (re.compile(r"\$\s*[1-4]\s*k|\$\s*[1-4][\s,]*000|[1-4]k|\d{3,4}\s*/\s*day", re.I), "$1k-$5k"),
    (re.compile(r"\$\s*\d{2,3}(?!\d)|few hundred|small budget", re.I), "< $1k"),
]

_PLATFORM_KEYWORDS: dict[str, list[str]] = {
    "google": ["google", "google ads", "adwords", "gads", "pmax", "performance max", "gg ", "gg\n", "bsod"],
    "meta": ["meta", "facebook", "fb ads", "instagram", "ig ads", "fb"],
    "taboola": ["taboola"],
    "outbrain": ["outbrain"],
    "mediago": ["mediago", "media go"],
}

_NICHE_KEYWORDS: dict[str, list[str]] = {
    "crypto": ["crypto", "bitcoin", "btc", "defi", "web3", "nft"],
    "finance": ["finance", "forex", "stocks", "insurance", "loans", "fintech"],
    "nutra": ["nutra", "health", "supplement", "weight loss", "diet"],
    "trading": ["trading", "binary", "options", "cfd"],
    "sweepstakes": ["sweepstakes", "sweeps", "giveaway", "contest"],
    "ecommerce": ["ecommerce", "e-commerce", "shopify", "dropship", "store"],
}

_URGENCY_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\basap\b|right now|immediately|urgent|today|\bnow\b|looking to buy|need .{0,10}(now|asap|today|urgently)", re.I), "asap"),
    (re.compile(r"this week|next few days|in a couple days|ready to buy|want to buy|looking for", re.I), "this_week"),
    (re.compile(r"this month|next week|soon|shortly|interested", re.I), "this_month"),
    (re.compile(r"exploring|just looking|researching|maybe|later", re.I), "exploring"),
]

# Negative / disqualification signals
_NEGATIVE_SIGNALS = re.compile(
    r"\bnot interested\b|\bstop\b|\bunsubscribe\b|\bno thanks\b|\bleave me alone\b|\bspam\b",
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

        result = self.score(
            budget=best_budget,
            platform=best_platform,
            niche=best_niche,
            timeline=best_timeline,
        )
        result["negative"] = has_negative
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
