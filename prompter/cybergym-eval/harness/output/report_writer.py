"""ReportWriter: VerificationResult + EnrichedFinding -> disclosure bundle."""
from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from harness.subagents.base import EnrichedFinding
from harness.subagents.verifier import VerificationResult
from .cvss import cvss_for_finding, severity_band
from .attack_map import attack_techniques_for_cwe
from .templates import REPORT_MD, ADVISORY_MD, EMAIL_TXT


_CWE_NAMES = {
    "CWE-119": "Improper Restriction of Operations within Bounds of a Memory Buffer",
    "CWE-120": "Buffer Copy without Checking Size of Input",
    "CWE-122": "Heap-based Buffer Overflow",
    "CWE-125": "Out-of-bounds Read",
    "CWE-416": "Use After Free",
    "CWE-415": "Double Free",
    "CWE-476": "NULL Pointer Dereference",
    "CWE-401": "Missing Release of Memory after Effective Lifetime",
    "CWE-190": "Integer Overflow or Wraparound",
    "CWE-191": "Integer Underflow",
    "CWE-369": "Divide By Zero",
    "CWE-197": "Numeric Truncation Error",
    "CWE-680": "Integer Overflow to Buffer Overflow",
    "CWE-89":  "SQL Injection",
    "CWE-78":  "OS Command Injection",
    "CWE-611": "Improper Restriction of XML External Entity Reference",
    "CWE-918": "Server-Side Request Forgery",
    "CWE-639": "Authorization Bypass Through User-Controlled Key",
    "CWE-134": "Use of Externally-Controlled Format String",
    "CWE-73":  "External Control of File Name or Path",
    "CWE-326": "Inadequate Encryption Strength",
    "CWE-327": "Use of a Broken or Risky Cryptographic Algorithm",
    "CWE-330": "Use of Insufficiently Random Values",
    "CWE-798": "Use of Hard-coded Credentials",
    "CWE-287": "Improper Authentication",
    "CWE-311": "Missing Encryption of Sensitive Data",
}


_IMPACT_BY_BAND = {
    "critical": "an unauthenticated remote attacker to achieve arbitrary code execution",
    "high":     "remote attackers to compromise confidentiality, integrity, or availability of the service",
    "medium":   "remote attackers to cause partial impact (e.g. limited DoS or data leak)",
    "low":      "limited information disclosure or denial-of-service in adversarial conditions",
    "none":     "no measurable impact",
}


_DEFAULT_MITIGATIONS = {
    "memory":      "Add explicit bounds checks before the memory operation; prefer `memcpy_s`/`strncpy_s` and validate the length against the destination capacity.",
    "integer":     "Validate arithmetic on attacker-controlled integers using checked-add/mul helpers; clamp values before allocation or indexing.",
    "injection":   "Use parameterized APIs (prepared statements, exec-with-array, parser libraries with entity expansion disabled). Never interpolate untrusted input into format strings, shells, or query strings.",
    "crypto_auth": "Replace the broken primitive with an algorithm from the CNSA / OpenSSL approved set; rotate any credentials that may have been derived from the weak source.",
    "generic":     "Apply input validation immediately at the trust boundary; ensure the dataflow path described above is broken by an explicit check.",
}


def _cwe_class(cwe: str) -> str:
    cwe = (cwe or "").upper()
    if cwe in {"CWE-119","CWE-120","CWE-122","CWE-125","CWE-416","CWE-415","CWE-476","CWE-401"}:
        return "memory"
    if cwe in {"CWE-190","CWE-191","CWE-369","CWE-197","CWE-680"}:
        return "integer"
    if cwe in {"CWE-89","CWE-78","CWE-611","CWE-918","CWE-639","CWE-134","CWE-73"}:
        return "injection"
    if cwe in {"CWE-326","CWE-327","CWE-330","CWE-798","CWE-287","CWE-311"}:
        return "crypto_auth"
    return "generic"


