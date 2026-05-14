"""End-to-end smoke test for the subagent framework. Offline (MockLLMClient)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from harness.subagents import (
    EnrichedFinding, MockLLMClient, SubagentOrchestrator,
    SA1Memory, SA2Integer, SA3Injection, SA4Crypto,
)
from harness.subagents.base import parse_llm_json, normalize_severity, clamp01


def _sample_queue_item(cwe: str, file_path: str, line: int, rule_id: str) -> dict:
    return {
        "finding": {
            "layer": "joern",
            "file_path": file_path,
            "line_start": line,
            "line_end": line,
            "rule_id": rule_id,
            "severity": "high",
            "message": f"Test finding for {cwe}",
            "cwe": cwe,
            "confidence": "high",
            "metadata": {"interprocedural": False},
        },
        "priority": 0.8,
    }


def _make_demo_source(tmp: Path) -> Path:
    src = tmp / "demo.c"
    src.write_text(
        "#include <string.h>\n"
        "void copy(char *dst, const char *src, size_t n) {\n"
        "    char buf[16];\n"
        "    memcpy(buf, src, n);\n"
        "    strcpy(dst, buf);\n"
        "}\n"
    )
    return src


def test_parse_llm_json_fenced():
    text = "stuff\n```json\n{\"a\": 1, \"b\": \"x\"}\n```\nmore"
    obj = parse_llm_json(text)
    assert obj == {"a": 1, "b": "x"}, obj


def test_parse_llm_json_bare():
    text = "{\"a\": 1, \"nested\": {\"k\": 2}} trailing garbage"
    obj = parse_llm_json(text)
    assert obj == {"a": 1, "nested": {"k": 2}}, obj


def test_parse_llm_json_failure():
    assert parse_llm_json("no json here") == {}


def test_normalize_and_clamp():
    assert normalize_severity("HIGH") == "high"
    assert normalize_severity("crit") == "critical"
    assert normalize_severity(None) == "unknown"
    assert clamp01(1.5) == 1.0
    assert clamp01(-0.2) == 0.0
    assert clamp01("nope", default=0.3) == 0.3


def test_each_agent_processes_one():
    client = MockLLMClient()
    cases = [
        (SA1Memory, "CWE-416", "joern.use_after_free"),
        (SA2Integer, "CWE-190", "codeql.integer_overflow"),
        (SA3Injection, "CWE-89", "semgrep.sqli"),
        (SA4Crypto, "CWE-798", "semgrep.hardcoded_secret"),
    ]
    for cls, cwe, rule in cases:
        agent = cls(client)
        item = _sample_queue_item(cwe, "/nonexistent/file.c", 10, rule)
        rec = agent.analyze(item)
        assert isinstance(rec, EnrichedFinding), cwe
        assert rec.error is None, f"{cwe} agent errored: {rec.error}"
        assert rec.agent_id == cls.AGENT_ID
        assert rec.cwe == cwe
        assert rec.severity in ("critical", "high", "medium", "low", "unknown"), rec.severity
        assert 0.0 <= rec.confidence <= 1.0
        assert rec.poc_stub, f"{cwe} produced empty poc_stub"
    print("  test_each_agent_processes_one: OK")


def test_orchestrator_parallel(tmp_path: Path):
    src = _make_demo_source(tmp_path)
    queues = {
        "sa1": [_sample_queue_item("CWE-416", str(src), 4, "joern.use_after_free"),
                _sample_queue_item("CWE-122", str(src), 4, "joern.heap_overflow")],
        "sa2": [_sample_queue_item("CWE-190", str(src), 3, "codeql.int_overflow")],
        "sa3": [_sample_queue_item("CWE-134", str(src), 5, "custom.format_string")],
        "sa4": [_sample_queue_item("CWE-327", str(src), 2, "semgrep.weak_crypto")],
    }
    out = tmp_path / "results"
    orch = SubagentOrchestrator(
        llm_client=MockLLMClient(),
        budget_usd=10.0,
        max_findings_per_agent=10,
        output_dir=out,
    )
    results = orch.run(queues)

    assert set(results.keys()) == {"sa1", "sa2", "sa3", "sa4"}, list(results.keys())
    assert results["sa1"].total == 2
    assert all(r.errors == 0 for r in results.values()), \
        {a: r.errors for a, r in results.items()}

    for aid in ("sa1", "sa2", "sa3", "sa4"):
        f = out / f"{aid}_enriched.jsonl"
        assert f.exists(), f
        rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        assert len(rows) == results[aid].total
        for r in rows:
            assert r["agent_id"] == aid
            assert r["error"] is None
        sm = json.loads((out / f"{aid}_summary.json").read_text())
        assert sm["agent_id"] == aid
        assert sm["ok"] == results[aid].total

    code_seen = any(
        ">>     4 |" in e.code_snippet
        for e in results["sa1"].enriched
    )
    assert code_seen, "expected snippet markers around line 4"

    print(f"  test_orchestrator_parallel: OK ({sum(r.total for r in results.values())} findings, "
          f"${sum(r.estimated_cost_usd for r in results.values()):.5f})")


def test_budget_cap():
    client = MockLLMClient()
    queues = {"sa1": [_sample_queue_item("CWE-416", "/x.c", 1, "r")] * 5}
    orch = SubagentOrchestrator(
        llm_client=client, budget_usd=0.0, max_findings_per_agent=10,
        output_dir=Path(tempfile.mkdtemp()),
    )
    results = orch.run(queues)
    errs = [e for e in results["sa1"].enriched if e.error and e.error.startswith("budget_exceeded")]
    assert len(errs) == 5, errs
    print("  test_budget_cap: OK")


def test_consume_real_dispatch_dir(tmp_path: Path):
    src = _make_demo_source(tmp_path)
    dispatch = tmp_path / "dispatch_queues"
    dispatch.mkdir()
    (dispatch / "sa1.jsonl").write_text(
        json.dumps(_sample_queue_item("CWE-122", str(src), 4, "joern.overflow")) + "\n"
    )
    (dispatch / "sa3.jsonl").write_text(
        json.dumps(_sample_queue_item("CWE-89", str(src), 2, "semgrep.sqli")) + "\n"
    )
    out = tmp_path / "out"
    orch = SubagentOrchestrator(llm_client=MockLLMClient(), output_dir=out)
    results = orch.run_from_dispatch_dir(dispatch, agents=["sa1", "sa2", "sa3", "sa4"])
    assert results["sa1"].total == 1
    assert results["sa2"].total == 0
    assert results["sa3"].total == 1
    assert results["sa4"].total == 0
    print("  test_consume_real_dispatch_dir: OK")


def main():
    print("=== subagent framework smoke tests ===")
    test_parse_llm_json_fenced()
    test_parse_llm_json_bare()
    test_parse_llm_json_failure()
    test_normalize_and_clamp()
    print("  parser/util tests: OK")
    test_each_agent_processes_one()
    with tempfile.TemporaryDirectory() as t:
        test_orchestrator_parallel(Path(t))
    test_budget_cap()
    with tempfile.TemporaryDirectory() as t:
        test_consume_real_dispatch_dir(Path(t))
    print("=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
