"""Extract seed corpus bytes from EnrichedFinding poc_stub fields.

PoC stubs come in two shapes:
  1. Python harness code (e.g. `socket.send(b'\\x00\\x00\\x00\\x20' + b'A'*32)`)
  2. Raw payload (hex, base64, or literal bytes string)

We do best-effort extraction:
  - Look for python `bytes(...)` / `b'...'` literals
  - Look for hex blobs (>=8 hex chars)
  - Look for base64 blobs
  - Fall back to the entire stub encoded as UTF-8

Each extracted seed is written as `<sha1[:12]>.bin` so duplicates collapse.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
from pathlib import Path
from typing import Iterable, List, Tuple


_BYTES_LITERAL_RE = re.compile(r"b['\"]((?:\\.|[^'\"\\])*?)['\"]", re.DOTALL)
_HEX_BLOB_RE = re.compile(r"\b([0-9a-fA-F]{8,})\b")
_BASE64_BLOB_RE = re.compile(r"\b([A-Za-z0-9+/]{20,}={0,2})\b")
_PAYLOAD_VAR_RE = re.compile(r"payload\s*[+]?=\s*(.+)$", re.MULTILINE)


def _decode_python_bytes_literal(s: str) -> bytes:
    """Interpret \\x.. escapes inside a python bytes literal."""
    try:
        return s.encode("latin-1").decode("unicode_escape").encode("latin-1")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s.encode("utf-8", errors="replace")


def extract_seed_bytes(poc_stub: str, max_seeds: int = 8,
                       max_bytes_per_seed: int = 16384) -> List[bytes]:
    """Extract candidate seed payloads from a PoC stub. Returns [] on no signal."""
    if not poc_stub:
        return []
    out: List[bytes] = []
    seen: set = set()

    def _add(b: bytes) -> None:
        if not b:
            return
        b = b[:max_bytes_per_seed]
        h = hashlib.sha1(b).digest()
        if h in seen:
            return
        seen.add(h)
        out.append(b)

    for m in _BYTES_LITERAL_RE.finditer(poc_stub):
        if len(out) >= max_seeds:
            break
        _add(_decode_python_bytes_literal(m.group(1)))

    if len(out) < max_seeds:
        for m in _HEX_BLOB_RE.finditer(poc_stub):
            if len(out) >= max_seeds:
                break
            blob = m.group(1)
            if len(blob) % 2 != 0:
                blob = blob[:-1]
            try:
                _add(binascii.unhexlify(blob))
            except (binascii.Error, ValueError):
                continue

    if len(out) < max_seeds:
        for m in _BASE64_BLOB_RE.finditer(poc_stub):
            if len(out) >= max_seeds:
                break
            blob = m.group(1)
            try:
                _add(base64.b64decode(blob, validate=True))
            except (binascii.Error, ValueError):
                continue

    if not out:
        # Fallback: whole stub as utf-8 payload. Better than empty corpus.
        _add(poc_stub.encode("utf-8", errors="replace")[:max_bytes_per_seed])

    return out


class SeedExtractor:
    """Write extracted seeds to a directory; return their paths."""

    def __init__(self, max_seeds: int = 8, max_bytes_per_seed: int = 16384):
        self.max_seeds = max_seeds
        self.max_bytes_per_seed = max_bytes_per_seed

    def write_seeds(self, poc_stub: str, dest_dir: Path) -> List[Tuple[str, str]]:
        """Extract seeds from poc_stub and write them to dest_dir.

        Returns list of (filename, sha1) for each seed written.
        """
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        results: List[Tuple[str, str]] = []
        for blob in extract_seed_bytes(poc_stub,
                                       max_seeds=self.max_seeds,
                                       max_bytes_per_seed=self.max_bytes_per_seed):
            sha = hashlib.sha1(blob).hexdigest()
            fname = f"{sha[:12]}.bin"
            (dest_dir / fname).write_bytes(blob)
            results.append((fname, sha))
        return results
