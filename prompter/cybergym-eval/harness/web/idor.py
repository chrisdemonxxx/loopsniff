"""IDOR / authorization bypass detector.

Given two authenticated sessions (e.g., user A and user B) and a list of
endpoints discovered while logged in as A, it re-requests each endpoint
as B (and unauthenticated) and flags cases where B / anon receives the
same sensitive content as A.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

from .crawler import Endpoint
from .probes import ProbeResult, default_sender


@dataclass
class IDORDetector:
    user_a_session: requests.Session
    user_b_session: Optional[requests.Session] = None
    anon_session: Optional[requests.Session] = field(default_factory=requests.Session)
    timeout: float = 5.0
    similarity_threshold: float = 0.85

    def scan(self, endpoints: List[Endpoint]) -> List[ProbeResult]:
        results: List[ProbeResult] = []
        for ep in endpoints:
            if ep.method.upper() != "GET":
                continue
            try:
                ra = default_sender(self.user_a_session, ep, ep.params, self.timeout)
            except requests.RequestException:
                continue
            if ra.status_code >= 400 or len(ra.text) < 32:
                continue
            for label, sess in [("anon", self.anon_session), ("user_b", self.user_b_session)]:
                if sess is None:
                    continue
                try:
                    rx = default_sender(sess, ep, ep.params, self.timeout)
                except requests.RequestException:
                    continue
                if rx.status_code != 200:
                    continue
                sim = difflib.SequenceMatcher(None, ra.text[:4000], rx.text[:4000]).ratio()
                if sim >= self.similarity_threshold:
                    results.append(ProbeResult(
                        probe="idor",
                        cwe="CWE-639",
                        severity="high",
                        confidence=min(0.6 + (sim - self.similarity_threshold), 0.95),
                        endpoint_url=ep.url,
                        method=ep.method,
                        param=",".join(ep.params.keys()) or "(path)",
                        payload=f"replay-as-{label}",
                        evidence=f"{label} response is {sim:.0%} similar to authorized response",
                        request={"method": ep.method, "url": ep.url, "as": label},
                        response_excerpt=rx.text[:512],
                    ))
        return results
