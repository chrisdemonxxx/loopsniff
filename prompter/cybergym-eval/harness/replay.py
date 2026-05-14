"""Replay PoC parsing on existing run dirs without re-calling the model.

Used after a parser fix to recover previously POC_PARSE_FAILED tasks. Reads
each run dir's cached model_response.txt, re-runs parse_poc, submits, verifies,
and writes a fresh result row to results.jsonl.
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

import run_baseline as baseline
from harness.runner import (
    Outcome, extract_task_metadata, append_result, write_json, read_json,
)


def replay_one(run_dir: Path, server: str, cybergym_api_key: str,
               db_path: Path, results_path: Path) -> dict:
    task_meta = read_json(run_dir / "task.json") or extract_task_metadata(
        run_dir / "submit.sh", "unknown", server)
    task_id = (task_meta.get("requested_task_id")
               or task_meta.get("task_id")
               or run_dir.name)
    agent_id = task_meta.get("agent_id")

    content = (run_dir / "model_response.txt").read_text()
    poc_bytes = baseline.parse_poc(content)
    if poc_bytes is None:
        result = {"task_id": task_id, "run_dir": str(run_dir), "ok": False,
                  "outcome": Outcome.POC_PARSE_FAILED.value, "replay": True}
        write_json(run_dir / "result.json", result)
        append_result(results_path, result)
        return result

    poc_path = run_dir / "poc"
    poc_path.write_bytes(poc_bytes)
    submit_result = baseline.submit(run_dir / "submit.sh", poc_path)
    write_json(run_dir / "submit.json", submit_result)
    (run_dir / "sanitizer.log").write_text(submit_result.get("output", ""))

    exit_code = submit_result.get("exit_code")
    vul_crashed = exit_code is not None and exit_code != 0
    verifier_payload = {}
    db_row = None
    if vul_crashed and agent_id:
        verifier_payload = baseline.verify_agent(server, agent_id, cybergym_api_key)
        write_json(run_dir / "verifier.json", verifier_payload)
        db_row = baseline.db_lookup(db_path, agent_id)
    else:
        write_json(run_dir / "verifier.json",
                   {"skipped": True, "reason": "vulnerable runner did not fail"})

    fix_exit = db_row.get("fix_exit_code") if db_row else None
    confirmed = bool(db_row and db_row.get("vul_exit_code") not in (None, 0)
                     and fix_exit == 0)
    if confirmed:
        outcome = Outcome.VERIFIER_POSITIVE
    elif exit_code is None:
        outcome = Outcome.SUBMIT_REJECTED
    else:
        outcome = Outcome.VERIFIER_NEGATIVE

    # Preserve original stratum from prior result.json if present
    prior = read_json(run_dir / "result.json") or {}
    stratum = prior.get("stratum", {})

    result = {
        "task_id": task_id,
        "run_dir": str(run_dir),
        "ok": confirmed,
        "outcome": outcome.value,
        "agent_id": agent_id,
        "poc_size": len(poc_bytes),
        "vul_exit_code": exit_code,
        "fix_exit_code": fix_exit,
        "submit_poc_id": submit_result.get("poc_id"),
        "verifier": verifier_payload,
        "stratum": stratum,
        "replay": True,
    }
    write_json(run_dir / "result.json", result)
    append_result(results_path, result)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dirs", nargs="+", required=True)
    ap.add_argument("--server", default=os.environ.get("CYBERGYM_SERVER",
                                                       "http://127.0.0.1:8666"))
    ap.add_argument("--db-path", default="/tmp/cgserver.db")
    ap.add_argument("--results-path", default="harness-results.jsonl")
    args = ap.parse_args()

    api_key = os.environ.get("CYBERGYM_API_KEY", "")
    results_path = Path(args.results_path)
    db_path = Path(args.db_path)

    for d in args.run_dirs:
        rd = Path(d)
        if not rd.exists():
            print(f"SKIP: {d} (not found)"); continue
        r = replay_one(rd, args.server, api_key, db_path, results_path)
        print(f"{r['task_id']}: outcome={r['outcome']} "
              f"vul={r.get('vul_exit_code')} fix={r.get('fix_exit_code')} "
              f"poc_size={r.get('poc_size')}")


if __name__ == "__main__":
    main()
