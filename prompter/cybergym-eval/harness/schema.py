from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Outcome(str, Enum):
    GEN_TASK_FAILED = "GEN_TASK_FAILED"
    MODEL_ERROR = "MODEL_ERROR"
    POC_PARSE_FAILED = "POC_PARSE_FAILED"
    SUBMIT_REJECTED = "SUBMIT_REJECTED"
    VERIFIER_NEGATIVE = "VERIFIER_NEGATIVE"
    VERIFIER_POSITIVE = "VERIFIER_POSITIVE"
    INFRA_ERROR = "INFRA_ERROR"


@dataclass
class ArtifactPaths:
    profile: str = "profile.json"
    task: str = "task.json"
    commands: str = "commands.json"
    build_log: str = "build.log"
    sanitizer_log: str = "sanitizer.log"
    model_response: str = "model_response.txt"
    poc: str = "poc"
    submit: str = "submit.json"
    verifier: str = "verifier.json"
    result: str = "result.json"


@dataclass
class Profile:
    task_id: str
    task_family: str
    difficulty: str
    description_bytes: int
    description_sha256: str
    source_archive: str
    source_archive_bytes: int
    source_archive_sha256: str
    source_file_count: int
    source_total_bytes: int
    language_mix: dict[str, int]
    build_systems: list[str]
    sanitizer_eligible: bool
    artifact_paths: ArtifactPaths = field(default_factory=ArtifactPaths)


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(payload), indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())

