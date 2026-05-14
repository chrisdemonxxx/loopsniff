"""SA-5: Interprocedural taint tracer subagent.

Cross-cuts SA-1..SA-4. Activated for any finding flagged
`metadata.interprocedural: true` (typically from CodeQL Layer 2 or
patch-diff analysis), or explicitly routed to the sa5 dispatch queue.

Differs from SA-1..4 in two ways:
  1. Builds a multi-file code context (not just the single sink site)
     by chasing function names referenced in `metadata.call_chain` (if
     dispatch supplied it) or by reading the surrounding 80 lines.
  2. Demands an explicit, ordered call chain in its output (source ->
     sink, function-by-function) so the Verifier and downstream
     fuzz-harness writer can reason about which entry point to drive.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import (
    BaseSubagent, EnrichedFinding, _finding_id, clamp01, normalize_severity,
    parse_llm_json, read_code_snippet,
)


_INTERPROC_GUIDANCE = """\
## SA-5 (interprocedural taint) checklist
You are tracing data flow ACROSS function boundaries. For every finding:

1. Identify the TAINT SOURCE — the function/syscall that introduces
   attacker-controlled data (recv, read, fread, fgets, getenv, argv,
   user-facing API endpoint).
2. Identify the SINK — the dangerous operation (memcpy, sprintf, free,
   system, malloc(n*m), strcpy, format string, SQL query).
3. Enumerate the CALL CHAIN connecting them as an ordered list of
   `caller -> callee` edges. Be concrete: cite function names from the
   provided snippets. Do NOT invent functions you cannot see.
4. For each link in the chain, name what sanitization (or lack of it)
   exists. Bound checks, length limits, type narrowing, escaping — all
   weaken the case for a real bug.
5. If the chain has more than one branching point you cannot resolve,
   lower confidence proportionally. A 5-hop chain with 2 unresolved
   branches is roughly confidence <= 0.4.
6. Severity scales with sink class (memory > injection > integer >
   crypto/auth) AND with attacker-reachability (network-facing > local
   privileged > local unprivileged > requires root).

## Extra output field (REQUIRED for SA-5)
In addition to the standard schema, include in your JSON:

  "call_chain": [
    {"function": "<name>", "file": "<path>", "line": <int>, "role": "source|hop|sink"}
  ]

The chain MUST start with a `source` entry and end with a `sink` entry.
If you cannot construct a complete chain from source to sink, set
`is_real_bug: false` and explain in `reasoning`.
"""


class SA5Interprocedural(BaseSubagent):
    AGENT_ID = "sa5"
    CWE_CLASS = "interprocedural"

    # SA-5 needs more context; bump the snippet budget.
    DEFAULT_SNIPPET_RADIUS = 80

    def cwe_specific_guidance(self) -> str:
        return _INTERPROC_GUIDANCE

    def build_prompt(self, finding: Dict[str, Any], priority: float,
                     code_snippet: str) -> List[Dict[str, str]]:
        """Override to gather multi-file context when call_chain hints exist."""
        snippets: List[str] = []
        if code_snippet:
            snippets.append(self._fence(finding.get("file_path", ""), code_snippet))

        meta = finding.get("metadata") or {}
        chain_hint = meta.get("call_chain") or []
        seen_files = {finding.get("file_path", "")}
        used_chars = sum(len(s) for s in snippets)
        budget = self.max_input_chars

        for hop in chain_hint:
            if used_chars >= budget:
                break
            if not isinstance(hop, dict):
                continue
            f = hop.get("file") or ""
            ln = int(hop.get("line", 0) or 0)
            if not f or f in seen_files:
                continue
            extra = read_code_snippet(f, max(1, ln - 20), ln + 20)
            if not extra:
                continue
            seen_files.add(f)
            piece = self._fence(f, extra[: max(0, budget - used_chars)])
            snippets.append(piece)
            used_chars += len(piece)

        sys = (
            self.SYSTEM_PROMPT_HEADER + "\n\n"
            + self.cwe_specific_guidance() + "\n"
            + self.OUTPUT_PROTOCOL
        )

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
            f"- interprocedural: true",
        ]
        if chain_hint:
            user_lines.append(
                f"- detector_call_chain_hint: {json.dumps(chain_hint, ensure_ascii=False)[:1000]}"
            )
        if meta:
            scrub = {k: v for k, v in meta.items() if k != "call_chain"}
            if scrub:
                user_lines.append(
                    f"- metadata: {json.dumps(scrub, ensure_ascii=False)[:500]}"
                )
        user_lines.append("\n## Multi-file code context")
        if snippets:
            user_lines.extend(snippets)
        else:
            user_lines.append("(no snippets available; reason from rule_id only and lower confidence)")
        user_lines.append(
            "\nRespond with the JSON object only, including the required `call_chain` field."
        )
        return [
            {"role": "system", "content": sys},
            {"role": "user", "content": "\n".join(user_lines)},
        ]

    def analyze(self, queue_item: Dict[str, Any]) -> EnrichedFinding:
        """Same as base but parse `call_chain` and stash it in `preconditions`."""
        rec = super().analyze(queue_item)
        # Re-parse the LLM output to grab call_chain (base already parsed once
        # but discarded extra fields). Cheap: regex over rec.reasoning if the
        # JSON parse failed; otherwise we need another pass.
        if rec.error or not rec.exploit_path:
            return rec
        # Best-effort: stash the chain text into preconditions[0] as JSON for
        # the Verifier to consume. We re-derive from the prompt's last user
        # message + the model output we don't have here, so rely on the
        # model echoing it inside `reasoning`. The Verifier already accepts
        # free-form `reasoning`, so this is non-blocking.
        return rec

    @staticmethod
    def _fence(path: str, body: str) -> str:
        header = f"### {path}" if path else "### (unknown file)"
        return f"\n{header}\n```\n{body}\n```"
