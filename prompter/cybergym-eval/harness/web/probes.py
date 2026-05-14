"""Active web vulnerability probes.

Each probe takes an Endpoint + an HTTP sender, mutates one parameter
at a time with payloads, and returns ProbeResult objects describing
suspected vulnerabilities. Detection uses response signatures
(error strings, reflected canaries, timing, status codes).

All probes are designed to be safe-ish (no destructive payloads) and
fast (small payload counts, time-budgeted).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

import requests

from .crawler import Endpoint


# ---------------- result type ----------------

@dataclass
class ProbeResult:
    probe: str
    cwe: str
    severity: str
    confidence: float
    endpoint_url: str
    method: str
    param: str
    payload: str
    evidence: str
    request: Dict[str, str] = field(default_factory=dict)
    response_excerpt: str = ""

    def to_finding_dict(self) -> Dict:
        """Convert to the static_analysis.Finding-shaped dict the
        triage / dispatch / verifier pipeline already understands."""
        return {
            "layer": "web",
            "file_path": self.endpoint_url,    # URL stands in for path
            "line_start": 0,
            "line_end": 0,
            "rule_id": f"web.{self.probe}",
            "severity": self.severity,
            "message": f"{self.probe} suspected on parameter '{self.param}': {self.evidence}",
            "cwe": self.cwe,
            "confidence": "high" if self.confidence >= 0.75 else "medium",
            "metadata": {
                "method": self.method,
                "param": self.param,
                "payload": self.payload,
                "evidence": self.evidence,
                "request": self.request,
                "response_excerpt": self.response_excerpt[:512],
            },
        }


# ---------------- HTTP sender ----------------

def default_sender(
    session: requests.Session, ep: Endpoint, params: Dict[str, str], timeout: float
) -> requests.Response:
    if ep.method.upper() == "GET":
        return session.get(ep.url, params=params, timeout=timeout, allow_redirects=False)
    if "json" in (ep.content_type or "").lower():
        return session.request(ep.method, ep.url, json=params,
                               timeout=timeout, allow_redirects=False)
    return session.request(ep.method, ep.url, data=params,
                           timeout=timeout, allow_redirects=False)


# ---------------- base ----------------

class _BaseProbe:
    name: str = "base"
    cwe: str = "CWE-?"
    severity: str = "medium"
    payloads: List[str] = []

    def __init__(self, session: Optional[requests.Session] = None, timeout: float = 5.0):
        self.session = session or requests.Session()
        self.timeout = timeout

    def run(self, ep: Endpoint) -> List[ProbeResult]:
        results: List[ProbeResult] = []
        if not ep.params:
            return results
        try:
            base_resp = default_sender(self.session, ep, ep.params, self.timeout)
            base_text = base_resp.text or ""
        except requests.RequestException:
            base_text = ""
        for pname in list(ep.params.keys()):
            for payload in self.payloads:
                muted = dict(ep.params)
                muted[pname] = payload
                try:
                    t0 = time.time()
                    resp = default_sender(self.session, ep, muted, self.timeout)
                    elapsed = time.time() - t0
                    text = resp.text or ""
                except requests.RequestException as e:
                    text, elapsed, resp = "", 0.0, None
                hit = self._detect(payload, text, base_text, elapsed,
                                   resp.status_code if resp is not None else 0,
                                   resp.headers if resp is not None else {})
                if hit:
                    evidence, conf = hit
                    results.append(ProbeResult(
                        probe=self.name, cwe=self.cwe, severity=self.severity,
                        confidence=conf, endpoint_url=ep.url, method=ep.method,
                        param=pname, payload=payload, evidence=evidence,
                        request={"method": ep.method, "url": ep.url, **{f"param.{k}": v for k, v in muted.items()}},
                        response_excerpt=text[:512],
                    ))
                    break  # one finding per param per probe is enough
        return results

    def _detect(self, payload: str, body: str, baseline: str, elapsed: float,
                status: int, headers) -> Optional[tuple]:
        raise NotImplementedError


# ---------------- SQLi ----------------

class SQLiProbe(_BaseProbe):
    name = "sqli"
    cwe = "CWE-89"
    severity = "critical"
    payloads = ["'", "''", "' OR '1'='1", "1' OR '1'='1' --", "\"); --"]
    _ERRORS = [
        re.compile(r"sql syntax.*mysql", re.I),
        re.compile(r"warning.*mysqli?_", re.I),
        re.compile(r"unclosed quotation mark after the character string", re.I),
        re.compile(r"sqlite3?\.(operationalerror|databaseerror)", re.I),
        re.compile(r"psql:.*ERROR", re.I),
        re.compile(r"PG::SyntaxError", re.I),
        re.compile(r"ORA-\d{5}", re.I),
        re.compile(r"unterminated quoted string", re.I),
        re.compile(r"you have an error in your sql syntax", re.I),
    ]

    def _detect(self, payload, body, baseline, elapsed, status, headers):
        for pat in self._ERRORS:
            m = pat.search(body)
            if m:
                return f"SQL error string in response: {m.group(0)[:80]!r}", 0.9
        return None


# ---------------- SSRF ----------------

class SSRFProbe(_BaseProbe):
    name = "ssrf"
    cwe = "CWE-918"
    severity = "high"
    payloads = [
        "http://127.0.0.1:1/", "http://localhost/", "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd", "gopher://127.0.0.1:1/", "dict://127.0.0.1:1/",
    ]

    def _detect(self, payload, body, baseline, elapsed, status, headers):
        b = body.lower()
        if "root:x:0:0" in b or "/bin/bash" in b:
            return "/etc/passwd content reflected (file:// SSRF)", 0.95
        if "ami-id" in b or "instance-id" in b or "iam/security-credentials" in b:
            return "AWS IMDS data reflected", 0.95
        if "ECONNREFUSED" in body or "connection refused" in b or "could not connect" in b:
            return "internal connection attempt observed", 0.7
        return None


# ---------------- XXE ----------------

class XXEProbe(_BaseProbe):
    name = "xxe"
    cwe = "CWE-611"
    severity = "high"
    payloads = [
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><x>&xxe;</x>',
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///nonexistent_xxe_canary">]><x>&xxe;</x>',
    ]

    def run(self, ep):  # XXE: post the payload as raw XML body
        ct = (ep.content_type or "").lower()
        if "xml" not in ct and ep.method.upper() == "GET":
            return []
        results: List[ProbeResult] = []
        url = ep.url
        for payload in self.payloads:
            try:
                resp = self.session.request(
                    "POST", url, data=payload.encode(),
                    headers={"Content-Type": "application/xml"},
                    timeout=self.timeout, allow_redirects=False)
                text = resp.text or ""
            except requests.RequestException:
                continue
            hit = self._detect(payload, text, "", 0.0,
                               resp.status_code, resp.headers)
            if hit:
                evidence, conf = hit
                results.append(ProbeResult(
                    probe=self.name, cwe=self.cwe, severity=self.severity,
                    confidence=conf, endpoint_url=url, method="POST",
                    param="(xml-body)", payload=payload, evidence=evidence,
                    request={"method": "POST", "url": url,
                             "Content-Type": "application/xml"},
                    response_excerpt=text[:512],
                ))
                break
        return results

    def _detect(self, payload, body, baseline, elapsed, status, headers):
        if "root:x:0:0" in body:
            return "/etc/passwd reflected via XXE entity", 0.95
        if "nonexistent_xxe_canary" in body and "no such file" in body.lower():
            return "external entity processed (filesystem error leaked)", 0.8
        return None


# ---------------- SSTI ----------------

class SSTIProbe(_BaseProbe):
    name = "ssti"
    cwe = "CWE-94"
    severity = "high"
    payloads = ["{{7*7}}", "${7*7}", "<%= 7*7 %>", "#{7*7}", "{{7*'7'}}"]

    def _detect(self, payload, body, baseline, elapsed, status, headers):
        if "49" in body and "49" not in baseline and payload not in body:
            return f"template engine evaluated {payload!r} → 49", 0.9
        if "7777777" in body and "7777777" not in baseline:
            return f"jinja-style {{7*'7'}} evaluation observed", 0.9
        return None


# ---------------- Path traversal ----------------

class PathTraversalProbe(_BaseProbe):
    name = "path_traversal"
    cwe = "CWE-22"
    severity = "high"
    payloads = [
        "../../../../etc/passwd", "..%2F..%2F..%2Fetc%2Fpasswd",
        "....//....//....//etc/passwd", "/etc/passwd",
    ]

    def _detect(self, payload, body, baseline, elapsed, status, headers):
        if "root:x:0:0" in body and "root:x:0:0" not in baseline:
            return "/etc/passwd content disclosed", 0.95
        return None


# ---------------- Command injection ----------------

class CommandInjectionProbe(_BaseProbe):
    name = "cmd_injection"
    cwe = "CWE-78"
    severity = "critical"
    _MARKER = "h4rn3sscmdinj"
    payloads = [
        f"; echo {_MARKER}", f"| echo {_MARKER}", f"&& echo {_MARKER}",
        f"`echo {_MARKER}`", f"$(echo {_MARKER})",
    ]

    def _detect(self, payload, body, baseline, elapsed, status, headers):
        if self._MARKER in body and self._MARKER not in baseline:
            return f"shell echo marker reflected ({self._MARKER})", 0.95
        return None


# ---------------- Open redirect ----------------

class OpenRedirectProbe(_BaseProbe):
    name = "open_redirect"
    cwe = "CWE-601"
    severity = "medium"
    payloads = [
        "https://evil.example.com/", "//evil.example.com/", "/\\evil.example.com",
    ]

    def _detect(self, payload, body, baseline, elapsed, status, headers):
        if status in (301, 302, 303, 307, 308):
            loc = (headers.get("Location") or headers.get("location") or "")
            if "evil.example.com" in loc:
                return f"3xx Location header points to attacker host: {loc[:120]}", 0.9
        return None


ALL_PROBES = [
    SQLiProbe, SSRFProbe, XXEProbe, SSTIProbe,
    PathTraversalProbe, CommandInjectionProbe, OpenRedirectProbe,
]
