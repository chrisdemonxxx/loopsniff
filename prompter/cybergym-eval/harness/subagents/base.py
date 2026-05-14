"""Base subagent abstraction + enriched finding schema."""
from __future__ import annotations

import hashlib
import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


def _finding_id(finding: Dict[str, Any]) -> str:
    """Stable hash for a finding so the same bug always gets the same ID."""
    key = "|".join([
        str(finding.get("file_path", "")),
        str(finding.get("line_start", 0)),
        str(finding.get("rule_id", "")),
        str(finding.get("cwe", "")),
    ])
    return hashlib.sha1(key.encode("utf-8", errors="replace")).hexdigest()[:16]


@dataclass
class EnrichedFinding:
    """Output of a subagent: a static-analysis finding enriched with LLM reasoning."""
    agent_id: str
    finding_id: str

    file_path: str
    line_start: int
    line_end: int
    cwe: str
    rule_id: str
    layer: str
    static_priority: float

    severity: str
    confidence: float
    false_positive_likelihood: float
    exploit_path: str
    preconditions: List[str]
    poc_stub: str
    reasoning: str

    model_used: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    timestamp: float = field(default_factory=time.time)

    code_snippet: str = ""
    error: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def error_record(cls, agent_id: str, queue_item: Dict[str, Any], err: str) -> "EnrichedFinding":
        f = queue_item.get("finding", queue_item) or {}
        return cls(
            agent_id=agent_id,
            finding_id=_finding_id(f),
            file_path=str(f.get("file_path", "")),
            line_start=int(f.get("line_start", 0) or 0),
            line_end=int(f.get("line_end", 0) or 0),
            cwe=str(f.get("cwe", "")),
            rule_id=str(f.get("rule_id", "")),
            layer=str(f.get("layer", "")),
            static_priority=float(queue_item.get("priority", 0.0) or 0.0),
            severity="unknown",
            confidence=0.0,
            false_positive_likelihood=1.0,
            exploit_path="",
            preconditions=[],
            poc_stub="",
            reasoning="",
            error=err,
        )


@dataclass
class SubagentResult:
    """Aggregated result from running an agent over a queue."""
    agent_id: str
    total: int
    enriched: List[EnrichedFinding]
    errors: int
    elapsed_s: float
    estimated_cost_usd: float

    def to_summary(self) -> Dict[str, Any]:
        confs = [e.confidence for e in self.enriched if e.error is None]
        return {
            "agent_id": self.agent_id,
            "total": self.total,
            "ok": sum(1 for e in self.enriched if e.error is None),
            "errors": self.errors,
            "elapsed_s": round(self.elapsed_s, 2),
            "estimated_cost_usd": round(self.estimated_cost_usd, 4),
            "mean_confidence": round(sum(confs) / max(len(confs), 1), 3),
            "high_confidence_count": sum(1 for c in confs if c >= 0.7),
        }


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_llm_json(text: str) -> Dict[str, Any]:
    """Extract a JSON object from LLM output. Tolerant of fenced/unfenced output."""
    if not text:
        return {}
    m = JSON_BLOCK_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return {}


def read_code_snippet(file_path: str, line_start: int, line_end: int,
                      context_lines: int = 6) -> str:
    """Read the relevant code snippet with surrounding context. Returns '' on failure."""
    p = Path(file_path)
    if not p.is_file():
        return ""
    try:
        lines = p.read_text(errors="replace").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""
    n = len(lines)
    lo = max(0, line_start - 1 - context_lines)
    hi = min(n, line_end + context_lines)
    out = []
    for i in range(lo, hi):
        marker = ">>" if (line_start - 1) <= i <= (line_end - 1) else "  "
        out.append(f"{marker} {i + 1:5d} | {lines[i]}")
    return "\n".join(out)


def clamp01(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, v))


def normalize_severity(s: Any) -> str:
    if not isinstance(s, str):
        return "unknown"
    s = s.strip().lower()
    if s in ("crit", "critical"):
        return "critical"
    if s in ("hi", "high"):
        return "high"
    if s in ("med", "medium", "moderate"):
        return "medium"
    if s in ("lo", "low"):
        return "low"
    if s in ("info", "informational", "none"):
        return "low"
    return "unknown"


