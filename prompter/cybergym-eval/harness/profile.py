from __future__ import annotations

import hashlib
from pathlib import Path

from .schema import ArtifactPaths, Profile, write_json


LANG_BY_SUFFIX = {
    ".c": "C",
    ".h": "C/C++ header",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".hh": "C++ header",
    ".hpp": "C++ header",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".rb": "Ruby",
    ".php": "PHP",
}

BUILD_SIGNALS = {
    "CMakeLists.txt": "cmake",
    "configure.ac": "autoconf",
    "configure.in": "autoconf",
    "Makefile.am": "automake",
    "Makefile": "make",
    "meson.build": "meson",
    "Cargo.toml": "cargo",
    "go.mod": "go",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "package.json": "npm",
    "setup.py": "python-setuptools",
    "pyproject.toml": "python-pyproject",
}

SANITIZER_LANGS = {"C", "C++", "C/C++ header", "C++ header", "Rust"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_language_mix(src_dir: Path) -> tuple[dict[str, int], int, int]:
    mix: dict[str, int] = {}
    file_count = 0
    total_bytes = 0
    for path in src_dir.rglob("*"):
        if not path.is_file():
            continue
        file_count += 1
        try:
            size = path.stat().st_size
        except OSError:
            continue
        total_bytes += size
        lang = LANG_BY_SUFFIX.get(path.suffix.lower())
        if lang:
            mix[lang] = mix.get(lang, 0) + size
    return dict(sorted(mix.items(), key=lambda item: item[1], reverse=True)), file_count, total_bytes


def detect_build_systems(src_dir: Path) -> list[str]:
    detected: set[str] = set()
    for path in src_dir.rglob("*"):
        if path.is_file():
            signal = BUILD_SIGNALS.get(path.name)
            if signal:
                detected.add(signal)
    return sorted(detected)


def profile_cybergym_task(task_id: str, task_dir: Path, src_dir: Path, difficulty: str = "level1") -> Profile:
    description = task_dir / "description.txt"
    archive = task_dir / "repo-vul.tar.gz"
    language_mix, file_count, total_bytes = detect_language_mix(src_dir)
    profile = Profile(
        task_id=task_id,
        task_family=task_id.split(":", 1)[0],
        difficulty=difficulty,
        description_bytes=description.stat().st_size if description.exists() else 0,
        description_sha256=sha256_file(description) if description.exists() else "",
        source_archive=str(archive.name),
        source_archive_bytes=archive.stat().st_size if archive.exists() else 0,
        source_archive_sha256=sha256_file(archive) if archive.exists() else "",
        source_file_count=file_count,
        source_total_bytes=total_bytes,
        language_mix=language_mix,
        build_systems=detect_build_systems(src_dir),
        sanitizer_eligible=any(lang in SANITIZER_LANGS for lang in language_mix),
        artifact_paths=ArtifactPaths(),
    )
    write_json(task_dir / "profile.json", profile)
    return profile

