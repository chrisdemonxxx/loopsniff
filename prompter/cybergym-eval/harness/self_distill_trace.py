"""Self-distill trace generation (w04c).

Takes GoldRecords with empty solve_trace, calls the abliterated 80B to fill the
structured <analysis> block with evidence-grounded fields. This is the w04c
self-distill step.

Usage:
    # Smoke test on seed positives (re-generates their traces to validate prompting)
    python -m harness.self_distill_trace --smoke-test
    
    # Run on actual corpus (e.g., from_arvo.v1.jsonl records)
    python -m harness.self_distill_trace --input sft-corpus/raw/from_arvo.v1.jsonl --max-records 50
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent

SYSTEM_PROMPT = """You are a vulnerability analysis engine. You will be given a binary crash reproducer and sanitizer output for a known confirmed vulnerability. Your job is to fill each field below with concrete, evidence-grounded analysis. Do not speculate. If you cannot ground a field in the provided sanitizer output or source context, write UNKNOWN. Do not write prose explanations outside the structured fields.

Respond only in this format:
<analysis>
  <hypothesis>One sentence: what class of bug this is and why, citing the sanitizer output line that confirms it.</hypothesis>
  <vulnerable_function>Exact function name and file:line from sanitizer output. No guessing.</vulnerable_function>
  <input_construction>Describe what property of the PoC input triggers the bug. Be specific: byte offset, value range, or structural constraint.</input_construction>
  <expected_crash_condition>Describe the memory or logic state at crash time as reported by the sanitizer. Quote the sanitizer line.</expected_crash_condition>
  <verification_result>CONFIRMED if sanitizer output matches hypothesis. PARTIAL if partially matches. MISMATCH if contradicts.</verification_result>
</analysis>"""


def build_user_prompt(record: dict) -> str:
    """Build user prompt from GoldRecord dict."""
    verif = record.get("verification", {})
    target = record.get("target", {})
    
    poc_sha = hashlib.sha256(target.get("poc_b64", "").encode()).hexdigest()[:16]
    poc_len = len(target.get("poc_b64", "")) * 3 // 4  # rough byte length from b64
    
    user = f"""## Vulnerability metadata
Task ID: {record.get('task_id', '?')}
Project: {record.get('project', '?')}
Language: {record.get('language', '?')}
Crash type: {verif.get('sanitizer_type', '?')}

## Proof-of-concept input
SHA256: {poc_sha}
Size: {poc_len} bytes
Delivery: {target.get('delivery', '?')}

## Sanitizer output
{verif.get('sanitizer_excerpt', '(no sanitizer output available)')}

