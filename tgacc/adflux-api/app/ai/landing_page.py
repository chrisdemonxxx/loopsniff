"""AI Landing Page Analyzer — HTML structure audit + LLM conversion optimization."""

import json
import time
import re
import logging
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.ai.llm_client import call_llm

router = APIRouter()
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LandingPageRequest(BaseModel):
    url: HttpUrl = Field(..., description="Landing page URL to analyze")


class Issue(BaseModel):
    check: str
    passed: bool
    severity: str  # critical, high, medium, low
    message: str
    details: str | None = None


class LandingPageResponse(BaseModel):
    url: str
    score: int = Field(..., ge=0, le=100)
    load_time_ms: int
    issues: list[Issue]
    recommendations: list[str]
    summary: str


# ---------------------------------------------------------------------------
# Checker helpers
# ---------------------------------------------------------------------------

SEVERITY_WEIGHTS = {"critical": 15, "high": 10, "medium": 5, "low": 2}


def _check_https(parsed_url) -> Issue:
    passed = parsed_url.scheme == "https"
    return Issue(
        check="HTTPS",
        passed=passed,
        severity="critical" if not passed else "low",
        message="Site uses HTTPS." if passed else "Site does NOT use HTTPS. This hurts trust and SEO.",
    )


def _check_title(soup: BeautifulSoup) -> Issue:
    title_tag = soup.find("title")
    if title_tag and title_tag.string and title_tag.string.strip():
        title_text = title_tag.string.strip()
        length = len(title_text)
        if 30 <= length <= 70:
            return Issue(check="Title Tag", passed=True, severity="low", message=f"Title tag present ({length} chars).", details=title_text)
        else:
            return Issue(check="Title Tag", passed=False, severity="medium", message=f"Title length ({length} chars) is outside ideal 30-70 range.", details=title_text)
    return Issue(check="Title Tag", passed=False, severity="high", message="Missing or empty <title> tag.")


def _check_meta_description(soup: BeautifulSoup) -> Issue:
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content", "").strip():
        content = meta["content"].strip()
        length = len(content)
        if 120 <= length <= 160:
            return Issue(check="Meta Description", passed=True, severity="low", message=f"Meta description present ({length} chars).", details=content[:160])
        else:
            return Issue(check="Meta Description", passed=False, severity="medium", message=f"Meta description length ({length} chars) is outside ideal 120-160 range.", details=content[:160])
    return Issue(check="Meta Description", passed=False, severity="high", message="Missing meta description tag.")


def _check_h1(soup: BeautifulSoup) -> Issue:
    h1_tags = soup.find_all("h1")
    if len(h1_tags) == 1:
        return Issue(check="H1 Tag", passed=True, severity="low", message="Single H1 tag found.", details=h1_tags[0].get_text(strip=True)[:120])
    elif len(h1_tags) == 0:
        return Issue(check="H1 Tag", passed=False, severity="high", message="No H1 tag found. Add a clear headline.")
    else:
        return Issue(check="H1 Tag", passed=False, severity="medium", message=f"Multiple H1 tags found ({len(h1_tags)}). Use only one.")


def _check_cta_buttons(soup: BeautifulSoup) -> Issue:
    cta_patterns = re.compile(
        r"(sign\s*up|get\s*start|buy\s*now|order|subscribe|learn\s*more|free\s*trial|try\s*free|contact|download|book|register|join|start)",
        re.IGNORECASE,
    )
    buttons = soup.find_all(["button", "a"])
    cta_found = [b.get_text(strip=True) for b in buttons if cta_patterns.search(b.get_text(strip=True))]
    if cta_found:
        return Issue(check="CTA Buttons", passed=True, severity="low", message=f"{len(cta_found)} CTA element(s) found.", details=", ".join(cta_found[:5]))
    return Issue(check="CTA Buttons", passed=False, severity="high", message="No clear CTA button or link found. Add a prominent call-to-action.")


def _check_forms(soup: BeautifulSoup) -> Issue:
    forms = soup.find_all("form")
    if forms:
        return Issue(check="Lead Capture Form", passed=True, severity="low", message=f"{len(forms)} form(s) found for lead capture.")
    return Issue(check="Lead Capture Form", passed=False, severity="medium", message="No form found. Consider adding a lead capture or contact form.")


def _check_viewport(soup: BeautifulSoup) -> Issue:
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport and viewport.get("content"):
        return Issue(check="Mobile Viewport", passed=True, severity="low", message="Mobile viewport meta tag is set.")
    return Issue(check="Mobile Viewport", passed=False, severity="high", message="Missing viewport meta tag. Page may not be mobile-friendly.")


