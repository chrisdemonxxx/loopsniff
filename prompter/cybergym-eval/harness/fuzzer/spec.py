"""Fuzz job spec + crash record dataclasses."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FuzzJobSpec:
    """Self-contained fuzz job. Serializes to a directory with a stable layout:

      jobs/<job_id>/
        spec.json           — this dataclass
        harness.c           — libFuzzer entry point
        build.sh            — clang -fsanitize=address,fuzzer ...
        run.sh              — invoke the fuzzer with a time budget
        seeds/<sha>.bin     — seed corpus
        README.md           — human-readable description
    """
    job_id: str                       # short hash of finding_id + cwe
    finding_id: str
    cwe: str
    target_file: str                  # original source file from finding
    target_lines: List[int]           # line range in target_file
    target_function: str              # best-effort name
    sanitizers: List[str]             # ["asan"], ["asan","ubsan"], etc.
    fuzzer: str                       # "libfuzzer" | "aflpp"
    harness_filename: str             # e.g. "harness.c"
    seed_count: int
    expected_crash: Dict[str, Any]    # {"type":"asan","summary":"heap-buffer-overflow"}
    build_cmd: str
    run_cmd: str
    time_budget_s: int
    memory_limit_mb: int
    notes: str = ""
    source_agent: str = ""            # which subagent enriched this
    static_priority: float = 0.0
    confidence: float = 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_dir(cls, job_dir: Path) -> "FuzzJobSpec":
        spec = json.loads((Path(job_dir) / "spec.json").read_text())
        return cls(**spec)


@dataclass
class CrashRecord:
    """One reproduced crash from a fuzz run. Consumed by w46 Verifier."""
    job_id: str
    finding_id: str
    cwe: str
    crash_input_path: str             # path to the crashing seed bytes
    crash_input_sha256: str
    sanitizer: str                    # "asan" | "ubsan" | "msan" | None
    crash_type: str                   # "heap-buffer-overflow" | etc.
    crash_address: Optional[str]      # e.g. "0x602000000020"
    stack_frames: List[str]           # top frames from sanitizer report
    matches_expected: bool            # crash matches expected_crash from spec
    full_output: str                  # raw fuzzer/sanitizer log
    duration_s: float                 # how long until crash hit
    severity: str = "unknown"

    def to_json(self) -> str:
        d = asdict(self)
        # truncate full_output for storage; full kept on disk
        d["full_output"] = (self.full_output or "")[:8000]
        return json.dumps(d, ensure_ascii=False)
