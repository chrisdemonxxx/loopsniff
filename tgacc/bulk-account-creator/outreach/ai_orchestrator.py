"""AI-driven campaign orchestrator for Telegram bulk outreach.

Monitors performance and auto-tunes parameters to maximise delivery rate
while minimising burn rate.  Rule-based mid-campaign analysis keeps
latency low; LLM is only invoked for post-campaign reports.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import aiohttp
from loguru import logger

# ── Ollama Cloud settings (mirror ai_responder.py) ──────────────────────
OLLAMA_URL = "https://ollama.com/v1/chat/completions"
OLLAMA_API_KEY = os.getenv(
    "OLLAMA_API_KEY",
    "baeb6fd660e34f15bab48271e676cf74.UHEnKkigGk5x3N_M4TEXLx4t",
)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2:1t")


# ── Data classes ─────────────────────────────────────────────────────────


@dataclass
class CampaignInsight:
    recommendation: str
    confidence: float  # 0.0 – 1.0
    parameter: str  # config key to adjust
    current_value: float
    suggested_value: float
    reason: str


@dataclass
class PerformanceSnapshot:
    timestamp: str
    messages_sent: int
    messages_failed: int
    sessions_used: int
    sessions_burned: int
    burn_rate: float
    delivery_rate: float
    avg_messages_per_session: float
    targets_skipped: int


# ── Orchestrator ─────────────────────────────────────────────────────────


class AICampaignOrchestrator:
    """AI-driven campaign optimiser.

    1. **Pre-campaign** – analyse targets & recommend settings.
    2. **Mid-campaign** – monitor metrics & auto-adjust delays / batch sizes.
    3. **Post-campaign** – generate insights report via LLM.
    """

    def __init__(
        self,
        ollama_url: str | None = None,
        ollama_model: str | None = None,
    ):
        self.ollama_url = ollama_url or OLLAMA_URL
        self.ollama_model = ollama_model or OLLAMA_MODEL
        self._snapshots: list[PerformanceSnapshot] = []
        self._insights: list[CampaignInsight] = []

    # ------------------------------------------------------------------
    # Pre-campaign
    # ------------------------------------------------------------------

    async def analyze_pre_campaign(
        self,
        session_count: int,
        target_count: int,
        niche: str,
        proxy_type: str,
    ) -> dict:
        """Return recommended config overrides (rule-based, no LLM)."""

        recommendations: dict = {}

        # Quota: sessions × avg_msgs (3) × safety (0.8)
        estimated_max = int(session_count * 3 * 0.8)
        recommendations["daily_quota"] = min(estimated_max, target_count)

        # Batch size / delay based on proxy type
        if proxy_type == "mobile":
            recommendations["micro_batch_max"] = 5
            recommendations["inter_message_delay_base"] = 20.0
        elif proxy_type == "residential":
            recommendations["micro_batch_max"] = 3
            recommendations["inter_message_delay_base"] = 30.0
        else:  # datacenter — very conservative
            recommendations["micro_batch_max"] = 2
            recommendations["inter_message_delay_base"] = 45.0

        # Message style by niche
        niche_styles = {
            "crypto": "casual",
            "trading": "professional",
            "forex": "professional",
            "affiliate": "casual",
            "saas": "professional",
            "web3": "casual",
            "nft": "casual",
            "defi": "casual",
        }
        recommendations["message_style"] = niche_styles.get(
            niche.lower(), "casual"
        )

        # Pre-generate buffer: 1.5× quota
        recommendations["pre_generate_count"] = int(
            recommendations["daily_quota"] * 1.5
        )

        logger.info(
            f"Pre-campaign analysis: {json.dumps(recommendations, indent=2)}"
        )
        return recommendations

    # ------------------------------------------------------------------
    # Snapshot recording
    # ------------------------------------------------------------------

    def record_snapshot(self, stats) -> PerformanceSnapshot:
        """Record a performance snapshot from *CampaignStats*.

        Should be called periodically (e.g. every 5 sessions).
        """
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            messages_sent=stats.messages_sent,
            messages_failed=stats.messages_failed,
            sessions_used=stats.sessions_used,
            sessions_burned=stats.sessions_burned,
            burn_rate=stats.burn_rate,
            delivery_rate=stats.delivery_rate,
            avg_messages_per_session=(
                stats.messages_sent / max(stats.sessions_used, 1)
            ),
            targets_skipped=stats.targets_skipped,
        )
        self._snapshots.append(snapshot)
        return snapshot

    # ------------------------------------------------------------------
    # Mid-campaign analysis (rule-based — fast, no LLM)
    # ------------------------------------------------------------------

    def analyze_mid_campaign(
        self, current_config: dict
    ) -> list[CampaignInsight]:
        """Auto-tune parameters based on performance trends.

        * High burn rate  → increase delays, decrease batch size
        * Low burn rate   → cautiously decrease delays
        * High skip rate  → suggest better target filtering
        * Low delivery    → suggest different message style
        """
        if len(self._snapshots) < 2:
            return []

        insights: list[CampaignInsight] = []
        latest = self._snapshots[-1]
        prev = self._snapshots[-2]

        delay_base = current_config.get("inter_message_delay_base", 25.0)
        batch_max = current_config.get("micro_batch_max", 5)

        # ── Burn rate ────────────────────────────────────────────────
        if latest.burn_rate > 0.9:
            insights.append(
                CampaignInsight(
                    recommendation="INCREASE delays — burn rate critically high",
                    confidence=0.95,
                    parameter="inter_message_delay_base",
                    current_value=delay_base,
                    suggested_value=delay_base * 1.5,
                    reason=f"Burn rate {latest.burn_rate:.0%} is critically high",
                )
            )
            insights.append(
                CampaignInsight(
                    recommendation="DECREASE batch size — reduce exposure per session",
                    confidence=0.9,
                    parameter="micro_batch_max",
                    current_value=batch_max,
                    suggested_value=max(1, batch_max - 2),
                    reason="High burn rate suggests sessions are being detected early",
                )
            )
        elif latest.burn_rate > 0.7 and latest.burn_rate > prev.burn_rate:
            insights.append(
                CampaignInsight(
                    recommendation="INCREASE delays — burn rate trending up",
                    confidence=0.8,
                    parameter="inter_message_delay_base",
                    current_value=delay_base,
                    suggested_value=delay_base * 1.2,
                    reason=(
                        f"Burn rate increasing: "
                        f"{prev.burn_rate:.0%} → {latest.burn_rate:.0%}"
                    ),
                )
            )
        elif latest.burn_rate < 0.3 and len(self._snapshots) >= 3:
            insights.append(
                CampaignInsight(
                    recommendation="Can cautiously DECREASE delays — burn rate is low",
                    confidence=0.6,
                    parameter="inter_message_delay_base",
                    current_value=delay_base,
                    suggested_value=max(15.0, delay_base * 0.85),
                    reason=f"Burn rate {latest.burn_rate:.0%} is healthy",
                )
            )

        # ── Skip rate ────────────────────────────────────────────────
        total_attempts = (
            latest.messages_sent
            + latest.messages_failed
            + latest.targets_skipped
        )
        skip_rate = latest.targets_skipped / max(total_attempts, 1)

        if skip_rate > 0.3:
            insights.append(
                CampaignInsight(
                    recommendation="HIGH skip rate — improve target quality",
                    confidence=0.85,
                    parameter="target_filters",
                    current_value=skip_rate,
                    suggested_value=0.1,
                    reason=(
                        f"Skip rate {skip_rate:.0%}: many targets have "
                        "privacy restrictions or are deactivated"
                    ),
                )
            )

        # ── Delivery rate ────────────────────────────────────────────
        if latest.delivery_rate < 0.5 and latest.messages_sent > 20:
            insights.append(
                CampaignInsight(
                    recommendation=(
                        "LOW delivery rate — consider changing message "
                        "style or template"
                    ),
                    confidence=0.7,
                    parameter="message_style",
                    current_value=0,
                    suggested_value=0,
                    reason=(
                        f"Only {latest.delivery_rate:.0%} of messages "
                        "delivered successfully"
                    ),
                )
            )

        # ── Avg messages per session ─────────────────────────────────
        if latest.avg_messages_per_session < 1.5 and latest.sessions_used > 10:
            insights.append(
                CampaignInsight(
                    recommendation=(
                        "Sessions burning before completing batches — "
                        "increase initial delays"
                    ),
                    confidence=0.75,
                    parameter="inter_message_delay_base",
                    current_value=delay_base,
                    suggested_value=delay_base * 1.3,
                    reason=(
                        f"Avg {latest.avg_messages_per_session:.1f} "
                        "msgs/session (target: 3+)"
                    ),
                )
            )

        self._insights.extend(insights)

        for insight in insights:
            logger.info(
                f"🧠 AI Insight [{insight.confidence:.0%}]: "
                f"{insight.recommendation}"
            )

        return insights

    # ------------------------------------------------------------------
    # Apply insights
    # ------------------------------------------------------------------

    def apply_insights(
        self,
        config: dict,
        insights: list[CampaignInsight],
        auto_apply_threshold: float = 0.8,
    ) -> dict:
        """Apply high-confidence insights to *config*.

        Only auto-applies insights whose confidence ≥ *auto_apply_threshold*.
        Returns a **new** dict (original is not mutated).
        """
        modified = dict(config)
        applied: list[str] = []

        for insight in insights:
            if insight.confidence >= auto_apply_threshold:
                if insight.parameter in modified and isinstance(
                    insight.suggested_value, (int, float)
                ):
                    old = modified[insight.parameter]
                    modified[insight.parameter] = insight.suggested_value
                    applied.append(
                        f"{insight.parameter}: {old} → {insight.suggested_value}"
                    )

        if applied:
            logger.info(
                f"🧠 Auto-applied {len(applied)} adjustments: "
                f"{', '.join(applied)}"
            )

        return modified

    # ------------------------------------------------------------------
    # Post-campaign report (LLM)
    # ------------------------------------------------------------------

    async def generate_post_campaign_report(self, stats) -> str:
        """Generate an actionable post-campaign report via Ollama Cloud."""

        if not self._snapshots:
            return "No performance data recorded."

        summary = {
            "total_messages_sent": stats.messages_sent,
            "total_messages_failed": stats.messages_failed,
            "total_sessions_used": stats.sessions_used,
            "final_burn_rate": f"{stats.burn_rate:.0%}",
            "final_delivery_rate": f"{stats.delivery_rate:.0%}",
            "targets_skipped": stats.targets_skipped,
            "errors": stats.errors[:10],
            "duration": f"{stats.started_at} to {stats.completed_at}",
            "performance_trend": [
                {
                    "timestamp": s.timestamp,
                    "burn_rate": f"{s.burn_rate:.0%}",
                    "delivery_rate": f"{s.delivery_rate:.0%}",
                    "avg_msgs_per_session": f"{s.avg_messages_per_session:.1f}",
                }
                for s in self._snapshots[-10:]
            ],
            "auto_adjustments_made": len(self._insights),
        }

        prompt = (
            "Analyze this Telegram outreach campaign performance and "
            "provide actionable insights:\n\n"
            f"{json.dumps(summary, indent=2)}\n\n"
            "Provide:\n"
            "1. Overall campaign grade (A-F)\n"
            "2. What went well\n"
            "3. What went wrong\n"
            "4. 3-5 specific, actionable recommendations for the next campaign\n"
            "5. Optimal settings to try next time (batch_size, delays, style)\n\n"
            "Be concise and practical. Format for Telegram (plain text, emoji headers)."
        )

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.ollama_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a Telegram outreach campaign analyst.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                }
                headers = {
                    "Authorization": f"Bearer {OLLAMA_API_KEY}",
                    "Content-Type": "application/json",
                }

                async with session.post(
                    self.ollama_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return (
                            data.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "Analysis unavailable")
                        )
                    logger.error(f"LLM API error: {resp.status}")
                    return self._generate_basic_report(stats)

        except Exception as e:
            logger.error(f"Post-campaign analysis failed: {e}")
            return self._generate_basic_report(stats)

    # ------------------------------------------------------------------
    # Fallback report (no LLM)
    # ------------------------------------------------------------------

    def _generate_basic_report(self, stats) -> str:
        if stats.delivery_rate > 0.8:
            grade = "A"
        elif stats.delivery_rate > 0.6:
            grade = "B"
        elif stats.delivery_rate > 0.4:
            grade = "C"
        else:
            grade = "D"

        burn_advice = (
            "Increase inter_message_delay to 35s"
            if stats.burn_rate > 0.7
            else "Current delays seem appropriate"
        )
        batch_advice = (
            "Reduce batch_max to 2"
            if stats.burn_rate > 0.8
            else "Batch size is fine"
        )
        target_advice = (
            "Improve target filtering"
            if stats.targets_skipped > stats.messages_sent * 0.3
            else "Target quality is acceptable"
        )
        delivery_note = (
            "✅ Good delivery rate!"
            if stats.delivery_rate > 0.6
            else "⚠️ Low delivery rate — consider increasing delays"
        )
        burn_note = (
            "✅ Acceptable burn rate"
            if stats.burn_rate < 0.5
            else "⚠️ High burn rate — reduce batch size or increase delays"
        )

        return (
            f"📊 Campaign Analysis ({grade})\n"
            f"{'=' * 30}\n\n"
            f"📈 Delivery Rate: {stats.delivery_rate:.0%}\n"
            f"🔥 Burn Rate: {stats.burn_rate:.0%}\n"
            f"📱 Sessions: {stats.sessions_used} used, "
            f"{stats.sessions_burned} burned\n"
            f"✉️ Messages: {stats.messages_sent} sent, "
            f"{stats.messages_failed} failed\n\n"
            f"{delivery_note}\n"
            f"{burn_note}\n\n"
            f"🔧 Suggestions:\n"
            f"- {burn_advice}\n"
            f"- {batch_advice}\n"
            f"- {target_advice}\n"
        )

    # ------------------------------------------------------------------
    # Accessors / reset
    # ------------------------------------------------------------------

    def get_all_insights(self) -> list[CampaignInsight]:
        """Return every insight generated during the campaign."""
        return self._insights

    def reset(self):
        """Clear state for a new campaign."""
        self._snapshots.clear()
        self._insights.clear()


# ── Demo ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dataclasses import dataclass as _dc

    @_dc
    class _FakeStats:
        messages_sent: int = 0
        messages_failed: int = 0
        sessions_used: int = 0
        sessions_burned: int = 0
        burn_rate: float = 0.0
        delivery_rate: float = 0.0
        targets_skipped: int = 0
        errors: list = field(default_factory=list)
        started_at: str = ""
        completed_at: str = ""

    async def _demo():
        orch = AICampaignOrchestrator()

        # 1. Pre-campaign
        recs = await orch.analyze_pre_campaign(
            session_count=50,
            target_count=200,
            niche="crypto",
            proxy_type="residential",
        )
        print("━" * 50)
        print("PRE-CAMPAIGN RECOMMENDATIONS")
        print(json.dumps(recs, indent=2))

        # 2. Simulate mid-campaign snapshots
        config = {
            "inter_message_delay_base": 25.0,
            "micro_batch_max": 4,
        }

        stats_a = _FakeStats(
            messages_sent=30,
            messages_failed=5,
            sessions_used=12,
            sessions_burned=3,
            burn_rate=0.25,
            delivery_rate=0.85,
            targets_skipped=4,
        )
        orch.record_snapshot(stats_a)

        stats_b = _FakeStats(
            messages_sent=80,
            messages_failed=15,
            sessions_used=30,
            sessions_burned=25,
            burn_rate=0.83,
            delivery_rate=0.72,
            targets_skipped=12,
        )
        orch.record_snapshot(stats_b)

        insights = orch.analyze_mid_campaign(config)
        print("\n" + "━" * 50)
        print("MID-CAMPAIGN INSIGHTS")
        for ins in insights:
            print(
                f"  [{ins.confidence:.0%}] {ins.recommendation}\n"
                f"        {ins.parameter}: {ins.current_value} → "
                f"{ins.suggested_value}\n"
                f"        Reason: {ins.reason}"
            )

        # 3. Apply insights
        new_config = orch.apply_insights(config, insights)
        print("\n" + "━" * 50)
        print("UPDATED CONFIG")
        print(json.dumps(new_config, indent=2))

        # 4. Fallback report
        stats_final = _FakeStats(
            messages_sent=120,
            messages_failed=20,
            sessions_used=50,
            sessions_burned=35,
            burn_rate=0.70,
            delivery_rate=0.75,
            targets_skipped=18,
            errors=["FloodWaitError", "UserPrivacyRestrictedError"],
            started_at="2025-01-01T10:00:00",
            completed_at="2025-01-01T14:30:00",
        )
        report = orch._generate_basic_report(stats_final)
        print("\n" + "━" * 50)
        print("POST-CAMPAIGN REPORT (fallback)")
        print(report)

    asyncio.run(_demo())