## Your task
Extract structured analysis from the above sanitizer output. Fill each XML field in the required format. If any field cannot be determined from the provided evidence, write UNKNOWN.
"""
    return user


def call_model(client: OpenAI, record: dict, temperature: float = 0.3, max_tokens: int = 2048) -> str:
    """Call the abliterated 80B to generate trace."""
    user_prompt = build_user_prompt(record)
    resp = client.chat.completions.create(
        model="Qwen3-Next-80B-A3B-Abliterated",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def parse_trace(text: str) -> tuple[dict[str, Any], str]:
    """Parse <analysis> block into SolveTrace dict. Returns (trace_dict, quality)."""
    import re
    fields = {}
    for tag in ["hypothesis", "vulnerable_function", "input_construction",
                "expected_crash_condition", "verification_result"]:
        rx = re.compile(f"<{tag}>(.+?)</{tag}>", re.DOTALL)
        m = rx.search(text)
        if m:
            val = m.group(1).strip()
            fields[tag] = val if val and val.lower() != "unknown" else None
        else:
            fields[tag] = None
    
    # Quality: high if all 5 fields populated, low otherwise
    populated = sum(1 for v in fields.values() if v)
    quality = "high" if populated == 5 else "low"
    
    # Add derived fields for SolveTrace schema
    if fields.get("vulnerable_function") and ":" in (fields["vulnerable_function"] or ""):
        # Assume format "function_name file:line" or just "file:line"
        parts = fields["vulnerable_function"].split()
        if len(parts) >= 2:
            fields["vulnerable_file_line"] = parts[-1]  # last token is file:line
            fields["vulnerable_function"] = " ".join(parts[:-1]) or parts[0]
        else:
            fields["vulnerable_file_line"] = None
    else:
        fields["vulnerable_file_line"] = None
    
    fields["cwe"] = None  # Not extractable from sanitizer alone without source analysis
    
    # rendered_sha256 for dedupe
    render_str = json.dumps({k: fields.get(k) for k in [
        "hypothesis", "vulnerable_function", "vulnerable_file_line", "cwe",
        "input_construction", "expected_crash_condition", "verification_result"
    ]}, sort_keys=True)
    fields["rendered_sha256"] = hashlib.sha256(render_str.encode()).hexdigest()
    
    return fields, quality


def distill_one(client: OpenAI, record: dict) -> tuple[dict, str, str]:
    """Generate trace for one record. Returns (updated_record, quality, raw_response)."""
    response_text = call_model(client, record)
    trace_dict, quality = parse_trace(response_text)
    
    # Update record with solve_trace
    record_copy = dict(record)
    record_copy["solve_trace"] = trace_dict
    return record_copy, quality, response_text


def smoke_test() -> int:
    """Run on seed positives to validate prompting."""
    seed_path = ROOT / "sft-corpus" / "raw" / "from_model_positives.v1.jsonl"
    if not seed_path.exists():
        print(f"[smoke] {seed_path} not found", file=sys.stderr)
        return 1
    
    client = OpenAI(
        base_url="https://model-qrj8djv3.api.baseten.co/environments/production/sync/v1",
        api_key="jhgmDoan.mIaf8jdD0UjXLMEjSk19iEAIvmhyBcRN",
    )
    
    records = [json.loads(l) for l in seed_path.read_text().splitlines() if l.strip()]
    print(f"[smoke] loaded {len(records)} seed records", flush=True)
    
    # Estimate cost
    # Avg input: 500 tokens (sanitizer excerpt ~3KB), output: 300 tokens
    # Baseten Qwen3-Next-80B: $0.50 per 1M input tokens, $1.50 per 1M output tokens
    # 5 records × (500 input + 300 output) = 4000 tokens ≈ $0.0026
    est_input_tok = 500 * len(records)
    est_output_tok = 300 * len(records)
    est_cost = (est_input_tok * 0.50 + est_output_tok * 1.50) / 1e6
    print(f"[smoke] estimated cost: ${est_cost:.4f} ({est_input_tok} input + {est_output_tok} output tokens)", flush=True)
    print("[smoke] proceeding with smoke test...", flush=True)
    
    results = []
    for i, rec in enumerate(records):
        print(f"\n[smoke] record {i+1}/{len(records)}: {rec.get('task_id')}", flush=True)
        try:
            updated, quality, raw = distill_one(client, rec)
            results.append((updated, quality, raw))
            trace = updated["solve_trace"]
            print(f"  quality: {quality}")
            print(f"  hypothesis: {trace.get('hypothesis', 'NONE')[:100]}")
            print(f"  vulnerable_function: {trace.get('vulnerable_function', 'NONE')}")
            print(f"  vulnerable_file_line: {trace.get('vulnerable_file_line', 'NONE')}")
            print(f"  input_construction: {(trace.get('input_construction') or 'NONE')[:80]}")
            print(f"  expected_crash_condition: {(trace.get('expected_crash_condition') or 'NONE')[:80]}")
            print(f"  verification_result: {trace.get('verification_result', 'NONE')}")
        except Exception as e:
            print(f"  ERROR: {repr(e)}", flush=True)
    
    high_q = sum(1 for _, q, _ in results if q == "high")
    print(f"\n[smoke] DONE: {high_q}/{len(results)} high-quality traces", flush=True)
    return 0


def batch_distill(input_path: Path, max_records: int | None) -> int:
    """Run on actual corpus."""
    if not input_path.exists():
        print(f"[batch] {input_path} not found", file=sys.stderr)
        return 1
    
    client = OpenAI(
        base_url="https://model-qrj8djv3.api.baseten.co/environments/production/sync/v1",
        api_key="jhgmDoan.mIaf8jdD0UjXLMEjSk19iEAIvmhyBcRN",
    )
    
    records = [json.loads(l) for l in input_path.read_text().splitlines() if l.strip()]
    if max_records:
        records = records[:max_records]
    print(f"[batch] loaded {len(records)} records from {input_path}", flush=True)
    
    # Cost estimate
    est_input_tok = 500 * len(records)
    est_output_tok = 300 * len(records)
    est_cost = (est_input_tok * 0.50 + est_output_tok * 1.50) / 1e6
    print(f"[batch] estimated cost: ${est_cost:.2f}", flush=True)
    print("[batch] Press Ctrl-C to abort, or wait 10s to proceed...", flush=True)
    try:
        time.sleep(10)
    except KeyboardInterrupt:
        print("\n[batch] aborted by user", flush=True)
        return 2
    
    out_path = input_path.parent / (input_path.stem + ".traced.jsonl")
    with out_path.open("w") as f:
        for i, rec in enumerate(records):
            try:
                updated, quality, _ = distill_one(client, rec)
                f.write(json.dumps(updated, separators=(",", ":")) + "\n")
                if (i + 1) % 10 == 0:
                    print(f"[batch] {i+1}/{len(records)} quality={quality}", flush=True)
            except Exception as e:
                print(f"[batch] {i+1} ERROR: {repr(e)}", flush=True)
    
    print(f"[batch] DONE wrote {out_path}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke-test", action="store_true", help="Run smoke test on seed positives")
    ap.add_argument("--input", type=Path, help="Input JSONL (for batch distill)")
    ap.add_argument("--max-records", type=int, help="Max records to process")
    args = ap.parse_args()
    
    if args.smoke_test:
        return smoke_test()
    elif args.input:
        return batch_distill(args.input, args.max_records)
    else:
        print("Usage: --smoke-test OR --input <path>", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
