"""End-to-end smoke tests for the w78 fuzzer handoff layer. Offline (no clang needed)."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from harness.fuzzer import (
    FuzzJobSpec, HarnessWriter, SeedExtractor, JobBuilder, CrashTriage, LocalRunner,
)
from harness.fuzzer.seed_corpus import extract_seed_bytes
from harness.fuzzer.harness_writer import _CWE_BODY_TEMPLATES


def _enriched(agent_id="sa1", cwe="CWE-122", confidence=0.9, poc_stub=""):
    return {
        "agent_id": agent_id,
        "finding_id": f"finding-{cwe}-x",
        "file_path": "/tmp/demo.c",
        "line_start": 6,
        "line_end": 6,
        "cwe": cwe,
        "rule_id": "joern.unsafe_memcpy",
        "layer": "joern",
        "static_priority": 0.85,
        "severity": "high",
        "confidence": confidence,
        "false_positive_likelihood": 1 - confidence,
        "exploit_path": "Attacker sends 4-byte length prefix then payload to overflow buf[16].",
        "preconditions": ["network reachable", "no length validation"],
        "poc_stub": poc_stub or (
            "import socket\n"
            "payload = b''\n"
            "payload += b'\\x00\\x00\\x00\\x20'\n"
            "payload += b'A' * 32\n"
            "sock = socket.socket()\n"
            "sock.connect(('localhost', 12345))\n"
            "sock.send(payload)\n"
        ),
        "reasoning": "Confirmed: n is read from socket and passed unchecked to memcpy.",
        "error": None,
    }


def test_seed_extraction_python_bytes():
    stub = "payload = b'\\x00\\x00\\x00\\x20' + b'A' * 32\nsock.send(payload)"
    seeds = extract_seed_bytes(stub)
    assert seeds, "expected at least one seed"
    joined = b"".join(seeds)
    assert b"\x00\x00\x00\x20" in joined, "first 4-byte prefix not extracted"
    print("  test_seed_extraction_python_bytes: OK")


def test_seed_extraction_hex():
    stub = "payload = bytes.fromhex('41414141deadbeefcafebabe')"
    seeds = extract_seed_bytes(stub)
    assert any(b"\xde\xad\xbe\xef" in s or b"AAAA" in s for s in seeds)
    print("  test_seed_extraction_hex: OK")


def test_seed_extraction_fallback():
    stub = "no payload here, just prose"
    seeds = extract_seed_bytes(stub)
    assert seeds, "expected fallback seed"
    assert seeds[0].startswith(b"no payload"), seeds[0][:20]
    print("  test_seed_extraction_fallback: OK")


def test_seed_extraction_empty():
    assert extract_seed_bytes("") == []
    print("  test_seed_extraction_empty: OK")


def test_harness_writer_renders_all_classes():
    writer = HarnessWriter(time_budget_s=120, memory_limit_mb=1024)
    for agent, cwe in [("sa1", "CWE-122"), ("sa2", "CWE-190"),
                       ("sa3", "CWE-134"), ("sa4", "CWE-327")]:
        # Inject expected_crash + seed_count fields normally added by JobBuilder
        rec = {**_enriched(agent_id=agent, cwe=cwe),
               "expected_crash": {"sanitizer": "asan", "summary": "test"},
               "seed_count": 3,
               "sanitizers": ["address", "undefined"]}
        files = writer.render_files(rec)
        assert "harness.c" in files
        assert "LLVMFuzzerTestOneInput" in files["harness.c"]
        assert "build.sh" in files
        assert "run.sh" in files
        assert "README.md" in files
        assert "clang" in files["build.sh"]
        assert "fuzz_target" in files["run.sh"]
        assert files["_target_function"], cwe
    print("  test_harness_writer_renders_all_classes: OK")


def test_job_builder_end_to_end(tmp_path: Path):
    enriched_jsonl = tmp_path / "sa1_enriched.jsonl"
    rows = [
        _enriched(agent_id="sa1", cwe="CWE-122", confidence=0.9),
        _enriched(agent_id="sa1", cwe="CWE-416", confidence=0.85),
        _enriched(agent_id="sa1", cwe="CWE-125", confidence=0.2),  # below threshold
    ]
    enriched_jsonl.write_text("\n".join(json.dumps(r) for r in rows))

    out = tmp_path / "jobs"
    builder = JobBuilder(out, time_budget_s=60, memory_limit_mb=512, min_confidence=0.4)
    specs = builder.build_from_jsonl(enriched_jsonl)
    assert len(specs) == 2, f"expected 2 jobs (1 filtered low-confidence), got {len(specs)}"

    for s in specs:
        d = out / s.job_id
        assert d.is_dir()
        assert (d / "harness.c").is_file()
        assert (d / "build.sh").is_file()
        assert (d / "run.sh").is_file()
        assert (d / "README.md").is_file()
        assert (d / "spec.json").is_file()
        seeds = list((d / "seeds").glob("*.bin"))
        assert seeds, f"no seeds extracted for {s.job_id}"
        assert (d / "build.sh").stat().st_mode & 0o111, "build.sh not executable"
        assert (d / "run.sh").stat().st_mode & 0o111, "run.sh not executable"
        spec_loaded = FuzzJobSpec.from_dir(d)
        assert spec_loaded.job_id == s.job_id
        assert spec_loaded.cwe == s.cwe
    print(f"  test_job_builder_end_to_end: OK ({len(specs)} jobs)")


def test_job_builder_from_subagent_results(tmp_path: Path):
    results_dir = tmp_path / "subagent_results"
    results_dir.mkdir()
    (results_dir / "sa1_enriched.jsonl").write_text(
        json.dumps(_enriched("sa1", "CWE-122")) + "\n"
    )
    (results_dir / "sa3_enriched.jsonl").write_text(
        json.dumps(_enriched("sa3", "CWE-134")) + "\n"
    )
    out = tmp_path / "jobs"
    builder = JobBuilder(out, time_budget_s=30)
    by_agent = builder.build_from_dir(results_dir)
    assert len(by_agent.get("sa1", [])) == 1
    assert len(by_agent.get("sa3", [])) == 1
    assert len(by_agent.get("sa2", [])) == 0
    manifest = out / "manifest.json"
    assert manifest.is_file()
    m = json.loads(manifest.read_text())
    assert "sa1" in m and "sa3" in m
    print("  test_job_builder_from_subagent_results: OK")


def test_crash_triage_asan_match():
    log = (
        "==12345==ERROR: AddressSanitizer: heap-buffer-overflow on address "
        "0x602000000020 at pc 0x000000123456\n"
        "  #0 0xdeadbeef in vulnerable_function /src/foo.c:42\n"
        "  #1 0xcafebabe in main /src/main.c:10\n"
        "SUMMARY: AddressSanitizer: heap-buffer-overflow"
    )
    spec = FuzzJobSpec(
        job_id="abc", finding_id="f1", cwe="CWE-122",
        target_file="/src/foo.c", target_lines=[42],
        target_function="vulnerable_function",
        sanitizers=["address"], fuzzer="libfuzzer",
        harness_filename="harness.c", seed_count=1,
        expected_crash={"sanitizer": "asan", "summary": "heap-buffer-overflow"},
        build_cmd="./build.sh", run_cmd="./run.sh",
        time_budget_s=60, memory_limit_mb=512,
    )
    triage = CrashTriage()
    rec = triage.parse(log, spec)
    assert rec is not None
    assert rec.sanitizer == "asan"
    assert rec.crash_type == "heap-buffer-overflow"
    assert rec.crash_address == "0x602000000020"
    assert rec.matches_expected is True
    assert rec.severity == "high"
    assert any("vulnerable_function" in f for f in rec.stack_frames)
    print("  test_crash_triage_asan_match: OK")


def test_crash_triage_ubsan_no_match():
    log = "SUMMARY: UndefinedBehaviorSanitizer: signed-integer-overflow /src/x.c:9:5"
    spec = FuzzJobSpec(
        job_id="x", finding_id="f", cwe="CWE-122",
        target_file="x.c", target_lines=[9], target_function="fn",
        sanitizers=["address"], fuzzer="libfuzzer",
        harness_filename="harness.c", seed_count=1,
        expected_crash={"sanitizer": "asan", "summary": "heap-buffer-overflow"},
        build_cmd="./build.sh", run_cmd="./run.sh",
        time_budget_s=60, memory_limit_mb=512,
    )
    rec = CrashTriage().parse(log, spec)
    assert rec is not None
    assert rec.sanitizer == "ubsan"
    # Different sanitizer than expected -> no match
    assert rec.matches_expected is False
    print("  test_crash_triage_ubsan_no_match: OK")


def test_crash_triage_no_crash():
    log = "INFO: libFuzzer ran 100 iterations, no crashes."
    spec = FuzzJobSpec(
        job_id="x", finding_id="f", cwe="CWE-122",
        target_file="x.c", target_lines=[1], target_function="fn",
        sanitizers=["address"], fuzzer="libfuzzer",
        harness_filename="harness.c", seed_count=1,
        expected_crash={}, build_cmd="./build.sh", run_cmd="./run.sh",
        time_budget_s=60, memory_limit_mb=512,
    )
    rec = CrashTriage().parse(log, spec)
    assert rec is None
    print("  test_crash_triage_no_crash: OK")


def test_local_runner_skip_if_no_clang(tmp_path: Path):
    runner = LocalRunner(clang_bin="/nonexistent/clang")
    # Manually set so can_run returns False even if system has clang
    runner.clang_bin = None
    res = runner.build_and_run(tmp_path)
    assert res["build_ok"] is False
    assert res["error"] == "clang not found on PATH"
    print("  test_local_runner_skip_if_no_clang: OK")


def main():
    print("=== w78 fuzzer handoff smoke tests ===")
    test_seed_extraction_python_bytes()
    test_seed_extraction_hex()
    test_seed_extraction_fallback()
    test_seed_extraction_empty()
    test_harness_writer_renders_all_classes()
    with tempfile.TemporaryDirectory() as t:
        test_job_builder_end_to_end(Path(t))
    with tempfile.TemporaryDirectory() as t:
        test_job_builder_from_subagent_results(Path(t))
    test_crash_triage_asan_match()
    test_crash_triage_ubsan_no_match()
    test_crash_triage_no_crash()
    with tempfile.TemporaryDirectory() as t:
        test_local_runner_skip_if_no_clang(Path(t))
    print("=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
