"""SFT corpus schema for the autonomous vuln-discovery model.

Two formats:
  GoldRecord  — raw curated record with full provenance/verification evidence
  TrainerExample — derived format the SFT trainer consumes (messages + loss mask)

GoldRecord is the source of truth. TrainerExample is regenerated from
GoldRecord by `to_trainer_example(record, prompt_template_version)`.
"""
from __future__ import annotations
import base64
import dataclasses
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "v1.0"
PROMPT_TEMPLATE_VERSION = "cybergym-v1"  # bump if prompt format in run_baseline changes


def _sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


@dataclass
class Prompt:
    system: str
    user: str
    template_version: str = PROMPT_TEMPLATE_VERSION
    rendered_sha256: str = ""

    def __post_init__(self):
        if not self.rendered_sha256:
            self.rendered_sha256 = _sha256(self.system + "\n---\n" + self.user)


@dataclass
class Target:
    """The ground-truth answer the model should produce."""
    poc_b64: str
    delivery: str = "stdin"            # stdin | argv | file | network
    argv: list[str] = field(default_factory=list)
    filename: str | None = None
    poc_sha256: str = ""

    def __post_init__(self):
        if not self.poc_sha256 and self.poc_b64:
            self.poc_sha256 = _sha256(base64.b64decode(self.poc_b64 + "=" * ((-len(self.poc_b64)) % 4)))


@dataclass
class Verification:
    """Evidence that the PoC verifies on our harness."""
    verified: bool
    verified_at: float
    vul_exit_code: int | None
    fix_exit_code: int | None
    crash_signal: str | None = None     # SIGSEGV, SIGABRT, ...
    sanitizer_type: str | None = None   # asan | msan | ubsan | tsan | none
    sanitizer_excerpt: str | None = None
    sanitizer_stack_sha256: str | None = None
    timeout_ms: int = 60000


@dataclass
class HarnessFingerprint:
    """Reproducibility fingerprint for the verifier environment."""
    name: str = "cybergym-binary"
    server_version: str | None = None
    docker_image: str | None = None      # for ARVO: e.g., n132/arvo:3938
    vul_binary_sha256: str | None = None
    fix_binary_sha256: str | None = None
    git_sha: str | None = None           # git rev of cybergym-eval repo


@dataclass
class Provenance:
    source: str                          # arvo | oss-fuzz | cve | aixcc | model-positive
    source_url: str | None = None
    license: str | None = None
    redistributable: bool = False
    curator: str = "auto"                # auto | human | self-distill
    curated_at: float = field(default_factory=time.time)
    notes: str | None = None


@dataclass
class SolveTrace:
    """Structured solve narrative used INSTEAD of unconstrained CoT.

    Each field is short and grounded in concrete evidence (sanitizer output,
    source line, input bytes). Built by either humans or LLM-with-evidence.
    """
    hypothesis: str                      # what bug is being targeted
    vulnerable_function: str | None = None  # e.g. "bit_utf8_to_TV"
    vulnerable_file_line: str | None = None  # e.g. "src/in_json.h:842"
    cwe: str | None = None
    input_construction: str | None = None    # how the PoC bytes are designed
    expected_crash_condition: str | None = None
    verification_result: str | None = None   # what the sanitizer actually said
    rendered_sha256: str = ""

    def __post_init__(self):
        if not self.rendered_sha256:
            self.rendered_sha256 = _sha256(json.dumps(
                {k: getattr(self, k) for k in (
                    "hypothesis","vulnerable_function","vulnerable_file_line",
                    "cwe","input_construction","expected_crash_condition",
                    "verification_result")}, sort_keys=True))


@dataclass
class GoldRecord:
    record_id: str                        # unique within corpus
    task_id: str                          # source-style id, e.g., "arvo:3938"
    schema_version: str
    language: str                         # c | c++ | other
    project: str                          # repo / project name (for split key)
    project_split_key: str                # used for train/dev/heldout split
    prompt: Prompt
    target: Target
    verification: Verification
    harness: HarnessFingerprint
    provenance: Provenance
    solve_trace: SolveTrace | None        # may be filled later
    dedupe_key: str                       # composite hash for dedup
    split: str = "train"                  # train | dev | heldout | excluded

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


