"""w78 fuzzer handoff layer.

Consumes enriched findings from harness/subagents/ and produces self-contained
"fuzz job specs" — packages of (harness source, seed corpus, build script,
run script, expected-crash metadata) that downstream infra (AFL++, libFuzzer,
honggfuzz) can execute without needing the LLM stack.

Module map:
- spec.py            FuzzJobSpec dataclass + on-disk layout
- harness_writer.py  Generate libFuzzer / AFL++ harness C source from an EnrichedFinding
- seed_corpus.py     Extract seed bytes from poc_stub fields
- job_builder.py     Orchestrator: enriched.jsonl -> jobs/<id>/{harness.c,seeds/,...}
- runner.py          Optional: compile + run libFuzzer locally if clang+sanitizers exist
- crash_triage.py    Parse sanitizer output into CrashRecord for w46 Verifier
"""

from .spec import FuzzJobSpec, CrashRecord
from .harness_writer import HarnessWriter
from .seed_corpus import SeedExtractor
from .job_builder import JobBuilder
from .runner import LocalRunner
from .crash_triage import CrashTriage

__all__ = [
    "FuzzJobSpec",
    "CrashRecord",
    "HarnessWriter",
    "SeedExtractor",
    "JobBuilder",
    "LocalRunner",
    "CrashTriage",
]
