"""w910 disclosure pipeline tests."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from harness.subagents.base import EnrichedFinding
from harness.subagents.verifier import VerificationResult
from harness.output import (
    compute_cvss, severity_band, cvss_for_finding, default_vector,
    attack_techniques_for_cwe, ReportWriter,
)


def test_cvss_critical_rce_vector():
    score, vstr = compute_cvss(default_vector("CWE-122"))
    # CVSS:3.1 N/L/N/N/U/H/H/H = 9.8 (critical)
    assert abs(score - 9.8) < 0.05, score
    assert "CVSS:3.1" in vstr
    assert severity_band(score) == "critical"
    print(f"  test_cvss_critical_rce_vector: OK (score={score})")


def test_cvss_dos_only():
    score, _ = compute_cvss(default_vector("CWE-476"))  # NULL deref -> DoS only
    assert 6.5 <= score <= 8.0, score
    assert severity_band(score) == "high" or severity_band(score) == "medium"
    print(f"  test_cvss_dos_only: OK (score={score})")


def test_cvss_overrides_lower_when_local():
    # Same CWE-122 but local-only attack: AV=L
    score, _, band = cvss_for_finding("CWE-122", vector_overrides={"AV": "L"})
    crit_score, _, _ = cvss_for_finding("CWE-122")
    assert score < crit_score, (score, crit_score)
    print(f"  test_cvss_overrides_lower_when_local: OK ({score} < {crit_score})")


def test_cvss_verifier_takes_max():
    # Default for CWE-401 is low; if verifier insists on 8.5, take the max.
    score, _, band = cvss_for_finding("CWE-401", verifier_score=8.5)
    assert score == 8.5, score
    assert band == "high"
    print("  test_cvss_verifier_takes_max: OK")


def test_cvss_severity_band_thresholds():
    assert severity_band(0.0) == "none"
    assert severity_band(3.9) == "low"
    assert severity_band(4.0) == "medium"
    assert severity_band(6.9) == "medium"
    assert severity_band(7.0) == "high"
    assert severity_band(8.9) == "high"
    assert severity_band(9.0) == "critical"
    assert severity_band(10.0) == "critical"
    print("  test_cvss_severity_band_thresholds: OK")


def test_attack_map_known_and_unknown():
    techs = attack_techniques_for_cwe("CWE-78")
    assert any(t["id"] == "T1059" for t in techs)
    assert attack_techniques_for_cwe("CWE-9999") == []
    print("  test_attack_map_known_and_unknown: OK")


def _vr(verified=True, verdict="crash_confirmed", finding_id="abc",
        cwe="CWE-122", crash=None):
    return VerificationResult(
        finding_id=finding_id, agent_id="sa1", cwe=cwe,
        file_path="/src/foo.c",
        verified=verified, confidence=0.9, verdict=verdict,
        reason="Confirmed via fuzzer." if verified else "Rejected.",
        cvss=9.0 if verified else 0.0,
        severity="critical" if verified else "low",
        crash_evidence=crash, llm_used=not crash,
        model_used="Qwen3-Next-80B-A3B-Abliterated",
        tokens_in=500, tokens_out=200, latency_ms=1234,
    )


def _ef(finding_id="abc", cwe="CWE-122"):
    return EnrichedFinding(
        agent_id="sa1", finding_id=finding_id,
        file_path="/src/foo.c", line_start=42, line_end=42,
        cwe=cwe, rule_id="joern.unsafe_memcpy", layer="joern",
        static_priority=0.9, severity="high",
        confidence=0.85, false_positive_likelihood=0.15,
        exploit_path="Attacker controls 4-byte length n via socket.recv, then memcpy(dst,src,n) overflows the 16-byte stack buffer.",
        preconditions=["service exposes TCP port 1234", "no length validation"],
        poc_stub="import socket\npayload = b'\\x00\\x00\\x00\\x40' + b'A'*64\nsocket.socket().sendto(payload,('h',1234))",
        reasoning="recv -> handle_msg -> copy_payload; copy_payload calls memcpy with attacker-controlled size.",
    )


def test_report_writer_verified_crash(tmp_path: Path):
    crash = {"crash_input_sha256": "abcdef", "sanitizer": "asan",
             "crash_type": "heap-buffer-overflow", "crash_address": "0x602000000020",
             "stack_frames": ["#0 vuln() foo.c:42", "#1 main() main.c:10"]}
    vr = _vr(crash=crash)
    ef = _ef()
    w = ReportWriter(tmp_path / "reports", project="libdemo")
    bundle = w.write_one(vr, ef)
    assert bundle is not None
    assert bundle.cvss_score >= 9.0
    assert bundle.cvss_band == "critical"

    bdir = Path(bundle.paths["report_md"]).parent
    for fname in ["report.md", "report.json", "advisory.md", "email.txt",
                  "github_issue.md", "gitlab_issue.md"]:
        assert (bdir / fname).is_file(), fname

    md = (bdir / "report.md").read_text()
    assert "CVSS:3.1/AV:N" in md
    assert "T1203" in md or "T1190" in md
    assert "heap-buffer-overflow" in md
    assert "import socket" in md
    record = json.loads((bdir / "report.json").read_text())
    assert record["cvss"]["band"] == "critical"
    assert record["crash_evidence"]["sanitizer"] == "asan"
    assert record["subagent"]["agent_id"] == "sa1"

    email = (bdir / "email.txt").read_text()
    assert "Subject:" in email
    assert "libdemo" in email
    assert "asan" in email

    print("  test_report_writer_verified_crash: OK")


def test_report_writer_skips_rejected_by_default(tmp_path: Path):
    vr = _vr(verified=False, verdict="llm_rejected")
    w = ReportWriter(tmp_path / "reports", project="libdemo")
    bundle = w.write_one(vr, _ef())
    assert bundle is None
    print("  test_report_writer_skips_rejected_by_default: OK")


def test_report_writer_includes_rejected_when_asked(tmp_path: Path):
    vr = _vr(verified=False, verdict="llm_rejected")
    w = ReportWriter(tmp_path / "reports", project="libdemo",
                     include_rejected=True)
    bundle = w.write_one(vr, _ef())
    assert bundle is not None
    assert bundle.verified is False
    md = Path(bundle.paths["report_md"]).read_text()
    assert "rejected" in md.lower()
    print("  test_report_writer_includes_rejected_when_asked: OK")


def test_report_writer_batch_index(tmp_path: Path):
    crash = {"sanitizer": "asan", "crash_type": "heap-buffer-overflow",
             "crash_address": "0x1", "crash_input_sha256": "x",
             "stack_frames": ["#0 a()"]}
    vrs = [
        _vr(finding_id="f1", cwe="CWE-122", crash=crash),
        _vr(finding_id="f2", cwe="CWE-78"),
        _vr(finding_id="f3", cwe="CWE-401"),
        _vr(finding_id="f4", cwe="CWE-119", verified=False, verdict="llm_rejected"),
    ]
    efs = [_ef(finding_id=v.finding_id, cwe=v.cwe) for v in vrs]
    w = ReportWriter(tmp_path / "reports", project="multi")
    bundles = w.write_batch(vrs, efs)
    assert len(bundles) == 3, len(bundles)  # f4 rejected, skipped
    # sorted descending by CVSS score
    scores = [b.cvss_score for b in bundles]
    assert scores == sorted(scores, reverse=True), scores

    idx_md = (tmp_path / "reports" / "index.md").read_text()
    assert "f1" in idx_md or "Heap-based" in idx_md
    assert "rejected" not in idx_md  # f4 not present

    idx_json = json.loads((tmp_path / "reports" / "index.json").read_text())
    assert len(idx_json) == 3
    assert all("paths" in b for b in idx_json)
    print("  test_report_writer_batch_index: OK")


def test_report_writer_handles_missing_finding(tmp_path: Path):
    """Verifier may emit a result for which we no longer have the EnrichedFinding."""
    vr = _vr(verified=True, verdict="llm_confirmed")
    w = ReportWriter(tmp_path / "reports", project="libdemo")
    bundle = w.write_one(vr, finding=None)
    assert bundle is not None
    md = Path(bundle.paths["report_md"]).read_text()
    assert "CVSS" in md
    print("  test_report_writer_handles_missing_finding: OK")


def main():
    print("=== w910 disclosure tests ===")
    test_cvss_critical_rce_vector()
    test_cvss_dos_only()
    test_cvss_overrides_lower_when_local()
    test_cvss_verifier_takes_max()
    test_cvss_severity_band_thresholds()
    test_attack_map_known_and_unknown()
    with tempfile.TemporaryDirectory() as t:
        test_report_writer_verified_crash(Path(t))
    with tempfile.TemporaryDirectory() as t:
        test_report_writer_skips_rejected_by_default(Path(t))
    with tempfile.TemporaryDirectory() as t:
        test_report_writer_includes_rejected_when_asked(Path(t))
    with tempfile.TemporaryDirectory() as t:
        test_report_writer_batch_index(Path(t))
    with tempfile.TemporaryDirectory() as t:
        test_report_writer_handles_missing_finding(Path(t))
    print("=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
