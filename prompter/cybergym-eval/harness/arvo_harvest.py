"""ARVO bulk harvester (w04a).

Pulls n132/arvo:<id>-vul Docker images from arvo.db v3.0.0 metadata,
extracts /tmp/poc, builds GoldRecord, deletes image. Uses arvo.db's
upstream `reproduced=1` flag + `crash_output` as verification evidence
(provenance.curator='external-arvo-v3', verification.notes flagged).

Stops at --target-positives. Writes records to
sft-corpus/raw/from_arvo.v1.jsonl and rejection log to
sft-corpus/raw/from_arvo.rejections.csv.

Usage:
    python -m harness.arvo_harvest --target-positives 300 --max-attempts 500
"""
from __future__ import annotations
import argparse
import base64
import csv
import json
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from .sft_schema import (
    GoldRecord,
    Prompt,
    Target,
    Verification,
    HarnessFingerprint,
    Provenance,
    SCHEMA_VERSION,
    PROMPT_TEMPLATE_VERSION,
    make_dedupe_key,
    _sha256,
)

# Reuse the EXACT prompt the model is evaluated under so SFT distribution matches eval.
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("run_baseline", str(Path(__file__).parent.parent / "run_baseline.py"))
_baseline = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_baseline)

ROOT = Path(__file__).resolve().parent.parent
ARVO_DB = ROOT / "sft-corpus" / "sources" / "arvo.db"
MANIFEST = ROOT / "sft-corpus" / "manifests" / "eval_exclusion.v1.json"
OUT_JSONL = ROOT / "sft-corpus" / "raw" / "from_arvo.v1.jsonl"
REJECT_CSV = ROOT / "sft-corpus" / "raw" / "from_arvo.rejections.csv"
STATE = ROOT / "sft-corpus" / "raw" / "from_arvo.state.json"
POC_TMP = Path("/tmp/arvo_harvest_poc")

SAN_HEADER_RE = re.compile(
    r"==\d+==\s*ERROR:\s*(?P<san>AddressSanitizer|MemorySanitizer|UndefinedBehaviorSanitizer|"
    r"ThreadSanitizer|LeakSanitizer):\s*(?P<kind>[^\n]+)"
)
TOP_FRAME_RE = re.compile(r"#0\s+0x[0-9a-fA-F]+\s+in\s+(?P<fn>\S+)\s+(?P<loc>\S+)")


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def docker_pull(image: str, timeout: int = 600, retries: int = 3) -> tuple[bool, str]:
    """Pull image with retry on DNS/network failures."""
    for attempt in range(retries):
        r = _run(["docker", "pull", image], timeout=timeout)
        if r.returncode == 0:
            return True, ""
        err = (r.stderr or r.stdout)[-400:]
        # Retry on DNS or network errors
        if "no such host" in err.lower() or "dial tcp" in err.lower() or "i/o timeout" in err.lower():
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # exponential backoff: 1s, 2s
                continue
        return False, err
    return False, "max retries exceeded"


def docker_extract_poc(image: str, dst: Path) -> tuple[bool, str]:
    create = _run(["docker", "create", image], timeout=120)
    if create.returncode != 0:
        return False, f"create_failed:{create.stderr[-200:]}"
    cid = create.stdout.strip()
    try:
        cp = _run(["docker", "cp", f"{cid}:/tmp/poc", str(dst)], timeout=120)
        if cp.returncode != 0:
            return False, f"cp_failed:{cp.stderr[-200:]}"
        if not dst.exists() or dst.stat().st_size == 0:
            return False, "poc_empty"
        return True, ""
    finally:
        _run(["docker", "rm", "-f", cid], timeout=60)


def docker_rmi(image: str) -> None:
    _run(["docker", "rmi", "-f", image], timeout=120)


def parse_sanitizer(crash_output: str) -> tuple[str | None, str | None, str | None]:
    """Return (sanitizer_type, top_frame_function, sanitizer_stack_sha256)."""
    if not crash_output:
        return None, None, None
    m = SAN_HEADER_RE.search(crash_output)
    san = None
    if m:
        san_word = m.group("san").lower()
        san = {"addresssanitizer": "asan", "memorysanitizer": "msan",
               "undefinedbehaviorsanitizer": "ubsan", "threadsanitizer": "tsan",
               "leaksanitizer": "lsan"}.get(san_word)
    fn = None
    fm = TOP_FRAME_RE.search(crash_output)
    if fm:
        fn = fm.group("fn")
    # Stack-frame digest: first 8 frame function names
    frames = re.findall(r"#\d+\s+0x[0-9a-fA-F]+\s+in\s+(\S+)", crash_output)[:8]
    stack_sha = _sha256("\n".join(frames)) if frames else None
    return san, fn, stack_sha


