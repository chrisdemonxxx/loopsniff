"""Commission calculator for AdFlux ad account top-ups."""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)

# ── Commission tiers ────────────────────────────────────────────────────────

BASE_RATES = {
    "basic": 0.10,       # 10% top-up fee
    "pro": 0.08,         # 8% top-up fee
    "enterprise": 0.06,  # 6% top-up fee
}

# Taboola has lower top-up fees
TABOOLA_RATES = {
    "basic": 0.05,       # 5% top-up fee
    "pro": 0.03,         # 3% top-up fee
    "enterprise": 0.02,  # 2% top-up fee
}

HIGH_RISK_SURCHARGE = 0.05

HIGH_RISK_NICHES = frozenset({
    "crypto", "gambling", "nutra", "forex", "trading", "sweepstakes",
})

# Volume discount thresholds (cumulative spend in USD)
VOLUME_DISCOUNTS = [
    (500_000, 0.10),
    (100_000, 0.08),
    (50_000,  0.05),
]

FLOOR_RATE = 0.10  # minimum commission rate


def _get_volume_discount(amount: float) -> float:
    """Return the volume discount percentage for a given spend amount."""
    for threshold, discount in VOLUME_DISCOUNTS:
        if amount >= threshold:
            return discount
    return 0.0


def calculate_topup_cost(
    amount: float,
    plan: str = "starter",
    niche: str = "other",
) -> dict:
    """Calculate the total cost for an ad-account top-up.

    Args:
        amount: Desired ad spend in USD.
        plan: One of 'starter', 'growth', 'enterprise'.
        niche: The advertiser's vertical (used for risk surcharge).

    Returns:
        dict with keys: ad_spend, commission, total, rate_pct
    """
    breakdown = get_commission_breakdown(amount, plan, niche)
    rate = breakdown["effective_rate"]
    commission = round(amount * rate, 2)
    total = round(amount + commission, 2)

    return {
        "ad_spend": amount,
        "commission": commission,
        "total": total,
        "rate_pct": round(rate * 100, 2),
    }


def get_commission_breakdown(
    amount: float,
    plan: str = "starter",
    niche: str = "other",
) -> dict:
    """Return a detailed breakdown of every commission factor.

    Returns:
        dict with keys: base_rate, high_risk, volume_discount,
                        raw_rate, floor_applied, effective_rate,
                        plan, niche, amount
    """
    plan = plan.lower()
    niche = niche.lower()

    base = BASE_RATES.get(plan, BASE_RATES["starter"])
    risk = HIGH_RISK_SURCHARGE if niche in HIGH_RISK_NICHES else 0.0
    vol_disc = _get_volume_discount(amount)

    raw_rate = base + risk - vol_disc
    floor_applied = raw_rate < FLOOR_RATE
    effective = max(raw_rate, FLOOR_RATE)

    return {
        "base_rate": base,
        "high_risk": risk,
        "volume_discount": vol_disc,
        "raw_rate": round(raw_rate, 4),
        "floor_applied": floor_applied,
        "effective_rate": round(effective, 4),
        "plan": plan,
        "niche": niche,
        "amount": amount,
    }
