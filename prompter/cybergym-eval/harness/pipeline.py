"""w1011 end-to-end pipeline orchestrator.

Single entry point that walks a target source tree through the full
Tier-1 stack:

    target_dir -> static_analysis (4 layers + patch_diff)
               -> triage + dispatch (sa{1..5}.jsonl)
               -> subagents (sa{N}_enriched.jsonl)
               -> fuzzer JobBuilder (fuzz_jobs/<id>/)
               -> [optional] LocalRunner -> crashes.jsonl
               -> Verifier (verifications.jsonl)
               -> ReportWriter (reports/)

Designed to run offline with MockLLMClient + no clang for CI tests, and
online with real Baseten + real clang for production runs.
"""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from harness.static_analysis import (
    SemgrepAnalyzer, CodeQLAnalyzer, JoernAnalyzer, CustomASTAnalyzer,
    PatchDiffMiner, TriageEngine, SubagentDispatcher,
)
from harness.subagents import (
    SubagentOrchestrator, MockLLMClient, LLMClient, Verifier,
)
from harness.subagents.base import EnrichedFinding
from harness.fuzzer import JobBuilder, LocalRunner, CrashTriage
from harness.fuzzer.spec import FuzzJobSpec
from harness.output import ReportWriter


@dataclass
class PipelineStats:
    target_dir: str
    project: str
    out_dir: str
    started_at: float
    elapsed_s: float = 0.0

    static_findings_total: int = 0
    static_findings_by_layer: Dict[str, int] = field(default_factory=dict)
    dispatched_per_agent: Dict[str, int] = field(default_factory=dict)
    enriched_per_agent: Dict[str, int] = field(default_factory=dict)
    fuzz_jobs_built: int = 0
    fuzz_jobs_run: int = 0
    crashes_observed: int = 0
    verified: int = 0
    rejected: int = 0
    reports_emitted: int = 0
    estimated_llm_cost_usd: float = 0.0

    errors: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)


