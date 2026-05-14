from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import run_baseline as baseline
from .runner import DEFAULT_DB_PATH, DEFAULT_RESULTS, profile_task, replay_run, run_tasks


DEFAULT_CYBERGYM_ROOT = Path("/home/cjs/prompter/cybergym")
DEFAULT_DATA_DIR = DEFAULT_CYBERGYM_ROOT / "cybergym_data" / "data"
DEFAULT_WORK_DIR = Path("/home/cjs/prompter/cybergym-eval/harness-runs")
DEFAULT_SERVER = "http://127.0.0.1:8666"


def cmd_profile(args: argparse.Namespace) -> None:
    task_dir = args.out_dir or DEFAULT_WORK_DIR / args.task_id.replace(":", "_")
    result = profile_task(
        args.task_id,
        task_dir,
        args.data_dir,
        args.server,
        args.cybergym_root,
    )
    print(json.dumps({"run_dir": str(task_dir), "task": result["task"]}, indent=2))


def cmd_run(args: argparse.Namespace) -> None:
    tasks = list(args.tasks)
    stratum_by_task: dict[str, dict] = {}
    if args.tasks_file:
        payload = json.loads(args.tasks_file.read_text())
        for entry in payload.get("tasks", []):
            tid = entry["task_id"]
            tasks.append(tid)
            stratum_by_task[tid] = {k: entry.get(k) for k in payload.get("strata", [])}
    if not tasks:
        tasks = list(baseline.DEFAULT_TASKS)
    seen = set()
    deduped = [t for t in tasks if not (t in seen or seen.add(t))]
    run_tasks(
        deduped,
        server=args.server,
        cybergym_root=args.cybergym_root,
        data_dir=args.data_dir,
        work_dir=args.work_dir,
        results_path=args.results,
        db_path=args.db_path,
        max_tokens=args.max_tokens,
        stratum_by_task=stratum_by_task or None,
    )


def cmd_replay(args: argparse.Namespace) -> None:
    api_key = os.environ.get("CYBERGYM_API_KEY", "cybergym-030a0cd7-5908-4862-8ab9-91f2bfc7b56d")
    for run_dir in args.run_dirs:
        result = replay_run(run_dir, server=args.server, cybergym_api_key=api_key, db_path=args.db_path)
        print(json.dumps(result, indent=2, sort_keys=True))


def _wilson_ci(passed: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    p = passed / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def cmd_report(args: argparse.Namespace) -> None:
    rows = []
    if args.results.exists():
        for line in args.results.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))

    # Optional filter: only rows for tasks in the given tasks-file
    filter_tids: set[str] | None = None
    stratum_by_task: dict[str, dict] = {}
    if args.tasks_file and args.tasks_file.exists():
        payload = json.loads(args.tasks_file.read_text())
        filter_tids = {t["task_id"] for t in payload.get("tasks", [])}
        for t in payload.get("tasks", []):
            stratum_by_task[t["task_id"]] = {k: t.get(k) for k in payload.get("strata", [])}
        rows = [r for r in rows if r.get("task_id") in filter_tids]

    passed = sum(1 for row in rows if row.get("ok"))
    total = len(rows)
    ci_lo, ci_hi = _wilson_ci(passed, total)
    by_outcome = {
        outcome: sum(1 for row in rows if row.get("outcome") == outcome)
        for outcome in sorted({row.get("outcome") for row in rows if row.get("outcome")})
    }

    # Stratified breakdown if we have stratum metadata (from tasks-file or row.stratum)
    strata_breakdown: dict[str, dict] = {}
    for row in rows:
        tid = row.get("task_id")
        meta = row.get("stratum") or stratum_by_task.get(tid) or {}
        for axis, value in meta.items():
            key = f"{axis}={value}"
            cell = strata_breakdown.setdefault(key, {"total": 0, "passed": 0})
            cell["total"] += 1
            if row.get("ok"):
                cell["passed"] += 1
    for key, cell in strata_breakdown.items():
        cell["pass_at_1"] = cell["passed"] / max(cell["total"], 1)
        lo, hi = _wilson_ci(cell["passed"], cell["total"])
        cell["ci95"] = [round(lo, 4), round(hi, 4)]

    out = {
        "results": str(args.results),
        "filter_tasks_file": str(args.tasks_file) if args.tasks_file else None,
        "total": total,
        "passed": passed,
        "pass_at_1": passed / max(total, 1),
        "ci95_wilson": [round(ci_lo, 4), round(ci_hi, 4)],
        "by_outcome": by_outcome,
        "by_stratum": dict(sorted(strata_breakdown.items())),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(out, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage 0 CyberGym harness")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--cybergym-root", type=Path, default=DEFAULT_CYBERGYM_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)

    sub = parser.add_subparsers(dest="command", required=True)

    profile = sub.add_parser("profile", help="Generate and profile one CyberGym task")
    profile.add_argument("task_id")
    profile.add_argument("--out-dir", type=Path)
    profile.set_defaults(func=cmd_profile)

    run = sub.add_parser("run", help="Run model -> submit -> verifier for tasks")
    run.add_argument("--tasks", nargs="+", default=[])
    run.add_argument("--tasks-file", type=Path, help="Path to a calibration tasks JSON")
    run.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    run.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    run.add_argument("--max-tokens", type=int, default=8000)
    run.set_defaults(func=cmd_run)

    replay = sub.add_parser("replay", help="Replay verifier for stored run directories")
    replay.add_argument("run_dirs", nargs="+", type=Path)
    replay.set_defaults(func=cmd_replay)

    report = sub.add_parser("report", help="Summarize harness result JSONL")
    report.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    report.add_argument("--tasks-file", type=Path, help="Restrict to tasks listed here, attach strata")
    report.add_argument("--json-out", type=Path, help="Write report JSON to this path")
    report.set_defaults(func=cmd_report)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
