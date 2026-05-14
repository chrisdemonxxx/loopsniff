"""Tests for w46: SA-5 interprocedural tracer + Verifier subagent."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from harness.subagents import (
    SA5Interprocedural, Verifier, VerificationResult,
    EnrichedFinding, MockLLMClient, SubagentOrchestrator,
)
from harness.subagents.llm_client import MockLLMClient as MLC


# ---------- helpers ----------

def _enriched(agent_id="sa1", cwe="CWE-122", confidence=0.85, finding_id=None):
    return EnrichedFinding(
        agent_id=agent_id,
        finding_id=finding_id or f"fid-{cwe}-{agent_id}",
        file_path="/tmp/x.c",
        line_start=10, line_end=12,
        cwe=cwe, rule_id="r1", layer="joern",
        static_priority=0.8,
        severity="high",
        confidence=confidence,
        false_positive_likelihood=1.0 - confidence,
        exploit_path="Attacker controls n via socket.recv, calls into helper which memcpys n bytes into 16-byte stack buf.",
        preconditions=["service exposes port"],
        poc_stub="b'\\x00\\x00\\x00\\x40' + b'A'*64",
        reasoning="recv -> handle_msg -> copy_payload, no length check at hop 2.",
        code_snippet="int handle(...) { recv(s,&n,4); copy(n); }",
    )


def _crash(finding_id, matches=True, sanitizer="asan", crash_type="heap-buffer-overflow",
           severity="high"):
    return {
        "job_id": "j1",
        "finding_id": finding_id,
        "cwe": "CWE-122",
        "crash_input_path": "/tmp/c.bin",
        "crash_input_sha256": "deadbeef",
        "sanitizer": sanitizer,
        "crash_type": crash_type,
        "crash_address": "0x602000000020",
        "stack_frames": ["#0 vuln() x.c:42"],
        "matches_expected": matches,
        "duration_s": 1.0,
        "severity": severity,
    }


# ---------- SA-5 ----------

def test_sa5_subagent_runs_with_mock():
    llm = MLC()
    agent = SA5Interprocedural(llm)
    queue_item = {
        "finding": {
            "file_path": "/tmp/nonexistent.c",
            "line_start": 5, "line_end": 5,
            "cwe": "CWE-416", "rule_id": "codeql.uaf.interproc",
            "layer": "codeql", "severity": "high",
            "message": "use-after-free across function boundary",
            "metadata": {
                "interprocedural": True,
                "call_chain": [
                    {"function": "recv_packet", "file": "/tmp/net.c", "line": 100},
                    {"function": "free_packet", "file": "/tmp/util.c", "line": 50},
                    {"function": "log_packet", "file": "/tmp/log.c", "line": 20},
                ],
            },
        },
        "priority": 0.9,
    }
    rec = agent.analyze(queue_item)
    assert rec.agent_id == "sa5", rec.agent_id
    assert rec.cwe == "CWE-416"
    assert rec.error is None or "json" in (rec.error or "")
    assert llm.calls == 1
    print("  test_sa5_subagent_runs_with_mock: OK")


def test_sa5_prompt_includes_interproc_marker():
    agent = SA5Interprocedural(MLC())
    msgs = agent.build_prompt(
        {"file_path": "/tmp/x.c", "line_start": 1, "line_end": 1,
         "cwe": "CWE-416", "rule_id": "r", "layer": "codeql",
         "severity": "high", "message": "uaf",
         "metadata": {"interprocedural": True,
                      "call_chain": [{"function": "f", "file": "/x", "line": 1}]}},
        priority=0.9, code_snippet="void f(){}",
    )
    user = msgs[-1]["content"]
    assert "interprocedural: true" in user
    assert "call_chain" in msgs[0]["content"], "guidance must mention call_chain"
    assert "detector_call_chain_hint" in user
    print("  test_sa5_prompt_includes_interproc_marker: OK")


def test_sa5_orchestrator_registry():
    """SA-5 must be discoverable via the orchestrator registry."""
    from harness.subagents.orchestrator import AGENT_REGISTRY
    assert "sa5" in AGENT_REGISTRY
    assert AGENT_REGISTRY["sa5"] is SA5Interprocedural
    print("  test_sa5_orchestrator_registry: OK")


def test_sa5_orchestrator_runs_sa5_queue(tmp_path: Path):
    dispatch = tmp_path / "dispatch"
    dispatch.mkdir()
    (dispatch / "sa5.jsonl").write_text(json.dumps({
        "finding": {"file_path": "/tmp/x.c", "line_start": 1, "line_end": 1,
                    "cwe": "CWE-416", "rule_id": "r", "layer": "codeql",
                    "severity": "high", "message": "uaf",
                    "metadata": {"interprocedural": True}},
        "priority": 0.85,
    }) + "\n")
    out = tmp_path / "out"
    orch = SubagentOrchestrator(MLC(), output_dir=out, budget_usd=1.0,
                                max_findings_per_agent=5)
    res = orch.run_from_dispatch_dir(dispatch, agents=["sa5"])
    assert "sa5" in res
    assert res["sa5"].total >= 1
    enriched_file = out / "sa5_enriched.jsonl"
    assert enriched_file.is_file()
    print("  test_sa5_orchestrator_runs_sa5_queue: OK")


# ---------- Verifier ----------

def test_verifier_crash_confirmed_short_circuit():
    v = Verifier(MLC())
    f = _enriched(confidence=0.6, finding_id="fid-A")
    crashes = [_crash("fid-A", matches=True)]
    r = v.verify(f, crashes)
    assert r.verified is True, r.verdict
    assert r.verdict == "crash_confirmed"
    assert r.confidence >= 0.9
    assert r.cvss >= 7.0
    assert r.crash_evidence is not None
    assert r.llm_used is False
    assert v.llm.calls == 0  # crash short-circuit -> no LLM call
    print("  test_verifier_crash_confirmed_short_circuit: OK")


def test_verifier_crash_mismatch():
    v = Verifier(MLC())
    f = _enriched(confidence=0.9, finding_id="fid-B")
    crashes = [_crash("fid-B", matches=False, crash_type="signed-integer-overflow",
                      sanitizer="ubsan")]
    r = v.verify(f, crashes)
    assert r.verified is False
    assert r.verdict == "crash_mismatch"
    assert r.cvss == 0.0
    assert v.llm.calls == 0
    print("  test_verifier_crash_mismatch: OK")


def test_verifier_low_confidence_short_circuit():
    v = Verifier(MLC(), skip_llm_below_confidence=0.5)
    f = _enriched(confidence=0.3, finding_id="fid-C")
    r = v.verify(f, crashes=[])
    assert r.verified is False
    assert r.verdict == "static_low_confidence"
    assert v.llm.calls == 0
    print("  test_verifier_low_confidence_short_circuit: OK")


def test_verifier_llm_judge_confirms():
    fixed = '```json\n{"verified": true, "confidence": 0.8, "cvss": 8.0, "severity": "high", "reason": "ok"}\n```'
    v = Verifier(MLC(fixed_text=fixed))
    f = _enriched(confidence=0.9, finding_id="fid-D")
    r = v.verify(f, crashes=[])
    assert r.verified is True, r.verdict
    assert r.verdict == "llm_confirmed"
    assert abs(r.cvss - 8.0) < 0.01
    assert r.severity == "high"
    assert v.llm.calls == 1
    print("  test_verifier_llm_judge_confirms: OK")


def test_verifier_llm_judge_rejects():
    fixed = '```json\n{"verified": false, "confidence": 0.7, "cvss": 5.0, "severity": "medium", "reason": "no source"}\n```'
    v = Verifier(MLC(fixed_text=fixed))
    f = _enriched(confidence=0.9, finding_id="fid-E")
    r = v.verify(f, crashes=[])
    assert r.verified is False
    assert r.verdict == "llm_rejected"
    assert r.cvss == 0.0  # zero on rejection regardless of model output
    print("  test_verifier_llm_judge_rejects: OK")


def test_verifier_handles_bad_json():
    v = Verifier(MLC(fixed_text="not json"))
    f = _enriched(confidence=0.9, finding_id="fid-F")
    r = v.verify(f, crashes=[])
    assert r.verdict == "error"
    assert r.verified is False
    print("  test_verifier_handles_bad_json: OK")


def test_verifier_batch_and_io_roundtrip(tmp_path: Path):
    enriched_path = tmp_path / "sa1_enriched.jsonl"
    findings = [
        _enriched(confidence=0.9, finding_id="bf-1"),
        _enriched(confidence=0.4, finding_id="bf-2"),
    ]
    enriched_path.write_text("\n".join(f.to_json() for f in findings))

    crashes_path = tmp_path / "crashes.jsonl"
    crashes_path.write_text(json.dumps(_crash("bf-1", matches=True)) + "\n")

    loaded_f = Verifier.load_enriched_jsonl(enriched_path)
    loaded_c = Verifier.load_crashes_jsonl(crashes_path)
    assert len(loaded_f) == 2
    assert len(loaded_c) == 1

    v = Verifier(MLC(fixed_text='```json\n{"verified": true, "confidence": 0.7, "cvss": 7.0, "severity": "high", "reason": "ok"}\n```'))
    results = v.verify_batch(loaded_f, loaded_c)
    assert len(results) == 2
    assert results[0].verdict == "crash_confirmed"
    assert results[1].verdict == "static_low_confidence"  # confidence 0.4 < 0.5

    out_path = tmp_path / "verifications.jsonl"
    v.write_results_jsonl(results, out_path)
    lines = out_path.read_text().strip().split("\n")
    assert len(lines) == 2
    parsed = json.loads(lines[0])
    assert parsed["finding_id"] == "bf-1"
    assert parsed["verified"] is True
    print("  test_verifier_batch_and_io_roundtrip: OK")


def test_verifier_match_crashes_isolation():
    v = Verifier(MLC())
    f = _enriched(finding_id="alpha")
    crashes = [_crash("beta"), _crash("alpha"), _crash("gamma")]
    matched = v.match_crashes(f, crashes)
    assert len(matched) == 1
    assert matched[0]["finding_id"] == "alpha"
    print("  test_verifier_match_crashes_isolation: OK")


def main():
    print("=== w46 SA-5 + Verifier tests ===")
    test_sa5_subagent_runs_with_mock()
    test_sa5_prompt_includes_interproc_marker()
    test_sa5_orchestrator_registry()
    with tempfile.TemporaryDirectory() as t:
        test_sa5_orchestrator_runs_sa5_queue(Path(t))
    test_verifier_crash_confirmed_short_circuit()
    test_verifier_crash_mismatch()
    test_verifier_low_confidence_short_circuit()
    test_verifier_llm_judge_confirms()
    test_verifier_llm_judge_rejects()
    test_verifier_handles_bad_json()
    with tempfile.TemporaryDirectory() as t:
        test_verifier_batch_and_io_roundtrip(Path(t))
    test_verifier_match_crashes_isolation()
    print("=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
