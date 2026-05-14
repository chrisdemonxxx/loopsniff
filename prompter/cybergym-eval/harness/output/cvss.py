"""CVSS v3.1 base-score helper."""
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
_AC = {"L": 0.77, "H": 0.44}
_PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_C = {"N": 0.85, "L": 0.68, "H": 0.50}
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"H": 0.56, "L": 0.22, "N": 0.0}

_CWE_DEFAULT_VECTOR: Dict[str, Dict[str, str]] = {
    "CWE-119": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="H", I="H", A="H"),
    "CWE-120": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="H", I="H", A="H"),
    "CWE-122": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="H", I="H", A="H"),
    "CWE-125": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="H", I="N", A="L"),
    "CWE-416": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="H", I="H", A="H"),
    "CWE-415": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="L", I="L", A="H"),
    "CWE-476": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="N", I="N", A="H"),
    "CWE-401": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="N", I="N", A="L"),
    "CWE-190": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="L", I="L", A="H"),
    "CWE-191": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="L", I="L", A="H"),
    "CWE-369": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="N", I="N", A="H"),
    "CWE-197": dict(AV="N", AC="H", PR="N", UI="N", S="U", C="L", I="L", A="L"),
    "CWE-680": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="H", I="H", A="H"),
    "CWE-89":  dict(AV="N", AC="L", PR="N", UI="N", S="C", C="H", I="H", A="H"),
    "CWE-78":  dict(AV="N", AC="L", PR="N", UI="N", S="C", C="H", I="H", A="H"),
    "CWE-611": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="H", I="N", A="N"),
    "CWE-918": dict(AV="N", AC="L", PR="L", UI="N", S="C", C="H", I="L", A="L"),
    "CWE-639": dict(AV="N", AC="L", PR="L", UI="N", S="U", C="H", I="N", A="N"),
    "CWE-134": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="H", I="H", A="H"),
    "CWE-73":  dict(AV="N", AC="L", PR="L", UI="N", S="U", C="H", I="H", A="N"),
    "CWE-326": dict(AV="N", AC="H", PR="N", UI="N", S="U", C="H", I="N", A="N"),
    "CWE-327": dict(AV="N", AC="H", PR="N", UI="N", S="U", C="H", I="N", A="N"),
    "CWE-330": dict(AV="N", AC="H", PR="N", UI="N", S="U", C="H", I="L", A="N"),
    "CWE-798": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="H", I="H", A="N"),
    "CWE-287": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="H", I="H", A="N"),
    "CWE-311": dict(AV="N", AC="L", PR="N", UI="N", S="U", C="H", I="N", A="N"),
}


def default_vector(cwe: str) -> Dict[str, str]:
    v = _CWE_DEFAULT_VECTOR.get((cwe or "").upper())
    if v:
        return dict(v)
    return dict(AV="N", AC="L", PR="L", UI="N", S="U", C="L", I="L", A="L")


def _roundup(x: float) -> float:
    n = int(round(x * 100000))
    if n % 10000 == 0:
        return n / 100000
    return (math.floor(n / 10000) + 1) / 10.0


def compute_cvss(vector: Dict[str, str]) -> Tuple[float, str]:
    v = {k: vector.get(k, "L") for k in ("AV", "AC", "PR", "UI", "S", "C", "I", "A")}
    av = _AV.get(v["AV"], _AV["N"])
    ac = _AC.get(v["AC"], _AC["L"])
    ui = _UI.get(v["UI"], _UI["N"])
    scope_changed = v["S"] == "C"
    pr = (_PR_C if scope_changed else _PR_U).get(v["PR"], 0.85)
    c = _CIA.get(v["C"], 0.0)
    i = _CIA.get(v["I"], 0.0)
    a = _CIA.get(v["A"], 0.0)

    iss = 1 - ((1 - c) * (1 - i) * (1 - a))
    if scope_changed:
        impact = 7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15)
    else:
        impact = 6.42 * iss
    exploitability = 8.22 * av * ac * pr * ui

    if impact <= 0:
        score = 0.0
    elif scope_changed:
        score = _roundup(min(1.08 * (impact + exploitability), 10.0))
    else:
        score = _roundup(min(impact + exploitability, 10.0))

    vstr = (
        f"CVSS:3.1/AV:{v['AV']}/AC:{v['AC']}/PR:{v['PR']}/UI:{v['UI']}/"
        f"S:{v['S']}/C:{v['C']}/I:{v['I']}/A:{v['A']}"
    )
    return score, vstr


def severity_band(score: float) -> str:
    if score == 0:
        return "none"
    if score < 4.0:
        return "low"
    if score < 7.0:
        return "medium"
    if score < 9.0:
        return "high"
    return "critical"


def cvss_for_finding(cwe: str,
                     verifier_score: Optional[float] = None,
                     vector_overrides: Optional[Dict[str, str]] = None
                     ) -> Tuple[float, str, str]:
    vec = default_vector(cwe)
    if vector_overrides:
        for k, val in vector_overrides.items():
            if k in vec and val:
                vec[k] = val
    score, vstr = compute_cvss(vec)
    if verifier_score and verifier_score > 0:
        score = max(score, min(10.0, float(verifier_score)))
    score = round(min(10.0, max(0.0, score)), 1)
    return score, vstr, severity_band(score)
