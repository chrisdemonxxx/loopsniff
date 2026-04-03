"""AI Compliance Checker — regex-based first pass + LLM-powered deep review."""

import json
import logging
import re
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.ai.llm_client import call_llm

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ComplianceCheckRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Ad creative text to check")
    platform: str = Field("all", description="Target platform: meta, google, tiktok, or all")


class Violation(BaseModel):
    rule: str
    severity: str  # critical, high, medium, low
    category: str
    message: str
    matched: str | None = None


class ComplianceCheckResponse(BaseModel):
    score: int = Field(..., ge=0, le=100)
    platform: str
    violations: list[Violation]
    suggestions: list[str]
    summary: str


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

SEVERITY_WEIGHTS = {"critical": 25, "high": 15, "medium": 8, "low": 3}

PROHIBITED_CONTENT: list[dict] = [
    {
        "pattern": r"\b(guaranteed?\s+(results?|income|returns?|profit))\b",
        "rule": "no_guaranteed_results",
        "severity": "critical",
        "category": "claims_without_evidence",
        "message": "Guarantee claims are prohibited on all major ad platforms.",
    },
    {
        "pattern": r"\b(get\s+rich\s+quick|make\s+money\s+fast|easy\s+money)\b",
        "rule": "no_get_rich_quick",
        "severity": "critical",
        "category": "prohibited_content",
        "message": "Get-rich-quick language is prohibited.",
    },
    {
        "pattern": r"\b(miracle|cure[sd]?\s+(cancer|diabetes|disease)|100%\s+effective)\b",
        "rule": "no_miracle_health_claims",
        "severity": "critical",
        "category": "prohibited_content",
        "message": "Miracle or unsubstantiated health claims are prohibited.",
    },
    {
        "pattern": r"\b(before\s+and\s+after|lose\s+\d+\s*(lbs?|kg|pounds?|kilos?)\s+in)\b",
        "rule": "no_unrealistic_body_claims",
        "severity": "high",
        "category": "restricted_content",
        "message": "Before/after or rapid weight-loss claims require substantiation.",
    },
    {
        "pattern": r"\b(fuck|shit|damn|ass|bitch|crap)\b",
        "rule": "no_profanity",
        "severity": "high",
        "category": "prohibited_content",
        "message": "Profanity is not allowed in ad creatives.",
    },
    {
        "pattern": r"\b(click\s*bait|you\s+won't\s+believe|shocking|doctors?\s+hate)\b",
        "rule": "no_clickbait",
        "severity": "medium",
        "category": "prohibited_content",
        "message": "Clickbait language violates ad policies.",
    },
    {
        "pattern": r"\b(buy\s+now\s+or\s+miss\s+out|last\s+chance\s+ever|act\s+now\s+or\s+lose)\b",
        "rule": "no_false_urgency",
        "severity": "medium",
        "category": "prohibited_content",
        "message": "False or exaggerated urgency claims are prohibited.",
    },
    {
        "pattern": r"\b(cbd|cannabis|marijuana|weed|thc)\b",
        "rule": "restricted_substance",
        "severity": "high",
        "category": "restricted_content",
        "message": "Cannabis/CBD products are restricted on most ad platforms.",
    },
    {
        "pattern": r"\b(cryptocurrency|crypto\s+trading|bitcoin\s+invest|forex\s+signal)\b",
        "rule": "restricted_financial",
        "severity": "high",
        "category": "restricted_content",
        "message": "Crypto/forex advertising is restricted and requires prior authorization.",
    },
    {
        "pattern": r"\b(gambling|casino|betting|poker|slot\s*machine)\b",
        "rule": "restricted_gambling",
        "severity": "high",
        "category": "restricted_content",
        "message": "Gambling ads are restricted and require pre-approval.",
    },
    {
        "pattern": r"\b(supplements?\s+that\s+(burn|melt)|fat\s+burner|weight\s+loss\s+pill)\b",
        "rule": "restricted_supplements",
        "severity": "high",
        "category": "restricted_content",
        "message": "Supplement claims must be substantiated and comply with health policies.",
    },
    {
        "pattern": r"\b(earn\s+\$\d{3,}|make\s+\$\d{3,}|\$\d{4,}\s*(per|a)\s*(day|week|month|hour))\b",
        "rule": "no_income_claims",
        "severity": "critical",
        "category": "claims_without_evidence",
        "message": "Specific income claims require substantiation and disclaimers.",
    },
    {
        "pattern": r"\b(FDA\s+approved|clinically\s+proven|scientifically\s+proven)\b",
        "rule": "unsubstantiated_authority",
        "severity": "high",
        "category": "claims_without_evidence",
        "message": "Authority claims (FDA approved, clinically proven) require documentation.",
    },
    {
        "pattern": r"\b(#1|number\s+one|best\s+in\s+the\s+world|world'?s?\s+best)\b",
        "rule": "superlative_claims",
        "severity": "medium",
        "category": "claims_without_evidence",
        "message": "Superlative claims (#1, best in the world) require third-party verification.",
    },
]

