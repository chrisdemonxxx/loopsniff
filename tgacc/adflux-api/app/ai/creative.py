"""AI Creative Generator — LLM-powered ad copy generation with template fallback."""

import json
import logging
import random
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
# Schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    product: str = Field(..., min_length=1, max_length=2000, description="Product/service description")
    audience: str = Field("general", max_length=500, description="Target audience")
    tone: str = Field("professional", description="Tone: professional, casual, urgent, luxury")
    platform: str = Field("meta", description="Platform: meta, google, tiktok")
    industry: str = Field("general", description="Industry: ecommerce, saas, finance, health, education, general")


class GenerateResponse(BaseModel):
    headlines: list[str]
    primary_texts: list[str]
    descriptions: list[str]
    cta_suggestions: list[str]
    platform: str
    tone: str


class ImproveRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Existing ad copy to improve")
    platform: str = Field("meta", description="Target platform")


class ImprovementItem(BaseModel):
    category: str
    current_score: str
    suggestion: str


class ImproveResponse(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    improvements: list[ImprovementItem]
    rewritten: str
    tips: list[str]


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

HEADLINE_TEMPLATES: dict[str, list[str]] = {
    "professional": [
        "{action} Your {goal} with {product}",
        "The Smarter Way to {goal}",
        "{product} — Built for {audience}",
        "Trusted by {audience} Worldwide",
        "Achieve {goal} Without the Hassle",
        "Streamline Your {goal} Today",
        "Professional-Grade {product} for {audience}",
    ],
    "casual": [
        "Hey {audience}, Meet {product}!",
        "Your New Favorite Way to {goal} 🚀",
        "{goal}? We Got You.",
        "Stop Struggling — Try {product}",
        "Finally, {goal} Made Easy",
        "Say Goodbye to {pain_point}",
        "{product} = Happy {audience}",
    ],
    "urgent": [
        "Don't Miss Out — {product}",
        "Limited Time: {goal} Starts Now",
        "Act Fast — {product} Won't Last",
        "{audience}: Claim Your {product} Today",
        "Hurry! {goal} Offer Ends Soon",
        "Last Chance to {goal}",
        "Time-Sensitive: {product} for {audience}",
    ],
    "luxury": [
        "Experience Premium {product}",
        "Elevate Your {goal} — {product}",
        "Exclusive {product} for Discerning {audience}",
        "Indulge in World-Class {product}",
        "The Art of {goal}",
        "Refined. Elegant. {product}.",
        "Where Quality Meets {goal}",
    ],
}

PRIMARY_TEXT_TEMPLATES: dict[str, list[str]] = {
    "professional": [
        "{product} helps {audience} {goal} with confidence. Our proven approach delivers consistent results so you can focus on what matters most.",
        "Built for {audience} who demand quality. {product} combines reliability with performance to help you {goal} efficiently.",
        "Discover how leading {audience} are using {product} to {goal}. Join the professionals who trust us for their success.",
    ],
    "casual": [
        "Tired of struggling to {goal}? {product} makes it ridiculously easy. Try it — your future self will thank you! ✌️",
        "We built {product} because {audience} deserve better. Simple, effective, and actually fun to use. Ready to {goal}?",
        "No jargon. No complexity. Just {product} helping {audience} {goal} without the headache. Sound good? 😎",
    ],
    "urgent": [
        "⏰ {audience}, this is your moment. {product} is available now — but not for long. Start your journey to {goal} before it's too late.",
        "Spots are filling up fast! {product} is the fastest way for {audience} to {goal}. Secure your access today.",
        "Every day you wait is a day you could be using {product} to {goal}. {audience} are already seeing results — join them now.",
    ],
    "luxury": [
        "For {audience} who accept nothing less than excellence. {product} represents the pinnacle of quality, designed to help you {goal} with unmatched sophistication.",
        "Meticulously crafted for {audience} who appreciate the finer things. {product} transforms the way you {goal} — elegantly.",
        "Step into a world where {goal} meets artistry. {product} is the luxury choice for discerning {audience}.",
    ],
}

DESCRIPTION_TEMPLATES: dict[str, list[str]] = {
    "professional": [
        "Enterprise-grade {product} designed for {audience}.",
        "Trusted solution to {goal}. Start your free trial.",
        "See why {audience} choose {product} for {goal}.",
    ],
    "casual": [
        "The easiest way for {audience} to {goal}. Try it free!",
        "{product} — because {goal} shouldn't be hard.",
        "Join thousands of happy {audience} today.",
    ],
    "urgent": [
        "Limited offer for {audience}. {goal} starts now!",
        "Don't wait — {product} deal ends soon.",
        "Exclusive access for {audience}. Claim yours!",
    ],
    "luxury": [
        "Premium {product}. Exceptional {goal}.",
        "For {audience} who expect the extraordinary.",
        "Discover the art of {goal} with {product}.",
    ],
}

CTA_OPTIONS: dict[str, list[str]] = {
    "professional": ["Get Started", "Request a Demo", "Learn More", "Start Free Trial", "Contact Us"],
    "casual": ["Try It Free", "Sign Me Up!", "Let's Go!", "Get Started", "Check It Out"],
    "urgent": ["Claim Now", "Get It Before It's Gone", "Start Today", "Act Now", "Don't Miss Out"],
    "luxury": ["Discover More", "Experience Now", "Explore Collection", "Book a Consultation", "Request Access"],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_keywords(product: str) -> dict[str, str]:
    """Derive template variables from the product description."""
    words = product.split()
    short_product = " ".join(words[:4]) if len(words) > 4 else product
    verbs = ["grow", "boost", "improve", "scale", "achieve", "optimize", "increase", "build"]
    goals = ["growth", "results", "performance", "success", "efficiency", "engagement"]
    pain_points = ["wasted time", "low results", "complexity", "high costs"]
    return {
        "product": short_product.title(),
        "goal": random.choice(goals),
        "action": random.choice(verbs).title(),
        "pain_point": random.choice(pain_points),
    }


def _fill(template: str, variables: dict[str, str]) -> str:
    try:
        return template.format(**variables)
    except KeyError:
        return template


def _generate_from_templates(req: GenerateRequest) -> GenerateResponse:
    """Fallback: generate ad copy from pre-built templates."""
    tone = req.tone if req.tone in HEADLINE_TEMPLATES else "professional"
    kw = _extract_keywords(req.product)
    kw["audience"] = req.audience.title() if req.audience != "general" else "Businesses"

    headlines_pool = HEADLINE_TEMPLATES[tone]
    primary_pool = PRIMARY_TEXT_TEMPLATES[tone]
    desc_pool = DESCRIPTION_TEMPLATES[tone]

    random.shuffle(headlines_pool)
    headlines = [_fill(t, kw) for t in headlines_pool[:5]]
    primary_texts = [_fill(t, kw) for t in primary_pool[:3]]
    descriptions = [_fill(t, kw) for t in desc_pool[:3]]
    ctas = CTA_OPTIONS.get(tone, CTA_OPTIONS["professional"])[:5]

    return GenerateResponse(
        headlines=headlines,
        primary_texts=primary_texts,
        descriptions=descriptions,
        cta_suggestions=ctas,
        platform=req.platform,
        tone=tone,
    )


_CREATIVE_SYSTEM_PROMPT = (
    "You are an expert ad copywriter. Generate compelling ad copy based on the provided parameters. "
    "Return ONLY valid JSON with this schema: "
    '{"headlines": [str] (5 options), "primary_texts": [str] (3 options), '
    '"descriptions": [str] (3 short descriptions), "cta_suggestions": [str] (5 CTA options)}'
)


async def generate_creatives(req: GenerateRequest) -> GenerateResponse:
    prompt = (
        f"Product/Service: {req.product}\n"
        f"Target Audience: {req.audience}\n"
        f"Tone: {req.tone}\n"
        f"Platform: {req.platform}\n"
        f"Industry: {req.industry}\n\n"
        "Generate ad copy variations optimized for this platform and audience."
    )

    llm_response = await call_llm(prompt, system_prompt=_CREATIVE_SYSTEM_PROMPT, temperature=0.8)
    if llm_response is None:
        return _generate_from_templates(req)

    try:
        cleaned = llm_response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"LLM creative response not valid JSON: {exc}")
        return _generate_from_templates(req)

    try:
        return GenerateResponse(
            headlines=data.get("headlines", [])[:5] or ["Your Ad Headline"],
            primary_texts=data.get("primary_texts", [])[:3] or ["Your ad primary text."],
            descriptions=data.get("descriptions", [])[:3] or ["Your ad description."],
            cta_suggestions=data.get("cta_suggestions", [])[:5] or ["Learn More"],
            platform=req.platform,
            tone=req.tone,
        )
    except Exception as exc:
        logger.warning(f"Failed to build creative response from LLM data: {exc}")
        return _generate_from_templates(req)


# ---------------------------------------------------------------------------
# Improvement engine
# ---------------------------------------------------------------------------

def _readability_score(text: str) -> tuple[int, str]:
    words = text.split()
    word_count = len(words)
    sentences = re.split(r"[.!?]+", text)
    sentence_count = max(len([s for s in sentences if s.strip()]), 1)
    avg_sentence_len = word_count / sentence_count

    if avg_sentence_len <= 15:
        return 90, "Excellent readability — short, punchy sentences."
    elif avg_sentence_len <= 25:
        return 70, "Good readability. Consider breaking longer sentences."
    else:
        return 40, "Sentences are long. Shorten for better engagement."


def _emotional_score(text: str) -> tuple[int, str]:
    power_words = [
        "free", "new", "proven", "exclusive", "instant", "easy", "save",
        "discover", "guaranteed", "limited", "secret", "amazing", "powerful",
        "transform", "boost", "unlock", "join", "love", "best", "fast",
    ]
    lower = text.lower()
    found = [w for w in power_words if w in lower]
    count = len(found)
    if count >= 4:
        return 90, f"Strong emotional triggers ({', '.join(found[:5])})."
    elif count >= 2:
        return 65, f"Some emotional triggers present ({', '.join(found)}). Add more power words."
    else:
        return 30, "Lacks emotional triggers. Add words like 'free', 'proven', 'exclusive'."


def _cta_score(text: str) -> tuple[int, str]:
    cta_patterns = [
        r"\b(sign\s+up|get\s+started|try\s+(it\s+)?free|learn\s+more|shop\s+now)\b",
        r"\b(buy\s+now|order\s+now|subscribe|download|join|start|claim|book)\b",
        r"\b(contact\s+us|request|explore|discover|register)\b",
    ]
    for pat in cta_patterns:
        if re.search(pat, text, re.IGNORECASE):
            return 85, "Clear call-to-action detected."
    return 25, "No clear call-to-action found. Add a CTA like 'Get Started' or 'Learn More'."


def _length_score(text: str, platform: str) -> tuple[int, str]:
    length = len(text)
    limits = {"meta": (50, 300), "google": (30, 180), "tiktok": (30, 150)}
    ideal_min, ideal_max = limits.get(platform, (50, 300))
    if ideal_min <= length <= ideal_max:
        return 90, f"Length ({length} chars) is optimal for {platform}."
    elif length < ideal_min:
        return 50, f"Text is short ({length} chars). Aim for {ideal_min}-{ideal_max} for {platform}."
    else:
        return 50, f"Text is long ({length} chars). Consider trimming to ~{ideal_max} chars for {platform}."


def _rewrite(text: str) -> str:
    rewritten = text.strip()
    rewritten = re.sub(r"[!]{2,}", "!", rewritten)
    rewritten = re.sub(r"[?]{2,}", "?", rewritten)
    sentences = re.split(r"(?<=[.!?])\s+", rewritten)
    if sentences and not re.search(r"\b(learn|start|get|try|shop|buy|sign|join|book|discover)\b", sentences[-1], re.IGNORECASE):
        rewritten = rewritten.rstrip(".!? ") + ". Get started today!"
    return rewritten


def improve_copy(req: ImproveRequest) -> ImproveResponse:
    improvements: list[ImprovementItem] = []

    read_score, read_msg = _readability_score(req.text)
    improvements.append(ImprovementItem(category="Readability", current_score=f"{read_score}/100", suggestion=read_msg))

    emo_score, emo_msg = _emotional_score(req.text)
    improvements.append(ImprovementItem(category="Emotional Triggers", current_score=f"{emo_score}/100", suggestion=emo_msg))

    cta_s, cta_msg = _cta_score(req.text)
    improvements.append(ImprovementItem(category="Call-to-Action", current_score=f"{cta_s}/100", suggestion=cta_msg))

    len_score, len_msg = _length_score(req.text, req.platform)
    improvements.append(ImprovementItem(category="Length Optimization", current_score=f"{len_score}/100", suggestion=len_msg))

    overall = (read_score + emo_score + cta_s + len_score) // 4

    tips = [
        "Use numbers and statistics to increase credibility.",
        "Address the reader directly with 'you' and 'your'.",
        "Lead with the strongest benefit in your headline.",
        "Test multiple variations to find what resonates.",
    ]

    return ImproveResponse(
        overall_score=overall,
        improvements=improvements,
        rewritten=_rewrite(req.text),
        tips=tips,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/creative/generate", response_model=GenerateResponse)
async def generate_ad_creative(
    req: GenerateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate ad copy variations from a product description."""
    return await generate_creatives(req)


@router.post("/creative/improve", response_model=ImproveResponse)
async def improve_ad_creative(
    req: ImproveRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Suggest improvements for existing ad copy."""
    return improve_copy(req)
