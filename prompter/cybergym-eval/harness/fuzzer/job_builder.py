"""JobBuilder: read enriched findings JSONL, emit fuzz job directories."""
from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .spec import FuzzJobSpec
from .harness_writer import HarnessWriter, _guess_function_name
from .seed_corpus import SeedExtractor


def _short_id(finding_id: str, cwe: str) -> str:
    h = hashlib.sha1(f"{finding_id}|{cwe}".encode()).hexdigest()
    return h[:12]


def _expected_crash_for_cwe(cwe: str) -> Dict[str, str]:
    cwe = (cwe or "").upper()
    table = {
        "CWE-119": {"sanitizer": "asan", "summary": "buffer-overflow"},
        "CWE-120": {"sanitizer": "asan", "summary": "buffer-overflow"},
        "CWE-122": {"sanitizer": "asan", "summary": "heap-buffer-overflow"},
        "CWE-125": {"sanitizer": "asan", "summary": "out-of-bounds-read"},
        "CWE-416": {"sanitizer": "asan", "summary": "heap-use-after-free"},
        "CWE-415": {"sanitizer": "asan", "summary": "double-free"},
        "CWE-476": {"sanitizer": "ubsan", "summary": "null-pointer-dereference"},
        "CWE-401": {"sanitizer": "lsan", "summary": "memory-leak"},
        "CWE-190": {"sanitizer": "ubsan", "summary": "signed-integer-overflow"},
        "CWE-191": {"sanitizer": "ubsan", "summary": "signed-integer-overflow"},
        "CWE-369": {"sanitizer": "ubsan", "summary": "divide-by-zero"},
        "CWE-197": {"sanitizer": "ubsan", "summary": "implicit-conversion"},
        "CWE-680": {"sanitizer": "asan", "summary": "heap-buffer-overflow"},
        "CWE-134": {"sanitizer": "asan", "summary": "format-string-write"},
    }
    return table.get(cwe, {})


def _sanitizers_for_cwe(cwe: str) -> List[str]:
    expected = _expected_crash_for_cwe(cwe)
    san = expected.get("sanitizer")
    if san == "asan":
        return ["address", "undefined"]
    if san == "ubsan":
        return ["undefined", "address"]
    if san == "msan":
        return ["memory"]
    return ["address", "undefined"]


def _make_executable(p: Path) -> None:
    st = p.stat().st_mode
    p.chmod(st | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class JobBuilder:
    """Convert enriched findings into self-contained fuzz job directories."""

    def __init__(self, output_root: Path,
                 fuzzer: str = "libfuzzer",
                 time_budget_s: int = 600,
                 memory_limit_mb: int = 2048,
                 min_confidence: float = 0.4,
                 max_seeds: int = 8):
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.writer = HarnessWriter(fuzzer=fuzzer,
                                    time_budget_s=time_budget_s,
                                    memory_limit_mb=memory_limit_mb)
        self.seeder = SeedExtractor(max_seeds=max_seeds)
        self.fuzzer = fuzzer
        self.time_budget_s = time_budget_s
        self.memory_limit_mb = memory_limit_mb
        self.min_confidence = min_confidence

    def build_one(self, enriched: Dict) -> Optional[FuzzJobSpec]:
        """Build one job dir for one EnrichedFinding dict.

        Returns None if the finding is filtered out (low confidence, error, etc.).
        """
        if enriched.get("error"):
            return None
        confidence = float(enriched.get("confidence", 0.0) or 0.0)
        if confidence < self.min_confidence:
            return None

        finding_id = enriched.get("finding_id", "unknown")
        cwe = enriched.get("cwe", "unknown")
        job_id = _short_id(finding_id, cwe)
        job_dir = self.output_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        seeds_dir = job_dir / "seeds"

        seeds = self.seeder.write_seeds(enriched.get("poc_stub", ""), seeds_dir)
        if not seeds:
            # Always inject a 1-byte fallback so libFuzzer has something to mutate.
            (seeds_dir / "fallback.bin").write_bytes(b"\x00")
            seeds = [("fallback.bin", hashlib.sha1(b"\x00").hexdigest())]

        sanitizers_norm = _sanitizers_for_cwe(cwe)
        expected_crash = _expected_crash_for_cwe(cwe)

        rendered = self.writer.render_files({
            **enriched,
            "sanitizers": sanitizers_norm,
            "expected_crash": expected_crash,
            "seed_count": len(seeds),
        })

        target_function = rendered.pop("_target_function", "")
        rendered.pop("_sanitizers", None)

        for fname, content in rendered.items():
            (job_dir / fname).write_text(content)
        _make_executable(job_dir / "build.sh")
        _make_executable(job_dir / "run.sh")

        line_start = int(enriched.get("line_start", 0) or 0)
        line_end = int(enriched.get("line_end", line_start) or line_start)
        spec = FuzzJobSpec(
            job_id=job_id,
            finding_id=finding_id,
            cwe=cwe,
            target_file=enriched.get("file_path", ""),
            target_lines=list(range(line_start, line_end + 1)) if line_end >= line_start else [line_start],
            target_function=target_function,
            sanitizers=sanitizers_norm,
            fuzzer=self.fuzzer,
            harness_filename="harness.c",
            seed_count=len(seeds),
            expected_crash=expected_crash,
            build_cmd="./build.sh",
            run_cmd="./run.sh",
            time_budget_s=self.time_budget_s,
            memory_limit_mb=self.memory_limit_mb,
            notes=enriched.get("reasoning", "")[:1000],
            source_agent=enriched.get("agent_id", ""),
            static_priority=float(enriched.get("static_priority", 0.0) or 0.0),
            confidence=confidence,
        )
        (job_dir / "spec.json").write_text(spec.to_json())
        return spec

    def build_from_jsonl(self, enriched_jsonl: Path) -> List[FuzzJobSpec]:
        """Read every line of an enriched.jsonl and build job dirs."""
        enriched_jsonl = Path(enriched_jsonl)
        specs: List[FuzzJobSpec] = []
        if not enriched_jsonl.is_file():
            return specs
        for raw in enriched_jsonl.read_text(errors="replace").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            spec = self.build_one(rec)
            if spec:
                specs.append(spec)
        return specs

    def build_from_dir(self, subagent_results_dir: Path,
                       agents: Iterable[str] = ("sa1", "sa2", "sa3", "sa4")
                       ) -> Dict[str, List[FuzzJobSpec]]:
        """Process every {agent}_enriched.jsonl in subagent_results_dir."""
        subagent_results_dir = Path(subagent_results_dir)
        out: Dict[str, List[FuzzJobSpec]] = {}
        for aid in agents:
            path = subagent_results_dir / f"{aid}_enriched.jsonl"
            specs = self.build_from_jsonl(path)
            out[aid] = specs
            if specs:
                print(f"[JobBuilder] {aid}: built {len(specs)} fuzz jobs in {self.output_root}")
        # Write a manifest
        manifest = self.output_root / "manifest.json"
        manifest.write_text(json.dumps({
            aid: [asdict(s) for s in specs] for aid, specs in out.items()
        }, indent=2))
        return out