FORMATTING_RULES: list[dict] = [
    {
        "check": "excessive_caps",
        "severity": "medium",
        "category": "formatting_issues",
        "message": "Excessive use of ALL CAPS can trigger policy flags.",
    },
    {
        "check": "excessive_punctuation",
        "severity": "low",
        "category": "formatting_issues",
        "message": "Excessive punctuation (!!!, ???) may reduce ad approval rates.",
    },
    {
        "check": "excessive_emojis",
        "severity": "low",
        "category": "formatting_issues",
        "message": "Too many emojis can reduce ad quality score.",
    },
    {
        "check": "too_long",
        "severity": "low",
        "category": "formatting_issues",
        "message": "Ad text is very long. Consider shorter copy for better engagement.",
    },
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def _check_formatting(text: str) -> list[Violation]:
    violations: list[Violation] = []
    words = text.split()
    cap_words = [w for w in words if w.isupper() and len(w) > 2]
    if len(cap_words) > max(3, len(words) * 0.3):
        violations.append(Violation(
            rule="excessive_caps", severity="medium",
            category="formatting_issues",
            message="Excessive use of ALL CAPS can trigger policy flags.",
            matched=", ".join(cap_words[:5]),
        ))

    if re.search(r"[!?]{3,}", text):
        violations.append(Violation(
            rule="excessive_punctuation", severity="low",
            category="formatting_issues",
            message="Excessive punctuation (!!!, ???) may reduce ad approval rates.",
            matched=re.findall(r"[!?]{3,}", text)[0],
        ))

    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF\U00002600-\U000026FF]+",
        re.UNICODE,
    )
    emojis = emoji_pattern.findall(text)
    total_emojis = sum(len(e) for e in emojis)
    if total_emojis > 5:
        violations.append(Violation(
            rule="excessive_emojis", severity="low",
            category="formatting_issues",
            message="Too many emojis can reduce ad quality score.",
            matched=f"{total_emojis} emojis found",
        ))

    if len(text) > 3000:
        violations.append(Violation(
            rule="too_long", severity="low",
            category="formatting_issues",
            message="Ad text is very long. Consider shorter copy for better engagement.",
            matched=f"{len(text)} characters",
        ))

    return violations


def _regex_compliance_check(text: str, platform: str) -> ComplianceCheckResponse:
    """First-pass regex-only compliance scan (original logic)."""
    violations: list[Violation] = []

    for rule in PROHIBITED_CONTENT:
        matches = re.findall(rule["pattern"], text, re.IGNORECASE)
        if matches:
            matched_str = matches[0] if isinstance(matches[0], str) else matches[0][0]
            violations.append(Violation(
                rule=rule["rule"],
                severity=rule["severity"],
                category=rule["category"],
                message=rule["message"],
                matched=matched_str,
            ))

    violations.extend(_check_formatting(text))

    total_penalty = sum(SEVERITY_WEIGHTS.get(v.severity, 5) for v in violations)
    score = max(0, 100 - total_penalty)

    suggestions: list[str] = []
    categories_hit = {v.category for v in violations}
    if "claims_without_evidence" in categories_hit:
        suggestions.append("Add disclaimers or remove unsubstantiated claims.")
    if "prohibited_content" in categories_hit:
        suggestions.append("Remove prohibited language or content to avoid ad rejection.")
    if "restricted_content" in categories_hit:
        suggestions.append("Ensure you have platform pre-approval for restricted categories.")
    if "formatting_issues" in categories_hit:
        suggestions.append("Clean up formatting to improve ad quality score and approval rate.")
    if not violations:
        suggestions.append("Your ad copy looks compliant! Consider A/B testing variations.")

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    violations.sort(key=lambda v: severity_order.get(v.severity, 4))

    if score >= 80:
        summary = "Ad copy is largely compliant with minor issues."
    elif score >= 50:
        summary = "Ad copy has several policy concerns that should be addressed."
    else:
        summary = "Ad copy has critical policy violations and is likely to be rejected."

    return ComplianceCheckResponse(
        score=score,
        platform=platform,
        violations=violations,
        suggestions=suggestions,
        summary=summary,
    )


