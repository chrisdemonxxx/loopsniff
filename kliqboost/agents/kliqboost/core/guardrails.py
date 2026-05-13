"""Re-export bridge.guardrails for in-process use by core.agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

try:
    from bridge.guardrails import (  # type: ignore
        evaluate_inbound_text,
        evaluate_outbound_text,
        validate_invite_urls,
    )
except Exception as exc:  # pragma: no cover
    log.warning("bridge.guardrails unavailable, using permissive fallback: %s", exc)

    @dataclass
    class _Decision:
        action: str = "allow"
        rewritten_text: str = ""
        reason: str = ""

    def evaluate_inbound_text(text: str, **_):
        return _Decision()

    def evaluate_outbound_text(text: str, allow_wallets: bool = True, **_):
        return _Decision(action="allow", rewritten_text=text)

    def validate_invite_urls(urls, allowed_domains=("t.me",)):
        return list(urls)


__all__ = ["evaluate_inbound_text", "evaluate_outbound_text", "validate_invite_urls"]
