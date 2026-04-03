"""A/B testing engine — tracks variant performance and picks winners."""
import logging, hashlib
from typing import Optional

log = logging.getLogger(__name__)

def assign_variant(username: str) -> str:
    """Deterministic 50/50 split based on username hash."""
    h = hashlib.md5(username.encode()).hexdigest()
    return "A" if int(h, 16) % 2 == 0 else "B"

def chi_squared_significance(a_sent: int, a_replied: int, b_sent: int, b_replied: int) -> tuple[Optional[str], float]:
    """Run chi-squared test for independence. Returns (winner_or_None, p_value)."""
    if a_sent < 30 or b_sent < 30:
        return None, 1.0  # Not enough data
    
    a_rate = a_replied / a_sent if a_sent > 0 else 0
    b_rate = b_replied / b_sent if b_sent > 0 else 0
    
    # Expected values under null hypothesis (equal rates)
    total = a_sent + b_sent
    total_replied = a_replied + b_replied
    total_not = total - total_replied
    
    if total_replied == 0 or total_not == 0:
        return None, 1.0
    
    # 2x2 contingency table
    e_a_yes = a_sent * total_replied / total
    e_a_no = a_sent * total_not / total
    e_b_yes = b_sent * total_replied / total
    e_b_no = b_sent * total_not / total
    
    # Chi-squared statistic
    chi2 = 0
    for obs, exp in [(a_replied, e_a_yes), (a_sent - a_replied, e_a_no), (b_replied, e_b_yes), (b_sent - b_replied, e_b_no)]:
        if exp > 0:
            chi2 += (obs - exp) ** 2 / exp
    
    # p-value approximation (1 degree of freedom)
    import math
    p = math.exp(-chi2 / 2) if chi2 < 20 else 0.0001
    
    winner = None
    if p < 0.05:
        winner = "A" if a_rate > b_rate else "B"
    
    return winner, round(p, 6)

def select_template(step: dict, username: str) -> tuple[str, str]:
    """Select template variant for a lead. Returns (text, variant)."""
    variant = assign_variant(username)
    if variant == "B" and step.get("template_b"):
        return step["template_b"], "B"
    return step.get("template_a", ""), "A"
