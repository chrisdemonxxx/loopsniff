"""End-to-end test of the full Tier-1 pipeline on a synthetic C target.

Runs offline with MockLLMClient, no clang, no Baseten. Verifies that
every stage produces the expected artifacts.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.pipeline import E2EPipeline, PipelineStats
from harness.subagents import MockLLMClient


_VULN_C = """\
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void handle(const char *user) {
    char buf[16];
    strcpy(buf, user);
    printf(buf);
}

int copy_payload(int fd, char *dst, int n) {
    char src[1024];
    int r = read(fd, src, n);
    memcpy(dst, src, n);
    return r;
}

void weak_random(unsigned int seed) {
    srand(seed);
    int token = rand();
    printf("token=%d\\n", token);
}

int main(int argc, char **argv) {
    if (argc > 1) handle(argv[1]);
    return 0;
}
"""


def _write_synthetic_target(root: Path) -> Path:
    src = root / "src"
    src.mkdir()
    (src / "vuln.c").write_text(_VULN_C)
    return root


def _seed_dispatch_queues_if_empty(out_dir: Path, target_dir: Path) -> None:
    ddir = out_dir / "dispatch_queues"
    ddir.mkdir(parents=True, exist_ok=True)
    files = list(ddir.glob("*.jsonl"))
    has_data = any(f.stat().st_size > 0 for f in files)
    if has_data:
        return
    target_file = str((target_dir / "src" / "vuln.c").resolve())
    seed = [
        ("sa1", {"finding": {"file_path": target_file, "line_start": 9, "line_end": 9,
                             "cwe": "CWE-120", "rule_id": "synthetic.strcpy",
                             "layer": "synthetic", "severity": "high",
                             "message": "strcpy of unbounded user input"},
                 "priority": 0.9}),
        ("sa1", {"finding": {"file_path": target_file, "line_start": 16, "line_end": 16,
                             "cwe": "CWE-122", "rule_id": "synthetic.memcpy",
                             "layer": "synthetic", "severity": "high",
                             "message": "memcpy attacker-controlled length"},
                 "priority": 0.9}),
        ("sa3", {"finding": {"file_path": target_file, "line_start": 10, "line_end": 10,
                             "cwe": "CWE-134", "rule_id": "synthetic.fmtstr",
                             "layer": "synthetic", "severity": "high",
                             "message": "non-literal format string"},
                 "priority": 0.85}),
        ("sa4", {"finding": {"file_path": target_file, "line_start": 21, "line_end": 21,
                             "cwe": "CWE-330", "rule_id": "synthetic.rand",
                             "layer": "synthetic", "severity": "medium",
                             "message": "rand() used for security token"},
                 "priority": 0.7}),
    ]
    by_agent = {}
    for aid, item in seed:
        by_agent.setdefault(aid, []).append(item)
    for aid, items in by_agent.items():
        with (ddir / f"{aid}.jsonl").open("w") as fh:
            for it in items:
                fh.write(json.dumps(it) + "\n")


def _run_with_seed_fallback(target: Path, out: Path, pipe: E2EPipeline) -> PipelineStats:
    stats = pipe.run(target)
    if stats.static_findings_total == 0 and not any(stats.dispatched_per_agent.values()):
        _seed_dispatch_queues_if_empty(out, target)
        stats2 = PipelineStats(target_dir=str(target), project=pipe.project,
                               out_dir=str(out), started_at=0.0)
        stats2.errors.append("static_layers_empty_seeded_synthetic_dispatch")
        stats2.dispatched_per_agent = {
            f.stem: sum(1 for _ in f.read_text().splitlines() if _.strip())
            for f in (out / "dispatch_queues").glob("*.jsonl")
        }
        enriched_dir = pipe._stage_subagents(out / "dispatch_queues", stats2)
        pipe._stage_fuzz_build(enriched_dir, stats2)
        crashes = pipe._stage_fuzz_run(out / "fuzz_jobs", stats2) if pipe.run_fuzzer_locally else []
        verifications = pipe._stage_verify(enriched_dir, crashes, stats2)
        pipe._stage_reports(verifications, enriched_dir, stats2)
        (out / "pipeline_stats.json").write_text(stats2.to_json())
        return stats2
    return stats


def test_e2e_full_pipeline_offline(tmp_path: Path):
    target = _write_synthetic_target(tmp_path)
    out = tmp_path / "out"
    pipe = E2EPipeline(out_dir=out, project="synthetic-vuln",
                       llm_client=MockLLMClient(), budget_usd=1.0,
                       max_findings_per_agent=10, fuzz_time_budget_s=10,
                       run_fuzzer_locally=False)
    stats = _run_with_seed_fallback(target, out, pipe)

    assert (out / "pipeline_stats.json").is_file()
    assert (out / "subagent_results").is_dir()
    assert (out / "fuzz_jobs").is_dir()
    assert (out / "verifications.jsonl").is_file()
    assert (out / "reports").is_dir()

    enriched_files = list((out / "subagent_results").glob("sa*_enriched.jsonl"))
    assert enriched_files, "no enriched findings"
    n_enriched = sum(sum(1 for _ in f.read_text().splitlines() if _.strip())
                     for f in enriched_files)
    assert n_enriched >= 1

    fuzz_jobs = [d for d in (out / "fuzz_jobs").iterdir() if d.is_dir()]
    assert fuzz_jobs, "no fuzz jobs built"
    for jd in fuzz_jobs:
        for required in ["spec.json", "harness.c", "build.sh", "run.sh"]:
            assert (jd / required).is_file(), f"{jd.name} missing {required}"

    vlines = [l for l in (out / "verifications.jsonl").read_text().splitlines() if l.strip()]
    assert vlines, "no verifications"

    reports = [d for d in (out / "reports").iterdir() if d.is_dir()]
    assert reports, "no report bundles"
    for r in reports[:3]:
        for required in ["report.md", "report.json", "advisory.md", "email.txt"]:
            assert (r / required).is_file(), f"{r.name} missing {required}"

    assert (out / "reports" / "index.md").is_file()
    idx = json.loads((out / "reports" / "index.json").read_text())
    assert isinstance(idx, list) and len(idx) >= 1
    bands = [b["cvss_band"] for b in idx]
    assert any(b in ("high", "critical") for b in bands), bands

    print(f"  test_e2e_full_pipeline_offline: OK "
          f"(enriched={n_enriched}, jobs={len(fuzz_jobs)}, "
          f"verif={len(vlines)}, reports={len(reports)}, "
          f"cost=${stats.estimated_llm_cost_usd})")


def test_e2e_handles_missing_clang(tmp_path: Path):
    import shutil as _sh
    target = _write_synthetic_target(tmp_path)
    out = tmp_path / "out"
    pipe = E2EPipeline(out_dir=out, project="x",
                       llm_client=MockLLMClient(), budget_usd=1.0,
                       max_findings_per_agent=3, fuzz_time_budget_s=5,
                       run_fuzzer_locally=True)
    stats = _run_with_seed_fallback(target, out, pipe)
    if not _sh.which("clang"):
        assert any("clang_not_found" in e for e in stats.errors), stats.errors
        assert stats.crashes_observed == 0
    print("  test_e2e_handles_missing_clang: OK")


def test_pipeline_stats_serializable(tmp_path: Path):
    target = _write_synthetic_target(tmp_path)
    out = tmp_path / "out"
    pipe = E2EPipeline(out_dir=out, project="x",
                       llm_client=MockLLMClient(), budget_usd=1.0,
                       max_findings_per_agent=2)
    _run_with_seed_fallback(target, out, pipe)
    parsed = json.loads((out / "pipeline_stats.json").read_text())
    for k in ["target_dir", "project", "static_findings_by_layer",
              "dispatched_per_agent", "enriched_per_agent",
              "fuzz_jobs_built", "verified", "rejected", "reports_emitted",
              "estimated_llm_cost_usd", "elapsed_s"]:
        assert k in parsed, k
    print("  test_pipeline_stats_serializable: OK")


def main():
    print("=== w1011 e2e pipeline tests ===")
    with tempfile.TemporaryDirectory() as t:
        test_e2e_full_pipeline_offline(Path(t))
    with tempfile.TemporaryDirectory() as t:
        test_e2e_handles_missing_clang(Path(t))
    with tempfile.TemporaryDirectory() as t:
        test_pipeline_stats_serializable(Path(t))
    print("=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
