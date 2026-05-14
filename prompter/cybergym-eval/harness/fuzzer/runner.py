"""LocalRunner: optionally compile + run a FuzzJobSpec locally.

Most of the time the user will hand `jobs/` to a CI/cluster that has clang +
sanitizers preinstalled. This runner is a convenience for one-off local tests.

Skipped gracefully if `clang` is not on PATH or if the harness needs the
real target sources (which we don't ship with the auto-generated stub).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .spec import FuzzJobSpec, CrashRecord
from .crash_triage import CrashTriage


class LocalRunner:
    def __init__(self, clang_bin: Optional[str] = None,
                 timeout_buffer_s: int = 30):
        self.clang_bin = clang_bin or shutil.which("clang")
        self.timeout_buffer_s = timeout_buffer_s

    def can_run(self) -> bool:
        return self.clang_bin is not None

    def build_and_run(self, job_dir: Path) -> dict:
        """Returns dict with build_ok, run_ok, crashes, error fields."""
        job_dir = Path(job_dir)
        result = {
            "job_dir": str(job_dir),
            "build_ok": False,
            "run_ok": False,
            "crashes": [],
            "error": None,
        }
        if not self.can_run():
            result["error"] = "clang not found on PATH"
            return result

        spec = FuzzJobSpec.from_dir(job_dir)

        # Build
        try:
            r = subprocess.run(
                ["bash", "build.sh"], cwd=job_dir, capture_output=True,
                text=True, timeout=300, env={**__import__("os").environ,
                                             "CLANG": self.clang_bin},
            )
            result["build_stdout"] = (r.stdout or "")[:4000]
            result["build_stderr"] = (r.stderr or "")[:4000]
            if r.returncode != 0:
                result["error"] = f"build failed (rc={r.returncode})"
                return result
            result["build_ok"] = True
        except subprocess.TimeoutExpired:
            result["error"] = "build timeout"
            return result
        except Exception as e:
            result["error"] = f"build exception: {e}"
            return result

        # Run
        run_timeout = spec.time_budget_s + self.timeout_buffer_s
        try:
            r = subprocess.run(
                ["bash", "run.sh"], cwd=job_dir, capture_output=True,
                text=True, timeout=run_timeout,
            )
            result["run_stdout"] = (r.stdout or "")[:4000]
            result["run_stderr"] = (r.stderr or "")[:4000]
            result["run_ok"] = True
        except subprocess.TimeoutExpired as e:
            result["run_stdout"] = (e.stdout.decode(errors="replace") if e.stdout else "")[:4000]
            result["run_ok"] = True  # libFuzzer terminating on its budget is normal
        except Exception as e:
            result["error"] = f"run exception: {e}"
            return result

        triage = CrashTriage()
        records = triage.parse_libfuzzer_run(job_dir)
        result["crashes"] = [r.to_json() for r in records]
        return result