def make_dedupe_key(*, project: str, vuln_function: str | None,
                    sanitizer_stack_sha256: str | None,
                    poc_sha256: str, vul_binary_sha256: str | None) -> str:
    """Composite dedup key — strongest guarantee against near-dup leakage."""
    parts = [
        f"proj={project}",
        f"fn={vuln_function or '?'}",
        f"san={sanitizer_stack_sha256 or '?'}",
        f"poc={poc_sha256[:16]}",
        f"vbin={(vul_binary_sha256 or '?')[:16]}",
    ]
    return _sha256("|".join(parts))[:24]


# ---------- Trainer-format derivation ----------

@dataclass
class TrainerExample:
    """Derived format for the SFT trainer."""
    messages: list[dict[str, str]]
    loss_mask: str = "assistant_only"
    metadata: dict[str, Any] = field(default_factory=dict)


def to_trainer_example(record: GoldRecord | dict) -> TrainerExample:
    """Render a GoldRecord (or dict) into messages for SFT.

    Assistant target is the structured solve trace + the canonical
    ```poc-base64\n<bytes>\n``` block, matching what eval expects.
    """
    # Handle both dict and dataclass
    def get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
    
    assistant_parts: list[str] = []
    solve_trace = get(record, 'solve_trace')
    if solve_trace:
        st = solve_trace
        # Compact, structured, evidence-grounded — NOT free-form CoT.
        assistant_parts.append("<analysis>")
        hypothesis = get(st, 'hypothesis')
        if hypothesis: assistant_parts.append(f"Hypothesis: {hypothesis}")
        vuln_fn = get(st, 'vulnerable_function')
        if vuln_fn:
            loc = get(st, 'vulnerable_file_line') or "?"
            assistant_parts.append(f"Vulnerable function: {vuln_fn} at {loc}")
        cwe = get(st, 'cwe')
        if cwe: assistant_parts.append(f"CWE: {cwe}")
        input_const = get(st, 'input_construction')
        if input_const:
            assistant_parts.append(f"Input construction: {input_const}")
        expected = get(st, 'expected_crash_condition')
        if expected:
            assistant_parts.append(f"Expected crash: {expected}")
        verif = get(st, 'verification_result')
        if verif:
            assistant_parts.append(f"Verification: {verif}")
        assistant_parts.append("</analysis>")
        assistant_parts.append("")
    assistant_parts.append("```poc-base64")
    target = get(record, 'target')
    poc_b64 = get(target, 'poc_b64')
    assistant_parts.append(poc_b64)
    assistant_parts.append("```")
    assistant = "\n".join(assistant_parts)

    prompt = get(record, 'prompt')
    return TrainerExample(
        messages=[
            {"role": "system",    "content": get(prompt, 'system')},
            {"role": "user",      "content": get(prompt, 'user')},
            {"role": "assistant", "content": assistant},
        ],
        loss_mask="assistant_only",
        metadata={
            "record_id": get(record, 'record_id'),
            "task_id": get(record, 'task_id'),
            "split": get(record, 'split'),
            "project_split_key": get(record, 'project_split_key'),
            "schema_version": get(record, 'schema_version'),
            "prompt_template_version": get(prompt, 'template_version'),
            "dedupe_key": get(record, 'dedupe_key'),
        },
    )


# ---------- Append helpers ----------

def append_gold(corpus_path: Path, record: GoldRecord) -> None:
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with corpus_path.open("a") as f:
        f.write(record.to_jsonl() + "\n")


def append_negative(corpus_path: Path, neg: dict[str, Any]) -> None:
    """Negative examples kept in a separate stream for later GRPO/DPO.
    Schema is intentionally lighter — we don't promise verification here.
    """
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    required = {"task_id", "model_response_sha256", "outcome",
                "vul_exit_code", "fix_exit_code", "captured_at"}
    missing = required - set(neg.keys())
    if missing:
        raise ValueError(f"negative record missing fields: {missing}")
    with corpus_path.open("a") as f:
        f.write(json.dumps(neg, separators=(",", ":")) + "\n")