_COMPLIANCE_SYSTEM_PROMPT = (
    "You are an ad compliance reviewer. Analyze this ad copy for policy violations "
    "(Meta, Google, TikTok ad policies). Return ONLY valid JSON with this schema: "
    '{"compliant": bool, "issues": [{"rule": str, "severity": "critical"|"high"|"medium"|"low", '
    '"description": str}], "suggestions": [str]}'
)


async def run_compliance_check(text: str, platform: str) -> ComplianceCheckResponse:
    """Run regex first-pass then enhance with LLM deep review."""
    regex_result = _regex_compliance_check(text, platform)

    # Build LLM prompt with ad text + regex findings
    regex_summary = ""
    if regex_result.violations:
        findings = [f"- [{v.severity}] {v.rule}: {v.message}" for v in regex_result.violations]
        regex_summary = "\n\nRegex pre-scan findings:\n" + "\n".join(findings)

    prompt = (
        f"Platform: {platform}\n\n"
        f"Ad copy to review:\n\"\"\"\n{text}\n\"\"\""
        f"{regex_summary}\n\n"
        "Identify any additional policy violations the regex scan may have missed. "
        "Return JSON only."
    )

    llm_response = await call_llm(prompt, system_prompt=_COMPLIANCE_SYSTEM_PROMPT, temperature=0.3)
    if llm_response is None:
        return regex_result

    try:
        # Strip markdown code fences if present
        cleaned = llm_response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        llm_data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"LLM compliance response not valid JSON: {exc}")
        return regex_result

    # Merge LLM issues with regex violations (deduplicate by rule name)
    existing_rules = {v.rule for v in regex_result.violations}
    llm_issues = llm_data.get("issues", [])
    for issue in llm_issues:
        rule_name = issue.get("rule", "llm_finding")
        if rule_name not in existing_rules:
            regex_result.violations.append(Violation(
                rule=rule_name,
                severity=issue.get("severity", "medium"),
                category="llm_review",
                message=issue.get("description", "LLM-identified policy issue."),
            ))
            existing_rules.add(rule_name)

    # Merge LLM suggestions
    existing_suggestions = set(regex_result.suggestions)
    for suggestion in llm_data.get("suggestions", []):
        if suggestion and suggestion not in existing_suggestions:
            regex_result.suggestions.append(suggestion)
            existing_suggestions.add(suggestion)

    # Recalculate score with merged violations
    total_penalty = sum(SEVERITY_WEIGHTS.get(v.severity, 5) for v in regex_result.violations)
    regex_result.score = max(0, 100 - total_penalty)

    # Re-sort and update summary
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    regex_result.violations.sort(key=lambda v: severity_order.get(v.severity, 4))

    if regex_result.score >= 80:
        regex_result.summary = "Ad copy is largely compliant with minor issues."
    elif regex_result.score >= 50:
        regex_result.summary = "Ad copy has several policy concerns that should be addressed."
    else:
        regex_result.summary = "Ad copy has critical policy violations and is likely to be rejected."

    return regex_result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/compliance/check", response_model=ComplianceCheckResponse)
async def check_compliance(
    req: ComplianceCheckRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyze ad creative text for policy violations across Meta, Google, and TikTok."""
    return await run_compliance_check(req.text, req.platform)