class E2EPipeline:
    """Glue layer: static -> subagents -> fuzz -> verify -> reports."""

    def __init__(self, out_dir: Path, project: str = "unknown",
                 llm_client=None, model_name: str = "Qwen3-Next-80B-A3B-Abliterated",
                 budget_usd: float = 10.0,
                 max_findings_per_agent: int = 10,
                 fuzz_time_budget_s: int = 60,
                 run_fuzzer_locally: bool = False,
                 include_rejected_in_reports: bool = False,
                 min_finding_confidence_for_fuzz: float = 0.5):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.project = project
        self.llm = llm_client or MockLLMClient()
        self.model_name = model_name
        self.budget_usd = budget_usd
        self.max_findings_per_agent = max_findings_per_agent
        self.fuzz_time_budget_s = fuzz_time_budget_s
        self.run_fuzzer_locally = run_fuzzer_locally
        self.include_rejected = include_rejected_in_reports
        self.min_fuzz_confidence = min_finding_confidence_for_fuzz

    # ---- public ----
    def run(self, target_dir: Path) -> PipelineStats:
        target_dir = Path(target_dir).resolve()
        stats = PipelineStats(
            target_dir=str(target_dir), project=self.project,
            out_dir=str(self.out_dir), started_at=time.time(),
        )
        t0 = time.time()
        try:
            ranked = self._stage_static(target_dir, stats)
            dispatch_dir = self._stage_dispatch(ranked, stats)
            enriched_dir = self._stage_subagents(dispatch_dir, stats)
            fuzz_dir = self._stage_fuzz_build(enriched_dir, stats)
            crashes = self._stage_fuzz_run(fuzz_dir, stats) if self.run_fuzzer_locally else []
            verifications = self._stage_verify(enriched_dir, crashes, stats)
            self._stage_reports(verifications, enriched_dir, stats)
        except Exception as e:
            stats.errors.append(f"pipeline_exception: {type(e).__name__}: {e}")
            raise
        finally:
            stats.elapsed_s = round(time.time() - t0, 2)
            (self.out_dir / "pipeline_stats.json").write_text(stats.to_json())
        return stats

    # ---- stages ----
    def _stage_static(self, target_dir: Path, stats: PipelineStats) -> List[Dict[str, Any]]:
        all_findings = []
        layer_counts: Dict[str, int] = {}

        for name, cls in [("semgrep", SemgrepAnalyzer),
                          ("codeql", CodeQLAnalyzer),
                          ("joern", JoernAnalyzer),
                          ("custom_ast", CustomASTAnalyzer)]:
            try:
                analyzer = cls()
                got = analyzer.analyze(target_dir) or []
            except Exception as e:
                stats.errors.append(f"{name}_failed: {e}")
                got = []
            layer_counts[name] = len(got)
            all_findings.extend(got)

        try:
            patch_findings = PatchDiffMiner().mine(target_dir) or []
        except Exception as e:
            stats.errors.append(f"patch_diff_failed: {e}")
            patch_findings = []

        ranked = TriageEngine().triage(all_findings, patch_findings)
        stats.static_findings_total = len(all_findings)
        stats.static_findings_by_layer = layer_counts
        return ranked

    def _stage_dispatch(self, ranked: List[Dict[str, Any]],
                        stats: PipelineStats) -> Path:
        ddir = self.out_dir / "dispatch_queues"
        ddir.mkdir(parents=True, exist_ok=True)
        # Clear stale
        for f in ddir.glob("*.jsonl"):
            f.unlink()
        counts = SubagentDispatcher(output_dir=ddir).dispatch(ranked)
        stats.dispatched_per_agent = dict(counts)
        return ddir

    def _stage_subagents(self, dispatch_dir: Path,
                         stats: PipelineStats) -> Path:
        edir = self.out_dir / "subagent_results"
        edir.mkdir(parents=True, exist_ok=True)
        orch = SubagentOrchestrator(
            llm_client=self.llm, model_name=self.model_name,
            budget_usd=self.budget_usd,
            max_findings_per_agent=self.max_findings_per_agent,
            output_dir=edir,
        )
        results = orch.run_from_dispatch_dir(dispatch_dir)
        per_agent: Dict[str, int] = {}
        cost = 0.0
        for aid, r in results.items():
            per_agent[aid] = sum(1 for e in r.enriched if e.error is None)
            cost += float(r.estimated_cost_usd or 0.0)
        stats.enriched_per_agent = per_agent
        stats.estimated_llm_cost_usd = round(cost, 4)
        return edir

    def _stage_fuzz_build(self, enriched_dir: Path,
                          stats: PipelineStats) -> Path:
        fdir = self.out_dir / "fuzz_jobs"
        fdir.mkdir(parents=True, exist_ok=True)
        builder = JobBuilder(
            fdir, time_budget_s=self.fuzz_time_budget_s,
            min_confidence=self.min_fuzz_confidence,
        )
        by_agent = builder.build_from_dir(enriched_dir)
        stats.fuzz_jobs_built = sum(len(v) for v in by_agent.values())
        return fdir

    def _stage_fuzz_run(self, fuzz_dir: Path,
                        stats: PipelineStats) -> List[Dict[str, Any]]:
        runner = LocalRunner()
        if not runner.can_run():
            stats.errors.append("clang_not_found_skipping_fuzz_run")
            return []
        all_crashes: List[Dict[str, Any]] = []
        crashes_path = self.out_dir / "crashes.jsonl"
        crashes_path.write_text("")
        triage = CrashTriage()
        for job_dir in sorted(p for p in fuzz_dir.iterdir() if p.is_dir()):
            spec_file = job_dir / "spec.json"
            if not spec_file.is_file():
                continue
            stats.fuzz_jobs_run += 1
            res = runner.build_and_run(job_dir)
            for c in res.get("crashes", []):
                try:
                    crash_dict = json.loads(c)
                except json.JSONDecodeError:
                    continue
                all_crashes.append(crash_dict)
                with crashes_path.open("a") as fh:
                    fh.write(json.dumps(crash_dict) + "\n")
        stats.crashes_observed = len(all_crashes)
        return all_crashes

    def _stage_verify(self, enriched_dir: Path,
                      crashes: List[Dict[str, Any]],
                      stats: PipelineStats) -> List:
        verifier = Verifier(self.llm, model_name=self.model_name)
        all_findings: List[EnrichedFinding] = []
        for jf in sorted(enriched_dir.glob("sa*_enriched.jsonl")):
            all_findings.extend(Verifier.load_enriched_jsonl(jf))
        results = verifier.verify_batch(all_findings, crashes)
        out_path = self.out_dir / "verifications.jsonl"
        verifier.write_results_jsonl(results, out_path)
        stats.verified = sum(1 for r in results if r.verified)
        stats.rejected = sum(1 for r in results if not r.verified)
        return results

    def _stage_reports(self, verifications: List, enriched_dir: Path,
                       stats: PipelineStats) -> None:
        all_findings: List[EnrichedFinding] = []
        for jf in sorted(enriched_dir.glob("sa*_enriched.jsonl")):
            all_findings.extend(Verifier.load_enriched_jsonl(jf))
        rdir = self.out_dir / "reports"
        writer = ReportWriter(rdir, project=self.project,
                              include_rejected=self.include_rejected)
        bundles = writer.write_batch(verifications, all_findings)
        stats.reports_emitted = len(bundles)


def _main():
    import argparse
    p = argparse.ArgumentParser(description="Run Tier-1 e2e vulnerability pipeline.")
    p.add_argument("target", type=Path, help="path to target source tree")
    p.add_argument("--out", type=Path, default=Path("e2e_out"))
    p.add_argument("--project", default="unknown")
    p.add_argument("--mock", action="store_true",
                   help="use MockLLMClient (offline, free)")
    p.add_argument("--run-fuzzer", action="store_true",
                   help="actually compile + run libFuzzer locally")
    p.add_argument("--budget-usd", type=float, default=10.0)
    p.add_argument("--max-per-agent", type=int, default=10)
    p.add_argument("--fuzz-time-s", type=int, default=60)
    p.add_argument("--include-rejected", action="store_true")
    args = p.parse_args()

    llm = MockLLMClient() if args.mock else LLMClient()
    pipe = E2EPipeline(
        out_dir=args.out, project=args.project,
        llm_client=llm, budget_usd=args.budget_usd,
        max_findings_per_agent=args.max_per_agent,
        fuzz_time_budget_s=args.fuzz_time_s,
        run_fuzzer_locally=args.run_fuzzer,
        include_rejected_in_reports=args.include_rejected,
    )
    stats = pipe.run(args.target)
    print(stats.to_json())


if __name__ == "__main__":
    _main()
