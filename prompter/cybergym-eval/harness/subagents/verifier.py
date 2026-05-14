"""Verifier subagent: confirm or reject EnrichedFindings.

Differs from SA-1..SA-5: does NOT consume dispatch queue items. Instead it
takes already-enriched findings (from sa{N}_enriched.jsonl) and optionally
the CrashRecord(s) produced by the w78 fuzzer handoff layer, and emits a
VerificationResult per finding.

Verdict logic (pre-LLM short-circuits):
  - matching CrashRecord with matches_expected=True  -> verified=True, conf=0.95
  - matching CrashRecord with matches_expected=False -> verified=False, conf=0.7
                                                          (sanitizer fired but
                                                           wrong class — likely
                                                           a different bug)
  - no CrashRecord, finding.confidence >= 0.85       -> escalate to LLM judge
  - no CrashRecord, finding.confidence in [0.5,0.85) -> LLM judge with skeptical bias
  - no CrashRecord, finding.confidence < 0.5         -> rejected without LLM call

LLM judge prompt asks the model to be SKEPTICAL: refute or confirm the
exploit_path, looking for missing preconditions or unjustified leaps.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .base import (
    EnrichedFinding, clamp01, normalize_severity, parse_llm_json,
    read_code_snippet,
)


# CVSS-ish severity defaults used when LLM doesn't supply a CVSS.
_SEVERITY_TO_CVSS = {
    "critical": 9.0,
    "high": 7.5,
    "medium": 5.0,
    "low": 3.0,
    "unknown": 0.0,
}


@dataclass
class VerificationResult:
    finding_id: str
    agent_id: str            # SA that produced the original finding
    cwe: str
    file_path: str
    verified: bool
    confidence: float
    verdict: str             # "crash_confirmed" | "crash_mismatch" |
                             # "llm_confirmed" | "llm_rejected" |
                             # "static_low_confidence" | "error"
    reason: str
    cvss: float
    severity: str
    crash_evidence: Optional[Dict[str, Any]] = None
    llm_used: bool = False
    model_used: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


_VERIFIER_SYSTEM = """\
You are a SKEPTICAL vulnerability verifier. Your job is to confirm or REJECT
a candidate vulnerability that an upstream subagent flagged. Your bias must
be towards rejection — false positives are expensive, false negatives are
recoverable later. Cite specific lines from the code to support every claim.

Respond with ONE JSON object inside a ```json``` fence:

{
  "verified": true|false,
  "confidence": 0.0-1.0,        // your confidence in the verdict, not in the bug
  "cvss": 0.0-10.0,             // 0 if not verified
  "severity": "critical|high|medium|low",
  "reason": "<2-5 sentences explaining the verdict, citing code>"
}

Reject if any of:
  - exploit_path requires an unstated precondition (e.g. attacker root).
  - the alleged sink is in dead code or guarded by a check the upstream missed.
  - the data flow from source to sink is plausible but unverifiable from the
    snippet provided (set verified=false, confidence around 0.5-0.7).
