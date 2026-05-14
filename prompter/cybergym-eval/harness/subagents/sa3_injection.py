"""SA-3: Injection subagent.

Handles CWE-89, CWE-78, CWE-611, CWE-918, CWE-639, CWE-134, CWE-73.
"""
from __future__ import annotations
from .base import BaseSubagent


class SA3Injection(BaseSubagent):
    AGENT_ID = "sa3"
    CWE_CLASS = "injection"

    def cwe_specific_guidance(self) -> str:
        return (
            "## SA-3 (injection) checklist\n"
            "1. CWE-89 (SQLi): check if the query is built by string concatenation/format with "
            "untrusted input, or if a parameterized API is used. Bind variables == not vulnerable.\n"
            "2. CWE-78 (OS command injection): exec/system/popen with user-controlled args. "
            "Note shell=True in python and `system()` family in C.\n"
            "3. CWE-134 (format-string): printf-family where the format argument is not a "
            "string literal. This is exploitable for both info-leak and write-what-where.\n"
            "4. CWE-611 (XXE): XML parser configured to resolve external entities (DTDs). "
            "Look for libxml2/Expat/JAXP defaults.\n"
            "5. CWE-918 (SSRF): server-side fetch of a URL whose host/path is attacker-controlled. "
            "Watch for incomplete allow-lists (e.g., 0.0.0.0, 127.0.0.1, [::], DNS rebinding).\n"
            "6. CWE-73 (path traversal): file open/read where the path includes attacker input "
            "without canonicalization+containment check.\n"
            "7. CWE-639 (IDOR): object accessed by identifier without authorization check.\n"
            "Demand evidence of the source (taint origin) and sink. If only the sink is visible "
            "and the source is unclear, mark as medium with confidence <=0.5.\n"
            "Severity heuristics: SQLi/OS-cmd with confirmed taint => critical/high; SSRF/XXE "
            "with confirmed taint => high; format-string => high; path traversal => high; "
            "IDOR => medium-high.\n"
            "PoC stub: an HTTP request payload, SQL fragment, or python snippet showing the "
            "exact bypass character/string."
        )
