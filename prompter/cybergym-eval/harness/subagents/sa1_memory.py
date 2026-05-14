"""SA-1: Memory-corruption subagent.

Handles CWE-119, CWE-120, CWE-122, CWE-125, CWE-416, CWE-476, CWE-415, CWE-401.
"""
from __future__ import annotations
from .base import BaseSubagent


class SA1Memory(BaseSubagent):
    AGENT_ID = "sa1"
    CWE_CLASS = "memory"

    def cwe_specific_guidance(self) -> str:
        return (
            "## SA-1 (memory corruption) checklist\n"
            "When evaluating the finding, focus on:\n"
            "1. Is the buffer/object size attacker-controlled or derived from untrusted input "
            "(network read, file parse, IPC)?\n"
            "2. For CWE-119/120/122/125 (overflow / OOB read): is there a missing bounds check "
            "between the size source and the memory operation? Walk the data flow.\n"
            "3. For CWE-416 (UAF): identify the freeing site and the dangling-pointer dereference. "
            "Is there a window where another path can re-allocate the same chunk?\n"
            "4. For CWE-415 (double free): are there multiple free paths reachable from the same input?\n"
            "5. For CWE-476 (NULL deref): can the producing call legitimately return NULL "
            "(malloc, fopen, accept) without subsequent check?\n"
            "6. For CWE-401 (memory leak): only report HIGH if it's a remotely-triggerable "
            "DoS, otherwise LOW.\n"
            "Demand evidence: cite specific line numbers from the snippet. If the snippet is "
            "missing or you cannot trace the size source, lower confidence to <=0.4.\n"
            "PoC stub format: a short C harness or Python `bytes()` payload that drives the "
            "vulnerable path. Mark untrusted-input bytes with comments.\n"
            "Severity heuristics: heap-overflow / UAF / double-free => high or critical; "
            "stack OOB read => medium-high; NULL deref reachable from network => medium; "
            "leak => low."
        )
