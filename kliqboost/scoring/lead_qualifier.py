"""Lead qualification pipeline.

Moves leads through funnel stages and recommends the next action the
outreach engine should take for each lead.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .bant_scorer import BANTScorer

log = logging.getLogger(__name__)

# Try importing shared models; fall back to lightweight stubs so the module
# can be loaded and tested before the full outreach package is wired up.
try:
    from ..models import Lead, Account, Message  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    Lead = None  # type: ignore[assignment,misc]
    Account = None  # type: ignore[assignment,misc]
    Message = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STAGES = [
    "new",
    "contacted",
    "replied",
    "engaged",
    "qualified",
    "hot",
    "customer",
    "dead",
]

# Actions the caller should take after qualification
ACTION_ESCALATE = "escalate"
ACTION_FOLLOWUP = "followup"
ACTION_NURTURE = "nurture"
ACTION_DROP = "drop"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# LeadQualifier
# ---------------------------------------------------------------------------


class LeadQualifier:
    """Pipeline to qualify leads through stages."""

    STAGES = STAGES

    def __init__(self, scorer: Optional[BANTScorer] = None):
        self.scorer = scorer or BANTScorer()

    # ------------------------------------------------------------------
    # Core qualification
    # ------------------------------------------------------------------

    async def qualify(
        self,
        lead_data: Dict[str, Any],
        conversation: Optional[List[str]] = None,
        new_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the qualification pipeline on a lead.

        Parameters
        ----------
        lead_data:
            Dict with at least ``username`` and ``stage`` keys.  Mutated
            in-place when a stage transition occurs.
        conversation:
            Full conversation history (list of message strings from the lead).
        new_message:
            The latest inbound message, if any.

        Returns
        -------
        dict with keys ``action``, ``score``, ``stage``, ``reason``.
        """
        username = lead_data.get("username", "unknown")
        current_stage = lead_data.get("stage", "new")

        # Build message list for scoring
        msgs: List[str] = list(conversation or [])
        if new_message:
            msgs.append(new_message)

        # Score
        if msgs:
            score = self.scorer.score_from_conversation(msgs)
        else:
            score = self.scorer.score()

        total = score["total"]
        negative = score.get("negative", False)

        # Determine action + stage transition
        action, new_stage, reason = self._decide(current_stage, total, negative, bool(new_message))

        if new_stage != current_stage:
            lead_data["stage"] = new_stage
            lead_data["stage_changed_at"] = _now().isoformat()
            log.info(
                "Lead @%s stage %s → %s (score=%d, action=%s)",
                username, current_stage, new_stage, total, action,
            )

        return {
            "action": action,
            "score": score,
            "stage": new_stage,
            "previous_stage": current_stage,
            "reason": reason,
        }

    # ------------------------------------------------------------------

    def _decide(
        self, stage: str, total: int, negative: bool, has_new_msg: bool
    ) -> tuple[str, str, str]:
        """Return (action, new_stage, reason)."""

        # Hard disqualification
        if negative:
            return ACTION_DROP, "dead", "Negative signal detected"

        # Hot threshold
        if total >= 75:
            new_stage = "hot" if stage not in ("customer",) else stage
            return ACTION_ESCALATE, new_stage, f"BANT score {total} ≥ 75 — hot lead"

        # Warm — keep nurturing / qualify
        if total >= 50:
            if stage in ("new", "contacted"):
                new_stage = "replied" if has_new_msg else stage
            elif stage == "replied":
                new_stage = "engaged"
            elif stage == "engaged":
                new_stage = "qualified"
            else:
                new_stage = stage
            return ACTION_FOLLOWUP, new_stage, f"BANT score {total} — warm, continue engaging"

        # Cool — nurture
        if total >= 25:
            if stage == "new" and has_new_msg:
                new_stage = "replied"
            else:
                new_stage = stage
            return ACTION_NURTURE, new_stage, f"BANT score {total} — cool, nurture"

        # Cold — low priority follow-up
        return ACTION_NURTURE, stage, f"BANT score {total} — cold, low-priority nurture"

    # ------------------------------------------------------------------
    # Funnel analytics
    # ------------------------------------------------------------------

    async def get_pipeline_stats(self, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Return funnel metrics from a list of lead dicts.

        Returns per-stage counts and simple conversion rates between
        adjacent stages.
        """
        counts: Dict[str, int] = {s: 0 for s in STAGES}
        for ld in leads:
            stage = ld.get("stage", "new")
            if stage in counts:
                counts[stage] += 1
            else:
                counts[stage] = counts.get(stage, 0) + 1

        total = len(leads) or 1
        conversions: Dict[str, float] = {}
        for i in range(len(STAGES) - 1):
            prev, cur = STAGES[i], STAGES[i + 1]
            prev_count = counts.get(prev, 0)
            if prev_count:
                conversions[f"{prev}_to_{cur}"] = round(counts.get(cur, 0) / prev_count * 100, 1)
            else:
                conversions[f"{prev}_to_{cur}"] = 0.0

        return {
            "total_leads": len(leads),
            "per_stage": counts,
            "conversion_rates": conversions,
            "hot_leads": counts.get("hot", 0),
            "customers": counts.get("customer", 0),
        }
