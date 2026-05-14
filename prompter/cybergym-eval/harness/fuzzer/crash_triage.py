"""Parse sanitizer / fuzzer output into CrashRecord. Used by w46 Verifier."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import List, Optional

from .spec import CrashRecord, FuzzJobSpec


_ASAN_SUMMARY_RE = re.compile(
    r"==\d+==ERROR: AddressSanitizer:\s+(\S+)(?:\s+on address\s+(0x[0-9a-fA-F]+))?",
    re.IGNORECASE,
)
_UBSAN_SUMMARY_RE = re.compile(
    r"SUMMARY: UndefinedBehaviorSanitizer:\s+(\S+)", re.IGNORECASE,
)
_MSAN_SUMMARY_RE = re.compile(
    r"==\d+==WARNING: MemorySanitizer:\s+(\S+)", re.IGNORECASE,
)
_LSAN_SUMMARY_RE = re.compile(
    r"==\d+==ERROR: LeakSanitizer:\s+(\S+)", re.IGNORECASE,
)
_FRAME_RE = re.compile(r"^\s*#\d+\s+0x[0-9a-fA-F]+\s+in\s+(.+?)$", re.MULTILINE)


_SEVERITY_MAP = {
    "heap-buffer-overflow": "high",
    "stack-buffer-overflow": "high",
    "heap-use-after-free": "critical",
    "double-free": "critical",
    "use-after-free": "critical",
    "out-of-bounds-read": "medium",
    "format-string-write": "high",
    "signed-integer-overflow": "medium",
    "divide-by-zero": "medium",
    "null-pointer-dereference": "medium",
    "uninitialized-memory": "high",
    "memory-leak": "low",
}


class CrashTriage:
    """Stateless parser. Combine fuzzer log + crashing input -> CrashRecord."""

    def parse(self, output: str, job_spec: FuzzJobSpec,
              crash_input_path: Optional[Path] = None,
              duration_s: float = 0.0) -> Optional[CrashRecord]:
        """Return a CrashRecord if `output` indicates a sanitizer crash, else None."""
        sanitizer, crash_type, address = self._detect(output)
        if not crash_type:
            return None

        frames = _FRAME_RE.findall(output)[:8]

        crash_input_path_str = str(crash_input_path) if crash_input_path else ""
        crash_sha = ""
        if crash_input_path and Path(crash_input_path).is_file():
            crash_sha = hashlib.sha256(Path(crash_input_path).read_bytes()).hexdigest()

        expected = job_spec.expected_crash or {}
        matches_expected = self._matches_expected(sanitizer, crash_type, expected)
        severity = _SEVERITY_MAP.get(crash_type.lower(), "unknown")

        return CrashRecord(
            job_id=job_spec.job_id,
            finding_id=job_spec.finding_id,
            cwe=job_spec.cwe,
            crash_input_path=crash_input_path_str,
            crash_input_sha256=crash_sha,
            sanitizer=sanitizer or "unknown",
            crash_type=crash_type,
            crash_address=address,
            stack_frames=frames,
            matches_expected=matches_expected,
            full_output=output,
            duration_s=duration_s,
            severity=severity,
        )

    def parse_libfuzzer_run(self, job_dir: Path) -> List[CrashRecord]:
        """Walk a job dir after `./run.sh`. Pair fuzz.log + crashes/* into CrashRecords."""
        job_dir = Path(job_dir)
        spec = FuzzJobSpec.from_dir(job_dir)
        log_file = job_dir / "fuzz.log"
        if not log_file.is_file():
            return []
        log = log_file.read_text(errors="replace")

        crashes_dir = job_dir / "crashes"
        crash_inputs = sorted(crashes_dir.glob("crash-*")) if crashes_dir.is_dir() else []

        records: List[CrashRecord] = []
        if not crash_inputs:
            rec = self.parse(log, spec)
            if rec:
                records.append(rec)
            return records

        for ci in crash_inputs:
            rec = self.parse(log, spec, crash_input_path=ci)
            if rec:
                records.append(rec)
        return records

    def _detect(self, output: str):
        for san, rx in (("asan", _ASAN_SUMMARY_RE), ("ubsan", _UBSAN_SUMMARY_RE),
                        ("msan", _MSAN_SUMMARY_RE), ("lsan", _LSAN_SUMMARY_RE)):
            m = rx.search(output)
            if m:
                ct = m.group(1).strip().lower().rstrip(",;")
                addr = m.group(2) if m.lastindex and m.lastindex >= 2 else None
                return san, ct, addr
        return None, None, None

    def _matches_expected(self, sanitizer, crash_type, expected) -> bool:
        if not expected:
            return True
        exp_san = (expected.get("sanitizer") or "").lower()
        exp_summary = (expected.get("summary") or "").lower()
        ct_norm = (crash_type or "").lower()
        if exp_san and sanitizer and exp_san != sanitizer:
            return False
        if exp_summary and exp_summary not in ct_norm and ct_norm not in exp_summary:
            return False
        return True
