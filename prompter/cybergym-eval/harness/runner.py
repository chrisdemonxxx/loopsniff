from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from uuid import uuid4

from openai import OpenAI

import run_baseline as baseline
from .profile import profile_cybergym_task
from .schema import Outcome, read_json, write_json


DEFAULT_DB_PATH = Path("/home/cjs/prompter/cybergym-eval/server_poc/poc.db")
DEFAULT_RESULTS = Path("/home/cjs/prompter/cybergym-eval/harness-results.jsonl")


def extract_task_metadata(submit_sh: Path, requested_task_id: str, server: str) -> dict[str, str | bool]:
    text = submit_sh.read_text() if submit_sh.exists() else ""
    def pick(name: str) -> str:
        match = re.search(rf'"{name}":\s*"([^"]+)"', text)
        return match.group(1) if match else ""

    return {
        "requested_task_id": requested_task_id,
        "masked_task_id": pick("task_id"),
        "agent_id": pick("agent_id"),
        "checksum": pick("checksum"),
        "server": server,
        "difficulty": "level1",
        "require_flag": "require_flag\": true" in text,
    }


def write_commands(task_dir: Path, gen_cmd: list[str], submit_cmd: list[str] | None = None) -> None:
    write_json(
        task_dir / "commands.json",
        {
            "gen_task": gen_cmd,
            "submit": submit_cmd or [],
            "verify": "POST /verify-agent-pocs with X-API-Key",
            "note": "CyberGym uses prebuilt Docker runners; no local source build is executed in Stage 0.",
        },
    )


def append_result(results_path: Path, result: dict) -> None:
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with results_path.open("a") as f:
        f.write(json.dumps(result, sort_keys=True) + "\n")


def build_gen_cmd(task_id: str, task_dir: Path, data_dir: Path, server: str, cybergym_root: Path) -> list[str]:
    return [
        "python3", "-m", "cybergym.task.gen_task",
        "--task-id", task_id,
        "--out-dir", str(task_dir),
        "--data-dir", str(data_dir),
        "--server", server,
        "--mask-map", str(cybergym_root / "mask_map.json"),
        "--difficulty", "level1",
    ]


def profile_task(task_id: str, task_dir: Path, data_dir: Path, server: str, cybergym_root: Path) -> dict:
    task_dir.mkdir(parents=True, exist_ok=True)
    gen_cmd = build_gen_cmd(task_id, task_dir, data_dir, server, cybergym_root)
    write_commands(task_dir, gen_cmd)
    baseline.gen_task(task_id, task_dir, data_dir, server, cybergym_root)
    task_meta = extract_task_metadata(task_dir / "submit.sh", task_id, server)
    write_json(task_dir / "task.json", task_meta)
    src_dir = baseline.extract_source(task_dir)
    profile = profile_cybergym_task(task_id, task_dir, src_dir)
    (task_dir / "build.log").write_text(
        "Stage 0 CyberGym profile: using prebuilt Docker runner images; no local build executed.\n"
    )
    return {"task": task_meta, "profile": profile}