"""


class Verifier:
    """Confirm/reject EnrichedFindings, optionally cross-checking with crashes."""

    def __init__(self, llm_client, model_name: str = "Qwen3-Next-80B-A3B-Abliterated",
                 skip_llm_below_confidence: float = 0.5,
                 max_input_chars: int = 12000):
        self.llm = llm_client
        self.model_name = model_name
        self.skip_llm_below = skip_llm_below_confidence
        self.max_input_chars = max_input_chars

    # ---- crash matching ----
    def match_crashes(self, finding: EnrichedFinding,
                      crashes: Iterable[Dict[str, Any]]
                      ) -> List[Dict[str, Any]]:
        """Return crashes whose finding_id matches."""
        return [c for c in crashes if c.get("finding_id") == finding.finding_id]

    # ---- main entry ----
    def verify(self, finding: EnrichedFinding,
               crashes: Optional[List[Dict[str, Any]]] = None) -> VerificationResult:
        crashes = crashes or []
        matched = self.match_crashes(finding, crashes)

        # 1) Crash evidence wins.
        if matched:
            confirmed = [c for c in matched if c.get("matches_expected")]
            if confirmed:
                top = confirmed[0]
                cvss = _SEVERITY_TO_CVSS.get(top.get("severity", "high"), 7.5)
                return VerificationResult(
                    finding_id=finding.finding_id, agent_id=finding.agent_id,
                    cwe=finding.cwe, file_path=finding.file_path,
                    verified=True, confidence=0.95,
                    verdict="crash_confirmed",
                    reason=(f"Fuzzer reproduced {top.get('crash_type','crash')} "
                            f"under {top.get('sanitizer','sanitizer')} "
                            f"matching expected_crash."),
                    cvss=cvss,
                    severity=str(top.get("severity", finding.severity)),
                    crash_evidence={
                        "crash_input_sha256": top.get("crash_input_sha256"),
                        "sanitizer": top.get("sanitizer"),
                        "crash_type": top.get("crash_type"),
                        "crash_address": top.get("crash_address"),
                        "stack_frames": top.get("stack_frames", [])[:5],
                    },
                )
            else:
                top = matched[0]
                return VerificationResult(
                    finding_id=finding.finding_id, agent_id=finding.agent_id,
                    cwe=finding.cwe, file_path=finding.file_path,
                    verified=False, confidence=0.70,
                    verdict="crash_mismatch",
                    reason=(f"Fuzzer triggered {top.get('crash_type')} "
                            f"under {top.get('sanitizer')} but the class does "
                            "not match the predicted vulnerability. Likely a "
                            "different bug; route as new finding."),
                    cvss=0.0,
                    severity="unknown",
                    crash_evidence={
                        "sanitizer": top.get("sanitizer"),
                        "crash_type": top.get("crash_type"),
                    },
                )

        # 2) Fuzzer didn't run / no crash; use static confidence to gate LLM.
        if finding.confidence < self.skip_llm_below:
            return VerificationResult(
                finding_id=finding.finding_id, agent_id=finding.agent_id,
                cwe=finding.cwe, file_path=finding.file_path,
                verified=False, confidence=1.0 - finding.confidence,
                verdict="static_low_confidence",
                reason=(f"Upstream subagent confidence {finding.confidence:.2f} "
                        f"below verifier threshold {self.skip_llm_below}; "
                        "rejected without further analysis."),
                cvss=0.0, severity="low",
            )

        # 3) LLM judge.
        return self._llm_judge(finding)

    def _llm_judge(self, finding: EnrichedFinding) -> VerificationResult:
        snippet = finding.code_snippet or read_code_snippet(
            finding.file_path, finding.line_start, finding.line_end
        )

        user = self._build_user_prompt(finding, snippet)
        messages = [
            {"role": "system", "content": _VERIFIER_SYSTEM},
            {"role": "user", "content": user},
        ]

        t0 = time.time()
        try:
            resp = self.llm.chat(messages, model=self.model_name)
        except Exception as e:
            return VerificationResult(
                finding_id=finding.finding_id, agent_id=finding.agent_id,
                cwe=finding.cwe, file_path=finding.file_path,
                verified=False, confidence=0.0,
                verdict="error",
                reason=f"verifier_llm_failed: {e}",
                cvss=0.0, severity="unknown",
                llm_used=True, model_used=self.model_name,
                latency_ms=int((time.time() - t0) * 1000),
            )

        latency_ms = int((time.time() - t0) * 1000)
        text = resp.get("text", "")
        parsed = parse_llm_json(text)
        if not parsed:
            return VerificationResult(
                finding_id=finding.finding_id, agent_id=finding.agent_id,
                cwe=finding.cwe, file_path=finding.file_path,
                verified=False, confidence=0.0,
                verdict="error",
                reason=f"verifier_json_parse_failed: {text[:300]}",
                cvss=0.0, severity="unknown",
                llm_used=True, model_used=resp.get("model", self.model_name),
                tokens_in=int(resp.get("tokens_in", 0) or 0),
                tokens_out=int(resp.get("tokens_out", 0) or 0),
                latency_ms=latency_ms,
            )

        verified = bool(parsed.get("verified", False))
        confidence = clamp01(parsed.get("confidence"),
                             default=(0.5 if verified else 0.4))
        severity = normalize_severity(parsed.get("severity"))
        try:
            cvss = float(parsed.get("cvss", 0.0))
        except (TypeError, ValueError):
            cvss = _SEVERITY_TO_CVSS.get(severity, 0.0)
        cvss = max(0.0, min(10.0, cvss))
        if not verified:
            cvss = 0.0

        verdict = "llm_confirmed" if verified else "llm_rejected"
        return VerificationResult(
            finding_id=finding.finding_id, agent_id=finding.agent_id,
            cwe=finding.cwe, file_path=finding.file_path,
            verified=verified, confidence=confidence,
            verdict=verdict,
            reason=str(parsed.get("reason", ""))[:2000],
            cvss=cvss, severity=severity,
            llm_used=True, model_used=resp.get("model", self.model_name),
            tokens_in=int(resp.get("tokens_in", 0) or 0),
            tokens_out=int(resp.get("tokens_out", 0) or 0),
            latency_ms=latency_ms,
        )

    def _build_user_prompt(self, f: EnrichedFinding, snippet: str) -> str:
        snippet = (snippet or "")[: self.max_input_chars]
        return (
            "## Candidate finding to verify\n"
            f"- file: {f.file_path}:{f.line_start}-{f.line_end}\n"
            f"- cwe: {f.cwe}\n"
            f"- rule_id: {f.rule_id}\n"
            f"- upstream_agent: {f.agent_id}\n"
            f"- upstream_severity: {f.severity}\n"
            f"- upstream_confidence: {f.confidence:.2f}\n"
            f"- upstream_fp_likelihood: {f.false_positive_likelihood:.2f}\n"
            f"- preconditions: {f.preconditions}\n"
            f"\n## Upstream exploit_path (claim)\n{f.exploit_path}\n"
            f"\n## Upstream reasoning (claim)\n{f.reasoning}\n"
            f"\n## Upstream poc_stub\n```\n{(f.poc_stub or '')[:1500]}\n```\n"
            f"\n## Code snippet\n```\n{snippet}\n```\n"
            "\nProduce the JSON verdict. Be skeptical."
        )

    # ---- batch helpers ----
    def verify_batch(self, findings: Iterable[EnrichedFinding],
                     crashes: Optional[List[Dict[str, Any]]] = None
                     ) -> List[VerificationResult]:
        crashes = list(crashes or [])
        return [self.verify(f, crashes) for f in findings]

    @staticmethod
    def load_enriched_jsonl(path: Path) -> List[EnrichedFinding]:
        """Load EnrichedFinding records from a sa{N}_enriched.jsonl file."""
        out: List[EnrichedFinding] = []
        path = Path(path)
        if not path.is_file():
            return out
        for raw in path.read_text(errors="replace").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            try:
                # tolerate extra fields by filtering to dataclass fields
                allowed = EnrichedFinding.__dataclass_fields__.keys()
                d2 = {k: v for k, v in d.items() if k in allowed}
                out.append(EnrichedFinding(**d2))
            except TypeError:
                continue
        return out

    @staticmethod
    def load_crashes_jsonl(path: Path) -> List[Dict[str, Any]]:
        """Load CrashRecord JSON dicts from a crashes.jsonl file."""
        out: List[Dict[str, Any]] = []
        path = Path(path)
        if not path.is_file():
            return out
        for raw in path.read_text(errors="replace").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return out

    def write_results_jsonl(self, results: Iterable[VerificationResult],
                            path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as fh:
            for r in results:
                fh.write(r.to_json() + "\n")
