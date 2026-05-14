"""Capture VERIFIER_NEGATIVE rows as a negatives stream for later GRPO/DPO.

Negatives are NOT for SFT — they're preference/contrastive data for w08+.
Schema is intentionally lighter than GoldRecord.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import time
from pathlib import Path

from harness.eval_exclusion import project_for_task
from harness.sft_schema import append_negative

REPO_ROOT = Path("/home/cjs/prompter/cybergym-eval")
RESULTS = REPO_ROOT / "harness-results.jsonl"
NEG_OUT = REPO_ROOT / "sft-corpus/negatives/from_runs.v1.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(RESULTS))
    ap.add_argument("--out", default=str(NEG_OUT))
    args = ap.parse_args()

    out = Path(args.out)
    if out.exists():
        out.unlink()

    n_neg = n_written = 0
    with open(args.results) as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("outcome") not in ("VERIFIER_NEGATIVE", "POC_PARSE_FAILED",
                                        "SUBMIT_REJECTED"):
                continue
            n_neg += 1
            tid = r["task_id"]
            run_dir = Path(r["run_dir"])
            mr_p = run_dir / "model_response.txt"
            poc_p = run_dir / "poc"
            mr = mr_p.read_text() if mr_p.exists() else ""
            poc_b64 = (base64.b64encode(poc_p.read_bytes()).decode()
                       if poc_p.exists() else None)
            rec = {
                "task_id": tid,
                "project": project_for_task(tid),
                "outcome": r.get("outcome"),
                "vul_exit_code": r.get("vul_exit_code"),
                "fix_exit_code": r.get("fix_exit_code"),
                "model_response_sha256": hashlib.sha256(mr.encode()).hexdigest()
                                         if mr else "",
                "model_response_excerpt": mr[:2000] if mr else "",
                "poc_b64": poc_b64,
                "poc_size": (len(base64.b64decode(poc_b64 + "=" *
                              ((-len(poc_b64)) % 4))) if poc_b64 else 0),
                "model_dt": r.get("model_dt"),
                "model": "Qwen3-Next-80B-A3B-Abliterated",
                "captured_at": time.time(),
                "stratum": r.get("stratum", {}),
            }
            append_negative(out, rec)
            n_written += 1

    print(f"wrote {n_written}/{n_neg} negative records → {out}")


if __name__ == "__main__":
    main()