def _check_img_alt(soup: BeautifulSoup) -> Issue:
    images = soup.find_all("img")
    if not images:
        return Issue(check="Image Alt Tags", passed=True, severity="low", message="No images found to check.")
    missing = [img.get("src", "unknown")[:60] for img in images if not img.get("alt")]
    total = len(images)
    missing_count = len(missing)
    if missing_count == 0:
        return Issue(check="Image Alt Tags", passed=True, severity="low", message=f"All {total} images have alt attributes.")
    pct = missing_count / total * 100
    return Issue(
        check="Image Alt Tags",
        passed=False,
        severity="medium" if pct < 50 else "high",
        message=f"{missing_count}/{total} images missing alt attributes ({pct:.0f}%).",
        details=", ".join(missing[:3]),
    )


def _check_load_time(load_time_ms: int) -> Issue:
    if load_time_ms < 1000:
        return Issue(check="Load Time", passed=True, severity="low", message=f"Fast response time ({load_time_ms}ms).")
    elif load_time_ms < 3000:
        return Issue(check="Load Time", passed=True, severity="low", message=f"Acceptable response time ({load_time_ms}ms).")
    else:
        return Issue(check="Load Time", passed=False, severity="high", message=f"Slow response time ({load_time_ms}ms). Aim for under 3 seconds.")


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

_LP_SYSTEM_PROMPT = (
    "You are a conversion rate optimization expert. Analyze this landing page content "
    "and provide ONLY valid JSON with this schema: "
    '{"score": int (0-100), "strengths": [str], "weaknesses": [str], "recommendations": [str]}'
)


async def analyze_page(url: str) -> LandingPageResponse:
    parsed = urlparse(url)
    try:
        start = time.time()
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(url, headers={"User-Agent": "AdFlux-LandingPageAnalyzer/1.0"})
        load_time_ms = int((time.time() - start) * 1000)
    except httpx.TimeoutException:
        raise HTTPException(status_code=422, detail="Page timed out (>15s). URL may be unreachable.")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=422, detail=f"Could not fetch URL: {exc}")

    if resp.status_code >= 400:
        raise HTTPException(status_code=422, detail=f"Page returned HTTP {resp.status_code}.")

    soup = BeautifulSoup(resp.text, "html.parser")

    issues: list[Issue] = [
        _check_https(parsed),
        _check_load_time(load_time_ms),
        _check_title(soup),
        _check_meta_description(soup),
        _check_h1(soup),
        _check_cta_buttons(soup),
        _check_forms(soup),
        _check_viewport(soup),
        _check_img_alt(soup),
    ]

    penalty = sum(SEVERITY_WEIGHTS.get(i.severity, 3) for i in issues if not i.passed)
    html_score = max(0, 100 - penalty)

    recommendations: list[str] = []
    for issue in issues:
        if not issue.passed:
            recommendations.append(issue.message)
    if not recommendations:
        recommendations.append("Page looks great! Consider running A/B tests on your headline and CTA.")

    if html_score >= 80:
        summary = "Landing page is well-optimized with minor improvements possible."
    elif html_score >= 50:
        summary = "Landing page has several issues that could hurt conversion rates."
    else:
        summary = "Landing page has critical issues that need immediate attention."

    # --- LLM content analysis for conversion optimization ---
    page_text = soup.get_text(separator="\n", strip=True)[:3000]
    title_text = soup.title.string.strip() if soup.title and soup.title.string else "N/A"

    prompt = (
        f"Landing page URL: {url}\n"
        f"Title: {title_text}\n"
        f"Load time: {load_time_ms}ms\n\n"
        f"Page content (truncated):\n\"\"\"\n{page_text}\n\"\"\"\n\n"
        "Analyze this landing page for conversion rate optimization."
    )

    llm_response = await call_llm(prompt, system_prompt=_LP_SYSTEM_PROMPT, temperature=0.4)
    final_score = html_score

    if llm_response is not None:
        try:
            cleaned = llm_response.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
            llm_data = json.loads(cleaned)

            llm_score = int(llm_data.get("score", html_score))
            llm_score = max(0, min(100, llm_score))
            # Blend: 40% HTML structure + 60% LLM content analysis
            final_score = int(html_score * 0.4 + llm_score * 0.6)

            existing_recs = set(recommendations)
            for rec in llm_data.get("recommendations", []):
                if rec and rec not in existing_recs:
                    recommendations.append(rec)
                    existing_recs.add(rec)

            for weakness in llm_data.get("weaknesses", []):
                if weakness and weakness not in existing_recs:
                    recommendations.append(weakness)
                    existing_recs.add(weakness)

            strengths = llm_data.get("strengths", [])
            if strengths:
                summary += " Strengths: " + "; ".join(strengths[:3]) + "."

        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            log.warning(f"LLM landing page response not valid JSON: {exc}")

    return LandingPageResponse(
        url=url,
        score=final_score,
        load_time_ms=load_time_ms,
        issues=issues,
        recommendations=recommendations,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/landing-page/analyze", response_model=LandingPageResponse)
async def analyze_landing_page(
    req: LandingPageRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyze a landing page URL for SEO, UX, and conversion best practices."""
    return await analyze_page(str(req.url))