class BaseSubagent(ABC):
    """Abstract subagent. Subclasses implement build_prompt() and CWE_CLASS."""

    AGENT_ID: str = "base"
    CWE_CLASS: str = "generic"
    SYSTEM_PROMPT_HEADER: str = (
        "You are an offensive-security expert specialized in vulnerability triage. "
        "You receive one static-analysis finding plus a code snippet. "
        "You must decide whether the finding is a real exploitable bug, draft an exploit "
        "path, propose a PoC stub, and rate your confidence."
    )

    OUTPUT_PROTOCOL = """
You MUST respond with a single JSON object inside a fenced ```json``` block. No prose
outside the fence. Schema:

{
  "is_real_bug": true|false,
  "severity": "critical|high|medium|low",
  "confidence": 0.0-1.0,
  "false_positive_likelihood": 0.0-1.0,
  "exploit_path": "<one-paragraph attacker walkthrough>",
  "preconditions": ["<attacker controls X>", "<service exposes Y>"],
  "poc_stub": "<short python harness or raw payload bytes; <=2KB>",
  "reasoning": "<2-5 sentences justifying the verdict, citing concrete code>"
}
"""

    def __init__(self, llm_client, model_name: str = "q415dj1",
                 max_input_chars: int = 12000):
        self.llm = llm_client
        self.model_name = model_name
        self.max_input_chars = max_input_chars

    def build_prompt(self, finding: Dict[str, Any], priority: float,
                     code_snippet: str) -> List[Dict[str, str]]:
        """Default prompt builder. Subclasses can override for CWE-specific guidance."""
        sys = self.SYSTEM_PROMPT_HEADER + "\n\n" + self.cwe_specific_guidance() + "\n" + self.OUTPUT_PROTOCOL

        user_lines = [
            f"## Static analysis finding (priority={priority:.2f})",
            f"- agent: {self.AGENT_ID} ({self.CWE_CLASS})",
            f"- file: {finding.get('file_path', '?')}",
            f"- lines: {finding.get('line_start', '?')}-{finding.get('line_end', '?')}",
            f"- cwe: {finding.get('cwe', '?')}",
            f"- rule_id: {finding.get('rule_id', '?')}",
            f"- detector_layer: {finding.get('layer', '?')}",
            f"- detector_severity: {finding.get('severity', '?')}",
            f"- detector_message: {finding.get('message', '?')}",
        ]
        meta = finding.get("metadata") or {}
        if meta:
            user_lines.append(f"- metadata: {json.dumps(meta, ensure_ascii=False)[:500]}")

        if code_snippet:
            snippet = code_snippet[: self.max_input_chars]
            user_lines.append("\n## Code context (>> = reported lines)")
            user_lines.append("```")
            user_lines.append(snippet)
            user_lines.append("```")
        else:
            user_lines.append("\n## Code context\n(unavailable; reason about the finding from the rule_id and message)")

        user_lines.append("\nRespond with the JSON object only.")
        return [
            {"role": "system", "content": sys},
            {"role": "user", "content": "\n".join(user_lines)},
        ]

    @abstractmethod
    def cwe_specific_guidance(self) -> str:
        """Return short text guiding the LLM about the CWE class to look for."""
        ...

    def analyze(self, queue_item: Dict[str, Any]) -> EnrichedFinding:
        """Run the agent on a single dispatch queue item."""
        finding = queue_item.get("finding", {}) or {}
        priority = float(queue_item.get("priority", 0.0) or 0.0)

        snippet = read_code_snippet(
            finding.get("file_path", ""),
            int(finding.get("line_start", 0) or 0),
            int(finding.get("line_end", 0) or 0),
        )

        try:
            messages = self.build_prompt(finding, priority, snippet)
        except Exception as e:
            return EnrichedFinding.error_record(self.AGENT_ID, queue_item, f"prompt_build_failed: {e}")

        t0 = time.time()
        try:
            resp = self.llm.chat(messages, model=self.model_name)
        except Exception as e:
            rec = EnrichedFinding.error_record(self.AGENT_ID, queue_item, f"llm_call_failed: {e}")
            rec.latency_ms = int((time.time() - t0) * 1000)
            rec.code_snippet = snippet
            return rec
        latency_ms = int((time.time() - t0) * 1000)

        text = resp.get("text", "")
        parsed = parse_llm_json(text)
        if not parsed:
            rec = EnrichedFinding.error_record(self.AGENT_ID, queue_item, "json_parse_failed")
            rec.reasoning = text[:500]
            rec.model_used = resp.get("model", self.model_name)
            rec.tokens_in = resp.get("tokens_in", 0)
            rec.tokens_out = resp.get("tokens_out", 0)
            rec.latency_ms = latency_ms
            rec.code_snippet = snippet
            return rec

        is_real = bool(parsed.get("is_real_bug", False))
        confidence = clamp01(parsed.get("confidence"), default=(0.5 if is_real else 0.2))
        fpl = clamp01(parsed.get("false_positive_likelihood"),
                      default=(1.0 - confidence))
        precond = parsed.get("preconditions") or []
        if not isinstance(precond, list):
            precond = [str(precond)]
        precond = [str(x)[:300] for x in precond][:10]

        return EnrichedFinding(
            agent_id=self.AGENT_ID,
            finding_id=_finding_id(finding),
            file_path=str(finding.get("file_path", "")),
            line_start=int(finding.get("line_start", 0) or 0),
            line_end=int(finding.get("line_end", 0) or 0),
            cwe=str(finding.get("cwe", "")),
            rule_id=str(finding.get("rule_id", "")),
            layer=str(finding.get("layer", "")),
            static_priority=priority,
            severity=normalize_severity(parsed.get("severity")),
            confidence=confidence,
            false_positive_likelihood=fpl,
            exploit_path=str(parsed.get("exploit_path", ""))[:4000],
            preconditions=precond,
            poc_stub=str(parsed.get("poc_stub", ""))[:4000],
            reasoning=str(parsed.get("reasoning", ""))[:4000],
            model_used=resp.get("model", self.model_name),
            tokens_in=int(resp.get("tokens_in", 0) or 0),
            tokens_out=int(resp.get("tokens_out", 0) or 0),
            latency_ms=latency_ms,
            code_snippet=snippet,
            error=None,
        )
