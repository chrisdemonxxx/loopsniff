"""Stratified sampler for Calibration Set B.

Reads cybergym_data/tasks.json, excludes the 10 curated subset tasks
(those that the project ships pre-cached in download_subset.py), and
draws a seeded stratified sample across (source, language) cells.

Output: a JSON file consumable by harness.cli run --tasks-file:
    {
      "seed": 42,
      "n": 30,
      "strata": ["source", "language"],
      "tasks": [
        {"task_id": "...", "source": "arvo", "language": "c", ...},
        ...
      ]
    }
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

CURATED = {
    "arvo:47101", "arvo:3938", "arvo:24993", "arvo:1065", "arvo:10400", "arvo:368",
    "oss-fuzz:42535201", "oss-fuzz:42535468", "oss-fuzz:370689421", "oss-fuzz:385167047",
}

LANG_BUCKETS = {"c": "c", "c++": "c++", "cpp": "c++"}


def lang_bucket(raw: str | None) -> str:
    if not raw:
        return "other"
    key = raw.strip().lower()
    return LANG_BUCKETS.get(key, "other")


def stratified_sample(tasks: list[dict], n: int, axes: list[str], seed: int) -> list[dict]:
    rng = random.Random(seed)
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for t in tasks:
        key = tuple(t[ax] for ax in axes)
        buckets[key].append(t)
    cells = sorted(buckets.keys())
    for c in cells:
        rng.shuffle(buckets[c])

    target = max(1, n // len(cells))
    chosen: list[dict] = []
    # First pass: take target from each cell
    for c in cells:
        chosen.extend(buckets[c][:target])
        buckets[c] = buckets[c][target:]
    # Top up with leftovers (any cell), shuffled together
    if len(chosen) < n:
        leftovers = [t for c in cells for t in buckets[c]]
        rng.shuffle(leftovers)
        chosen.extend(leftovers[: n - len(chosen)])
    # Trim if over (rare — when target rounds up x cells > n)
    if len(chosen) > n:
        rng.shuffle(chosen)
        chosen = chosen[:n]
    return chosen


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tasks-json", type=Path,
                   default=Path("/home/cjs/prompter/cybergym/cybergym_data/tasks.json"))
    p.add_argument("--out", type=Path,
                   default=Path("/home/cjs/prompter/cybergym-eval/harness/calibration_b_tasks.json"))
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--axes", nargs="+", default=["source", "language"])
    args = p.parse_args()

    raw = json.loads(args.tasks_json.read_text())
    pool: list[dict] = []
    for t in raw:
        tid = t["task_id"]
        if tid in CURATED:
            continue
        pool.append({
            "task_id": tid,
            "source": tid.split(":", 1)[0],
            "language": lang_bucket(t.get("project_language")),
            "project_name": t.get("project_name"),
            "vulnerability_description": (t.get("vulnerability_description") or "")[:200],
        })

    chosen = stratified_sample(pool, args.n, args.axes, args.seed)

    # Stratum tally for the report
    tally: dict[str, int] = defaultdict(int)
    for t in chosen:
        tally["|".join(t[ax] for ax in args.axes)] += 1

    payload = {
        "seed": args.seed,
        "n": len(chosen),
        "strata": args.axes,
        "stratum_counts": dict(sorted(tally.items())),
        "excluded_curated": sorted(CURATED),
        "pool_size": len(pool),
        "tasks": chosen,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"out": str(args.out), "n": len(chosen),
                      "stratum_counts": payload["stratum_counts"],
                      "pool_size": len(pool)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
