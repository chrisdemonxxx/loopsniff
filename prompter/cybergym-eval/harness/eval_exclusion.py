"""Frozen eval-exclusion manifest.

Tasks (and their PROJECTS) listed here MUST NOT enter the SFT corpus.
This prevents data leakage when we re-evaluate on CyberGym L1 at Gates 2/3.

Splitting is by PROJECT, not task ID — a task on libxml2 in eval means NO
libxml2 task can be trained on, even a different one. This is the cybersec-
specific generalization of "split by repo, not commit".

Manifest is frozen by emitting `sft-corpus/manifests/eval_exclusion.v1.json`.
Once emitted, the file should be treated as append-only.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

CYBERGYM_DATA_ROOT = Path("/home/cjs/prompter/cybergym/cybergym_data/data")
HARNESS_RUNS = Path("/home/cjs/prompter/cybergym-eval/harness-runs")
CALIBRATION_TASKS_FILE = Path(
    "/home/cjs/prompter/cybergym-eval/harness/calibration_b_tasks.json"
)
MANIFEST_PATH = Path(
    "/home/cjs/prompter/cybergym-eval/sft-corpus/manifests/eval_exclusion.v1.json"
)

# Tasks used in Gate 1 baseline (the original 10 curated subset)
GATE1_CURATED = {
    "arvo:3938",
    "arvo:34755",
    "arvo:6247",
    "oss-fuzz:370689421",
    "oss-fuzz:373522467",
    "oss-fuzz:42536748",
    "oss-fuzz:42537014",
    "oss-fuzz:42537407",
    "oss-fuzz:42537883",
    "oss-fuzz:42538574",
}


def _project_from_repo_listing(task_dir: Path) -> str | None:
    """Best-effort project name from the unpacked repo: top-level src dir name."""
    src = task_dir / "src" / "src-vul"
    if not src.exists():
        return None
    for child in sorted(src.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            return child.name.lower()
    return None


def _project_from_description(desc: str) -> str | None:
    """Pull a project hint from the description text (best-effort)."""
    # Common prefixes in CyberGym descriptions
    for pat in (r"project[:\s]+([a-zA-Z0-9._-]+)",
                r"in\s+([a-z][a-zA-Z0-9._-]{2,})/",
                r"github\.com/[^/]+/([a-zA-Z0-9._-]+)"):
        m = re.search(pat, desc)
        if m:
            return m.group(1).lower()
    return None


def project_for_task(task_id: str) -> str:
    """Resolve a CyberGym task_id to a normalized project name.

    Looks first at any harness-run dir (we have repos unpacked there for the
    30 calibration tasks). Falls back to description.txt parse. Falls back
    to the task_id itself (so the exclusion is at LEAST as strict as task-level).
    """
    # 1. unpacked harness run dir
    norm_id = task_id.replace(":", "_")
    candidates = sorted(HARNESS_RUNS.glob(f"{norm_id}_*"), reverse=True)
    for cand in candidates:
        proj = _project_from_repo_listing(cand)
        if proj:
            return proj

    # 2. description.txt under cybergym_data
    src, num = task_id.split(":", 1)
    desc_p = CYBERGYM_DATA_ROOT / src / num / "description.txt"
    if desc_p.exists():
        proj = _project_from_description(desc_p.read_text())
        if proj:
            return proj

    # 3. fall back to task-level
    return task_id


def build_manifest() -> dict:
    excluded_tasks: set[str] = set(GATE1_CURATED)

    # Calibration B 30 tasks
    if CALIBRATION_TASKS_FILE.exists():
        cb = json.loads(CALIBRATION_TASKS_FILE.read_text())
        for t in cb.get("tasks", []):
            excluded_tasks.add(t["task_id"])

    # Resolve project per task
    project_map = {tid: project_for_task(tid) for tid in sorted(excluded_tasks)}
    excluded_projects = sorted({p for p in project_map.values()
                                if p and ":" not in p})  # drop fallback ids

    return {
        "manifest_version": "v1",
        "frozen": True,
        "rule": "any task whose project_split_key matches an entry in "
                "excluded_projects MUST NOT enter the SFT training corpus",
        "excluded_tasks": sorted(excluded_tasks),
        "task_to_project": project_map,
        "excluded_projects": excluded_projects,
        "project_count": len(excluded_projects),
        "task_count": len(excluded_tasks),
    }


def is_excluded(*, task_id: str | None, project: str | None,
                manifest: dict) -> tuple[bool, str]:
    if task_id and task_id in manifest["excluded_tasks"]:
        return True, f"task {task_id} in excluded_tasks"
    if project and project.lower() in manifest["excluded_projects"]:
        return True, f"project {project} in excluded_projects"
    return False, ""


def main():
    if MANIFEST_PATH.exists():
        existing = json.loads(MANIFEST_PATH.read_text())
        print(f"manifest already frozen: {MANIFEST_PATH}")
        print(f"  tasks: {existing['task_count']}  projects: {existing['project_count']}")
        return
    m = build_manifest()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(m, indent=2))
    print(f"wrote {MANIFEST_PATH}")
    print(f"  excluded tasks: {m['task_count']}")
    print(f"  excluded projects: {m['project_count']}")
    print(f"  projects: {m['excluded_projects'][:30]}")


if __name__ == "__main__":
    main()
