from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


_PROMPT_INJECTION_PATTERNS = (
    r"ignore all previous instructions",
    r"print (your|the) (full )?system prompt",
    r"reveal (admin|internal|hidden)",
    r"show (api key|token|secret|chat id)",
)

_PROHIBITED_INTENT_PATTERNS = (
    r"\bphishing\b",
    r"\bcredential(s)?\b",
    r"\baccount takeover\b",
    r"\bmalware\b",
    r"\bransomware\b",
    r"\bfraud\b",
    r"\bscam\b",
)

_WALLET_PATTERNS = (
    r"\b0x[a-fA-F0-9]{40}\b",  # EVM
    r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b",  # BTC legacy
    r"\bbc1[ac-hj-np-z02-9]{11,71}\b",  # BTC bech32
    r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b",  # TRON
)

_INVITE_URL_RE = re.compile(r"https?://t\.me/[^\s]+", re.I)


@dataclass(frozen=True)
class GuardrailDecision:
    action: str  # allow | safe_rewrite | block_and_escalate
    reason: str
    rewritten_text: str | None = None


def _contains_any(patterns: Iterable[str], text: str) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


def _extract_wallet_like_strings(text: str) -> list[str]:
    out: list[str] = []
    for p in _WALLET_PATTERNS:
        out.extend(re.findall(p, text))
    deduped: list[str] = []
    for token in out:
        if token not in deduped:
            deduped.append(token)
    return deduped


def evaluate_inbound_text(text: str) -> GuardrailDecision:
    normalized = (text or "").strip()
    if not normalized:
        return GuardrailDecision(action="allow", reason="empty")
    # Only check for prompt injection attempts — prohibited intent patterns
    # (phishing, fraud, scam, etc.) are normal business terms in the ad
    # infrastructure context and clients routinely mention their verticals.
    if _contains_any(_PROMPT_INJECTION_PATTERNS, normalized):
        return GuardrailDecision(
            action="block_and_escalate",
            reason="prompt_injection_attempt",
        )
    return GuardrailDecision(action="allow", reason="ok")


def evaluate_outbound_text(
    text: str,
    *,
    approved_wallets: Iterable[str] | None = None,
    allow_wallets: bool = False,
) -> GuardrailDecision:
    normalized = (text or "").strip()
    if not normalized:
        return GuardrailDecision(action="allow", reason="empty")

    # Note: _PROHIBITED_INTENT_PATTERNS check removed from outbound —
    # these words (phishing, fraud, scam, etc.) are normal business terms
    # in the ad infrastructure context and the LLM naturally uses them
    # when discussing client verticals. Inbound check still applies for
    # prompt injection protection.

    wallets = _extract_wallet_like_strings(normalized)
    if wallets and not allow_wallets:
        return GuardrailDecision(
            action="safe_rewrite",
            reason="wallet_not_allowed_in_context",
            rewritten_text="I will share payment instructions in the dedicated payment step only.",
        )

    if wallets and allow_wallets:
        allowed = {w.strip() for w in (approved_wallets or []) if w.strip()}
        if not allowed or any(w not in allowed for w in wallets):
            return GuardrailDecision(
                action="block_and_escalate",
                reason="unapproved_wallet_detected",
            )

    return GuardrailDecision(action="allow", reason="ok")


def validate_invite_urls(urls: Iterable[str], allowed_domains: Iterable[str] | None = None) -> list[str]:
    domains = [d.lower().strip() for d in (allowed_domains or ["t.me"]) if d.strip()]
    out: list[str] = []
    for u in urls:
        candidate = (u or "").strip()
        if not candidate:
            continue
        if not _INVITE_URL_RE.match(candidate):
            continue
        host_ok = any(f"://{d}/" in candidate.lower() or f"://{d}?" in candidate.lower() for d in domains)
        if host_ok and candidate not in out:
            out.append(candidate)
    return out