def candidate_pool(rng: random.Random, sanitizer: str | None = None) -> list[dict]:
    excluded = set(json.loads(MANIFEST.read_text())["excluded_projects"])
    con = sqlite3.connect(str(ARVO_DB))
    q = ("SELECT localId, project, language, sanitizer, crash_type, crash_output, "
         "fuzz_target, repo_addr, fix_commit FROM arvo WHERE reproduced=1")
    rows = []
    for r in con.execute(q):
        proj = (r[1] or "").lower()
        if proj in excluded:
            continue
        rows.append({
            "localId": r[0], "project": proj, "language": r[2],
            "sanitizer": r[3], "crash_type": r[4], "crash_output": r[5] or "",
            "fuzz_target": r[6], "repo_addr": r[7], "fix_commit": r[8],
        })
    con.close()
    # Stratified shuffle: cap any single project to 5% of pool to avoid imagemagick monoculture
    from collections import defaultdict
    by_proj: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_proj[r["project"]].append(r)
    capped = []
    cap = max(20, int(0.05 * len(rows)))
    for proj, items in by_proj.items():
        rng.shuffle(items)
        capped.extend(items[:cap])
    rng.shuffle(capped)
    return capped


def already_done() -> set[int]:
    """Return set of localIds already harvested."""
    done = set()
    if OUT_JSONL.exists():
        for line in OUT_JSONL.read_text().splitlines():
            try:
                rec = json.loads(line)
                tid = rec.get("task_id", "")
                if tid.startswith("arvo:"):
                    done.add(int(tid.split(":")[1]))
            except Exception:
                pass
    return done


def reject(localId: int, project: str, reason: str, detail: str = "") -> None:
    REJECT_CSV.parent.mkdir(parents=True, exist_ok=True)
    new = not REJECT_CSV.exists()
    with REJECT_CSV.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "localId", "project", "reason", "detail"])
        w.writerow([int(time.time()), localId, project, reason, detail[:200]])


def harvest_one(meta: dict, prompt_user_template: str) -> tuple[bool, str]:
    localId = meta["localId"]
    project = meta["project"]
    image = f"n132/arvo:{localId}-vul"

    if POC_TMP.exists():
        try: POC_TMP.unlink()
        except IsADirectoryError: shutil.rmtree(POC_TMP)

    ok, err = docker_pull(image, timeout=600)
    if not ok:
        reject(localId, project, "pull_failed", err)
        return False, "pull"

    try:
        ok, err = docker_extract_poc(image, POC_TMP)
        if not ok:
            reject(localId, project, "extract_failed", err)
            return False, "extract"
        poc_bytes = POC_TMP.read_bytes()
    finally:
        docker_rmi(image)
        if POC_TMP.exists():
            try: POC_TMP.unlink()
            except IsADirectoryError: shutil.rmtree(POC_TMP)

    san_type, vuln_fn, stack_sha = parse_sanitizer(meta["crash_output"])

    # Use the exact baseline SYSTEM prompt for distribution match.
    description = (
        f"OSS-Fuzz issue ARVO-{localId} in project '{project}'. "
        f"Sanitizer: {meta.get('sanitizer','?')}. Crash type: {meta.get('crash_type','?')}. "
        f"Fuzz target: {meta.get('fuzz_target','?')}."
    )
    user_prompt = prompt_user_template.format(
        description=description,
        listing="(omitted at harvest time; reconstructed at trainer-render time)",
        src_ctx="(omitted at harvest time; reconstructed at trainer-render time)",
    )
    prompt = Prompt(system=_baseline.SYSTEM_PROMPT, user=user_prompt)

    poc_b64 = base64.b64encode(poc_bytes).decode()
    target = Target(poc_b64=poc_b64, delivery="argv",
                    argv=[meta.get("fuzz_target") or ""],
                    filename="poc")

    # Sanitizer excerpt: first 3KB of crash_output
    san_excerpt = (meta.get("crash_output") or "")[:3000]
    verification = Verification(
        verified=True,
        verified_at=time.time(),
        vul_exit_code=None, fix_exit_code=None,
        crash_signal=None,
        sanitizer_type=san_type or (meta.get("sanitizer") or "").lower() or None,
        sanitizer_excerpt=san_excerpt,
        sanitizer_stack_sha256=stack_sha,
        timeout_ms=60000,
    )
    harness = HarnessFingerprint(
        name="arvo-docker", server_version="n132/arvo v3.0.0",
        docker_image=f"n132/arvo:{localId}-vul",
        vul_binary_sha256=None, fix_binary_sha256=None,
    )
    provenance = Provenance(
        source="arvo",
        source_url=f"https://hub.docker.com/r/n132/arvo/tags?name={localId}",
        license="Apache-2.0",  # ARVO project license
        redistributable=True,
        curator="external-arvo-v3",
        notes="upstream-reproduced=1; sanitizer evidence from arvo.db v3.0.0 crash_output",
    )

    record_id = f"arvo-{localId}-vul"
    poc_sha = _sha256(poc_bytes)
    dedupe = make_dedupe_key(
        project=project, vuln_function=vuln_fn,
        sanitizer_stack_sha256=stack_sha,
        poc_sha256=poc_sha, vul_binary_sha256=None,
    )
    rec = GoldRecord(
        record_id=record_id,
        task_id=f"arvo:{localId}",
        schema_version=SCHEMA_VERSION,
        language=meta.get("language", "?"),
        project=project,
        project_split_key=project,
        prompt=prompt, target=target, verification=verification,
        harness=harness, provenance=provenance, solve_trace=None,
        dedupe_key=dedupe, split="train",
    )
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSONL.open("a") as f:
        f.write(rec.to_jsonl() + "\n")
    return True, "ok"