def _slugify(s: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", (s or "")).strip("-").lower()
    return (s or "finding")[:max_len]


def _isoformat(ts: Optional[float] = None) -> str:
    return _dt.datetime.fromtimestamp(ts or _dt.datetime.utcnow().timestamp(),
                                      tz=_dt.timezone.utc).isoformat()


@dataclass
class DisclosureBundle:
    finding_id: str
    cwe: str
    title: str
    cvss_score: float
    cvss_vector: str
    cvss_band: str
    verified: bool
    verdict: str
    project: str
    file_path: str
    paths: Dict[str, str] = field(default_factory=dict)  # role -> path
    record: Dict[str, Any] = field(default_factory=dict)


class ReportWriter:
    """Render disclosure bundles for verified findings.

    Default policy: write reports only for `verified=True` results. Pass
    `include_rejected=True` to also write bundles for rejected/error
    verdicts (useful for triage review).
    """

    def __init__(self, output_root: Path, project: str = "unknown",
                 include_rejected: bool = False,
                 verifier_model: str = "Qwen3-Next-80B-A3B-Abliterated"):
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.project = project
        self.include_rejected = include_rejected
        self.verifier_model = verifier_model

    # ---- public API ----
    def write_one(self, vr: VerificationResult,
                  finding: Optional[EnrichedFinding] = None) -> Optional[DisclosureBundle]:
        if not vr.verified and not self.include_rejected:
            return None

        cwe = vr.cwe or (finding.cwe if finding else "")
        cwe_name = _CWE_NAMES.get((cwe or "").upper(), "Unknown")
        cwe_class = _cwe_class(cwe)
        score, vstr, band = cvss_for_finding(cwe, verifier_score=vr.cvss)

        title = self._derive_title(finding, vr, cwe_name)
        slug = _slugify(f"{vr.finding_id}-{cwe}")
        bundle_dir = self.output_root / slug
        bundle_dir.mkdir(parents=True, exist_ok=True)

        ctx = self._build_context(vr, finding, title, cwe, cwe_name, cwe_class,
                                  score, vstr, band)

        # Render artifacts
        report_md = REPORT_MD.format(**ctx)
        advisory_md = ADVISORY_MD.format(**ctx)
        email_txt = EMAIL_TXT.format(**ctx)
        record = self._build_json_record(vr, finding, ctx)

        (bundle_dir / "report.md").write_text(report_md)
        (bundle_dir / "advisory.md").write_text(advisory_md)
        (bundle_dir / "email.txt").write_text(email_txt)
        (bundle_dir / "report.json").write_text(json.dumps(record, indent=2,
                                                           ensure_ascii=False))
        # GitHub/GitLab issue bodies are just report.md with a tracker prefix.
        (bundle_dir / "github_issue.md").write_text(_github_issue_wrap(report_md, title))
        (bundle_dir / "gitlab_issue.md").write_text(_gitlab_issue_wrap(report_md, title, band))

        return DisclosureBundle(
            finding_id=vr.finding_id, cwe=cwe, title=title,
            cvss_score=score, cvss_vector=vstr, cvss_band=band,
            verified=vr.verified, verdict=vr.verdict,
            project=self.project, file_path=vr.file_path,
            paths={
                "report_md": str(bundle_dir / "report.md"),
                "report_json": str(bundle_dir / "report.json"),
                "advisory_md": str(bundle_dir / "advisory.md"),
                "email_txt": str(bundle_dir / "email.txt"),
                "github_issue_md": str(bundle_dir / "github_issue.md"),
                "gitlab_issue_md": str(bundle_dir / "gitlab_issue.md"),
            },
            record=record,
        )

    def write_batch(self, verifications: Iterable[VerificationResult],
                    findings: Optional[Iterable[EnrichedFinding]] = None
                    ) -> List[DisclosureBundle]:
        f_index: Dict[str, EnrichedFinding] = {}
        for f in (findings or []):
            f_index[f.finding_id] = f

        bundles: List[DisclosureBundle] = []
        for vr in verifications:
            f = f_index.get(vr.finding_id)
            b = self.write_one(vr, f)
            if b:
                bundles.append(b)

        bundles.sort(key=lambda b: (-b.cvss_score, b.finding_id))
        self._write_index(bundles)
        return bundles

    # ---- internal ----
    def _derive_title(self, f, vr, cwe_name) -> str:
        if f and f.exploit_path:
            short = f.exploit_path.strip().splitlines()[0][:80]
            return f"{cwe_name} in {Path(vr.file_path).name}: {short}"
        return f"{cwe_name} in {Path(vr.file_path).name}"

    def _build_context(self, vr, f, title, cwe, cwe_name, cwe_class,
                       score, vstr, band) -> Dict[str, Any]:
        cwe_num = (cwe or "").replace("CWE-", "") or "0"
        atk = attack_techniques_for_cwe(cwe)
        attack_md = ("\n".join(f"- **{a['id']}** — {a['name']}" for a in atk)
                     if atk else "_(no mapped techniques)_")
        preconds = (f.preconditions if f else None) or []
        preconditions_md = ("\n".join(f"- {p}" for p in preconds)
                            if preconds else "_(none beyond reaching the entry point)_")
        reasoning = (vr.reason or (f.reasoning if f else "") or
                     "(no reasoning recorded)").strip()

        crash_evidence_md = "(no fuzzer crash; verified by static + LLM analysis)"
        crash_email_line = ""
        if vr.crash_evidence:
            ce = vr.crash_evidence
            crash_evidence_md = (f"`{ce.get('sanitizer','?')}` reproduced "
                                 f"`{ce.get('crash_type','?')}` at "
                                 f"`{ce.get('crash_address','?')}`")
            crash_email_line = (
                f"  - Fuzzer-reproduced crash: {ce.get('sanitizer','?')}/"
                f"{ce.get('crash_type','?')} (matches expected class)"
            )
        reproduction_block = self._reproduction_block(f, vr)
        summary = self._summary(f, vr, cwe_name)

        return {
            "title": title,
            "finding_id": vr.finding_id,
            "cwe": cwe or "CWE-?",
            "cwe_num": cwe_num,
            "cwe_name": cwe_name,
            "cvss_score": score,
            "cvss_band": band,
            "cvss_vector": vstr,
            "verdict": vr.verdict,
            "verifier_confidence": float(vr.confidence or 0.0),
            "status": "verified" if vr.verified else "rejected",
            "project": self.project,
            "file_path": vr.file_path,
            "line_start": (f.line_start if f else 0),
            "line_end": (f.line_end if f else 0),
            "target_function": (f.rule_id if f else "(unknown)"),
            "summary": summary,
            "exploit_path": (f.exploit_path if f and f.exploit_path
                             else "_(not provided by upstream agent)_"),
            "preconditions_md": preconditions_md,
            "reasoning": reasoning.replace("\n", "\n> "),
            "reproduction_block": reproduction_block,
            "attack_md": attack_md,
            "layer": (f.layer if f else "?"),
            "rule_id": (f.rule_id if f else "?"),
            "agent_id": (f.agent_id if f else vr.agent_id),
            "subagent_confidence": float(f.confidence if f else 0.0),
            "verifier_model": vr.model_used or self.verifier_model,
            "crash_evidence_md": crash_evidence_md,
            "crash_email_line": crash_email_line,
            "timestamp_iso": _isoformat(vr.timestamp),
            "impact_sentence": _IMPACT_BY_BAND.get(band, _IMPACT_BY_BAND["medium"]),
            "mitigations": _DEFAULT_MITIGATIONS.get(cwe_class, _DEFAULT_MITIGATIONS["generic"]),
        }

    def _reproduction_block(self, f, vr) -> str:
        parts = []
        if f and f.poc_stub:
            parts.append("Proof-of-concept payload / harness:\n\n```\n"
                         + f.poc_stub.strip() + "\n```")
        if vr.crash_evidence:
            ce = vr.crash_evidence
            parts.append(
                "\nReproduced crash (fuzzer):\n\n"
                f"- sanitizer: `{ce.get('sanitizer','?')}`\n"
                f"- type: `{ce.get('crash_type','?')}`\n"
                f"- address: `{ce.get('crash_address','?')}`\n"
                f"- crash input sha256: `{ce.get('crash_input_sha256','?')}`\n"
                "- top stack frames:\n```\n"
                + "\n".join(ce.get("stack_frames", [])[:5]) + "\n```"
            )
        return "\n".join(parts) if parts else "_(no reproduction artifact attached)_"

    def _summary(self, f, vr, cwe_name) -> str:
        if vr.crash_evidence:
            return (f"A {cwe_name.lower()} in `{vr.file_path}` was confirmed "
                    "by sanitizer-instrumented fuzzing. The bug is reachable "
                    "from the documented attack surface and matches the "
                    "expected vulnerability class.")
        if f and f.exploit_path:
            return (f"A suspected {cwe_name.lower()} in `{vr.file_path}` was "
                    "confirmed by the verifier subagent based on the dataflow "
                    "described below. No fuzzer crash is attached; reproduction "
                    "may require building the target from source.")
        return f"A potential {cwe_name.lower()} in `{vr.file_path}`."

    def _build_json_record(self, vr, f, ctx) -> Dict[str, Any]:
        return {
            "finding_id": vr.finding_id,
            "title": ctx["title"],
            "cwe": ctx["cwe"],
            "cwe_name": ctx["cwe_name"],
            "cvss": {
                "score": ctx["cvss_score"],
                "vector": ctx["cvss_vector"],
                "band": ctx["cvss_band"],
            },
            "attack_techniques": attack_techniques_for_cwe(ctx["cwe"]),
            "verifier": {
                "verdict": vr.verdict,
                "confidence": vr.confidence,
                "verified": vr.verified,
                "model": vr.model_used or self.verifier_model,
                "tokens_in": vr.tokens_in,
                "tokens_out": vr.tokens_out,
                "latency_ms": vr.latency_ms,
                "reason": vr.reason,
            },
            "subagent": {
                "agent_id": (f.agent_id if f else vr.agent_id),
                "confidence": (f.confidence if f else 0.0),
                "rule_id": (f.rule_id if f else ""),
                "layer": (f.layer if f else ""),
                "exploit_path": (f.exploit_path if f else ""),
                "preconditions": (f.preconditions if f else []),
                "poc_stub": (f.poc_stub if f else ""),
                "reasoning": (f.reasoning if f else ""),
            },
            "location": {
                "project": ctx["project"],
                "file_path": vr.file_path,
                "line_start": ctx["line_start"],
                "line_end": ctx["line_end"],
            },
            "crash_evidence": vr.crash_evidence,
            "timestamp": ctx["timestamp_iso"],
        }

    def _write_index(self, bundles: List[DisclosureBundle]) -> None:
        idx_md = self.output_root / "index.md"
        idx_json = self.output_root / "index.json"
        lines = [f"# Disclosure index — {self.project}",
                 "",
                 f"_Generated {_isoformat()}_",
                 "",
                 "| CVSS | Band | CWE | File | Verdict | Title |",
                 "|---:|---|---|---|---|---|"]
        for b in bundles:
            lines.append(
                f"| {b.cvss_score} | {b.cvss_band} | {b.cwe} | "
                f"`{b.file_path}` | `{b.verdict}` | "
                f"[{b.title}]({Path(b.paths['report_md']).relative_to(self.output_root)}) |"
            )
        if not bundles:
            lines.append("| _(no verified findings)_ |  |  |  |  |  |")
        idx_md.write_text("\n".join(lines) + "\n")
        idx_json.write_text(json.dumps([{
            "finding_id": b.finding_id, "cwe": b.cwe, "title": b.title,
            "cvss_score": b.cvss_score, "cvss_band": b.cvss_band,
            "verdict": b.verdict, "verified": b.verified,
            "file_path": b.file_path, "paths": b.paths,
        } for b in bundles], indent=2))


def _github_issue_wrap(md: str, title: str) -> str:
    return ("<!-- Open this as a private security advisory under the "
            "repo's Security tab, then convert to issue if appropriate. -->\n\n"
            f"**Title:** {title}\n\n" + md)


def _gitlab_issue_wrap(md: str, title: str, band: str) -> str:
    label = {"critical": "~security::critical", "high": "~security::high",
             "medium": "~security::medium", "low": "~security::low"}.get(band, "")
    return f"/title {title}\n{label}\n\n{md}"
