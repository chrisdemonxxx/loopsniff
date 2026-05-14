"""SA-2: Integer-bug subagent.

Handles CWE-190, CWE-191, CWE-369, CWE-197, CWE-680.
"""
from __future__ import annotations
from .base import BaseSubagent


class SA2Integer(BaseSubagent):
    AGENT_ID = "sa2"
    CWE_CLASS = "integer"

    def cwe_specific_guidance(self) -> str:
        return (
            "## SA-2 (integer bugs) checklist\n"
            "1. CWE-190 (overflow) / CWE-191 (underflow): identify the arithmetic operation and "
            "check whether either operand is attacker-influenced. Note integer width — "
            "overflow on size_t silently wraps and is the classic malloc(n*m) bug.\n"
            "2. CWE-680 (overflow -> buffer overflow): explicitly trace whether the wrapped "
            "result is later used as a buffer size or index. If yes, severity rises to high/critical.\n"
            "3. CWE-369 (divide-by-zero): does the divisor come from untrusted input, and is "
            "the zero-check missing on every reaching path?\n"
            "4. CWE-197 (numeric truncation): a wide value cast to a narrower type may lose "
            "the high bits and bypass a length/bounds check that ran on the wider value.\n"
            "Walk the data flow. If you cannot identify both the untrusted source and the "
            "downstream sink, lower confidence to <=0.4.\n"
            "Severity heuristics: overflow feeding allocation/copy size => high; isolated "
            "overflow on a value not used as a length => medium; div-by-zero remotely "
            "triggerable => medium (DoS); pure truncation without later sink => low.\n"
            "PoC stub: a small input vector or python harness that crafts the overflowing value."
        )