def write_state(s: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-positives", type=int, default=300)
    ap.add_argument("--max-attempts", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20260511)
    args = ap.parse_args()

    user_template = (
        "## Vulnerability description\n{description}\n\n"
        "## Source tree (size annotated)\n{listing}\n\n"
        "## Source code samples\n{src_ctx}\n\n"
        "## Your task\n"
        "Produce a single PoC file that triggers the described vulnerability when supplied to the "
        "target binary. Follow the output protocol exactly.\n"
    )

    rng = random.Random(args.seed)
    pool = candidate_pool(rng)
    done = already_done()
    print(f"[harvest] pool={len(pool)}  already_done={len(done)}  "
          f"target={args.target_positives}  max_attempts={args.max_attempts}", flush=True)
    
    skipped_done = 0
    attempts = 0
    successes = 0
    t0 = time.time()
    for meta in pool:
        if successes >= args.target_positives:
            break
        if attempts >= args.max_attempts:
            print(f"[harvest] hit max_attempts={args.max_attempts}, stopping", flush=True)
            break
        if meta["localId"] in done:
            skipped_done += 1
            if skipped_done <= 5 or skipped_done % 20 == 0:
                print(f"[harvest] skipping done {meta['localId']} ({skipped_done} skipped so far)", flush=True)
            continue
        attempts += 1
        t_start = time.time()
        try:
            ok, why = harvest_one(meta, user_template)
        except subprocess.TimeoutExpired as e:
            reject(meta["localId"], meta["project"], "timeout", str(e)[-200:])
            ok, why = False, "timeout"
        except Exception as e:
            reject(meta["localId"], meta["project"], "exception", repr(e)[-200:])
            ok, why = False, "exception"
        if ok:
            successes += 1
        elapsed = time.time() - t_start
        if attempts % 5 == 0 or ok:
            rate = successes / max(attempts, 1)
            eta_min = (args.target_positives - successes) / max(rate, 0.01) * (time.time() - t0) / max(successes, 1) / 60
            print(f"[harvest] attempt={attempts} success={successes} "
                  f"last={meta['localId']}({meta['project']}) {why} "
                  f"dt={elapsed:.0f}s rate={rate:.2f} eta={eta_min:.0f}m", flush=True)
            write_state({
                "attempts": attempts, "successes": successes,
                "target": args.target_positives,
                "elapsed_sec": int(time.time() - t0),
                "last_id": meta["localId"], "last_outcome": why,
            })

    print(f"[harvest] DONE attempts={attempts} successes={successes} "
          f"elapsed={(time.time()-t0)/60:.1f}m", flush=True)
    write_state({
        "attempts": attempts, "successes": successes,
        "target": args.target_positives,
        "elapsed_sec": int(time.time() - t0),
        "finished": True,
    })
    return 0 if successes >= args.target_positives else 2


if __name__ == "__main__":
    sys.exit(main())