def run_task(
    task_id: str,
    *,
    client: OpenAI,
    server: str,
    cybergym_api_key: str,
    cybergym_root: Path,
    data_dir: Path,
    work_dir: Path,
    results_path: Path,
    db_path: Path,
    max_tokens: int,
    stratum: dict | None = None,
) -> dict:
    slug = task_id.replace(":", "_")
    task_dir = work_dir / f"{slug}_{uuid4().hex[:6]}"
    start = time.time()
    baseline.log(f"=== {task_id} -> {task_dir.name} ===")
    try:
        profile_task(task_id, task_dir, data_dir, server, cybergym_root)
    except Exception as exc:
        result = {"task_id": task_id, "run_dir": str(task_dir), "ok": False,
                  "outcome": Outcome.GEN_TASK_FAILED.value, "error": str(exc)}
        write_json(task_dir / "result.json", result)
        append_result(results_path, result)
        return result

    task_meta = read_json(task_dir / "task.json")
    try:
        description = (task_dir / "description.txt").read_text()
        src_dir = task_dir / "src"
        listing = baseline.file_listing(src_dir)
        src_ctx = baseline.collect_source_context(src_dir)
        t0 = time.time()
        content = baseline.call_model(client, description, listing, src_ctx, max_tokens)
        model_dt = time.time() - t0
        (task_dir / "model_response.txt").write_text(content)
    except Exception as exc:
        result = {"task_id": task_id, "run_dir": str(task_dir), "ok": False,
                  "outcome": Outcome.MODEL_ERROR.value, "error": str(exc)}
        write_json(task_dir / "result.json", result)
        append_result(results_path, result)
        return result

    poc_bytes = baseline.parse_poc(content)
    if poc_bytes is None:
        result = {"task_id": task_id, "run_dir": str(task_dir), "ok": False,
                  "outcome": Outcome.POC_PARSE_FAILED.value, "model_dt": model_dt}
        write_json(task_dir / "result.json", result)
        append_result(results_path, result)
        return result

    poc_path = task_dir / "poc"
    poc_path.write_bytes(poc_bytes)
    submit_cmd = ["bash", str(task_dir / "submit.sh"), str(poc_path)]
    write_commands(task_dir, build_gen_cmd(task_id, task_dir, data_dir, server, cybergym_root), submit_cmd)
    submit_result = baseline.submit(task_dir / "submit.sh", poc_path)
    write_json(task_dir / "submit.json", submit_result)
    (task_dir / "sanitizer.log").write_text(submit_result.get("output", ""))

    exit_code = submit_result.get("exit_code")
    vul_crashed = exit_code is not None and exit_code != 0
    agent_id = task_meta.get("agent_id")
    verifier_payload = {}
    db_row = None
    if vul_crashed and agent_id:
        verifier_payload = baseline.verify_agent(server, agent_id, cybergym_api_key)
        write_json(task_dir / "verifier.json", verifier_payload)
        db_row = baseline.db_lookup(db_path, agent_id)
    else:
        write_json(task_dir / "verifier.json", {"skipped": True, "reason": "vulnerable runner did not fail"})

    fix_exit = db_row.get("fix_exit_code") if db_row else None
    confirmed = bool(db_row and db_row.get("vul_exit_code") not in (None, 0) and fix_exit == 0)
    if confirmed:
        outcome = Outcome.VERIFIER_POSITIVE
    elif exit_code is None:
        outcome = Outcome.SUBMIT_REJECTED
    else:
        outcome = Outcome.VERIFIER_NEGATIVE

    result = {
        "task_id": task_id,
        "run_dir": str(task_dir),
        "ok": confirmed,
        "outcome": outcome.value,
        "agent_id": agent_id,
        "poc_size": len(poc_bytes),
        "model_dt": model_dt,
        "total_dt": time.time() - start,
        "vul_exit_code": exit_code,
        "fix_exit_code": fix_exit,
        "submit_poc_id": submit_result.get("poc_id"),
        "verifier": verifier_payload,
        "stratum": stratum or {},
    }
    write_json(task_dir / "result.json", result)
    append_result(results_path, result)
    baseline.log(
        f"  result: outcome={outcome.value} vul={exit_code} fix={fix_exit} confirmed={confirmed}"
    )
    return result


def run_tasks(
    tasks: list[str],
    *,
    server: str,
    cybergym_root: Path,
    data_dir: Path,
    work_dir: Path,
    results_path: Path,
    db_path: Path = DEFAULT_DB_PATH,
    max_tokens: int = 8000,
    stratum_by_task: dict[str, dict] | None = None,
) -> list[dict]:
    api_key = os.environ.get("BASETEN_API_KEY")
    if not api_key:
        raise SystemExit("Set BASETEN_API_KEY")
    cybergym_api_key = os.environ.get("CYBERGYM_API_KEY", "cybergym-030a0cd7-5908-4862-8ab9-91f2bfc7b56d")
    client = OpenAI(base_url=baseline.ENDPOINT, api_key=api_key, timeout=600.0)
    work_dir.mkdir(parents=True, exist_ok=True)
    results = [
        run_task(
            task_id,
            client=client,
            server=server,
            cybergym_api_key=cybergym_api_key,
            cybergym_root=cybergym_root,
            data_dir=data_dir,
            work_dir=work_dir,
            results_path=results_path,
            db_path=db_path,
            max_tokens=max_tokens,
            stratum=(stratum_by_task or {}).get(task_id),
        )
        for task_id in tasks
    ]
    passed = sum(1 for r in results if r.get("ok"))
    baseline.log(f"=== DONE pass@1 = {passed}/{len(results)} = {passed / max(len(results), 1):.3f} ===")
    return results


def replay_run(run_dir: Path, *, server: str, cybergym_api_key: str, db_path: Path = DEFAULT_DB_PATH) -> dict:
    task_meta = read_json(run_dir / "task.json") if (run_dir / "task.json").exists() else {}
    if not task_meta:
        task_meta = extract_task_metadata(run_dir / "submit.sh", "unknown", server)
    agent_id = task_meta.get("agent_id")
    if not agent_id:
        raise ValueError(f"Cannot replay {run_dir}: missing agent_id")

    verifier_payload = baseline.verify_agent(server, str(agent_id), cybergym_api_key)
    db_row = baseline.db_lookup(db_path, str(agent_id)) or {}
    result = {
        "run_dir": str(run_dir),
        "task_id": task_meta.get("requested_task_id") or "unknown",
        "agent_id": agent_id,
        "ok": db_row.get("vul_exit_code") not in (None, 0) and db_row.get("fix_exit_code") == 0,
        "vul_exit_code": db_row.get("vul_exit_code"),
        "fix_exit_code": db_row.get("fix_exit_code"),
        "verifier": verifier_payload,
    }
    write_json(run_dir / "replay-verifier.json", verifier_payload)
    write_json(run_dir / "replay-result.json", result)
    return result

