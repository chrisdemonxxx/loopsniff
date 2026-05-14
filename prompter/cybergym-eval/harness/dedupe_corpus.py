"""w04d dedupe pass — remove duplicate records from raw corpus.

Uses dedupe_key (composite: project, vuln_function, sanitizer_stack_sha256,
poc_sha256[:16], vul_binary_sha256[:16]) to identify duplicates. Keeps first
occurrence, drops rest.

Usage:
    python -m harness.dedupe_corpus
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "sft-corpus" / "raw"
DEDUPED_DIR = ROOT / "sft-corpus" / "deduped"

def main() -> int:
    # Find all raw/*.v1.jsonl files
    raw_files = list(RAW_DIR.glob("*.v1.jsonl"))
    if not raw_files:
        print("[dedupe] no raw/*.v1.jsonl files found", file=sys.stderr)
        return 1
    
    print(f"[dedupe] found {len(raw_files)} raw files:", flush=True)
    for f in raw_files:
        print(f"  {f.name}", flush=True)
    
    # Load all records
    all_records = []
    for f in raw_files:
        for line in f.read_text().splitlines():
            if line.strip():
                try:
                    rec = json.loads(line)
                    all_records.append(rec)
                except Exception as e:
                    print(f"[dedupe] skip malformed line in {f.name}: {e}", flush=True)
    
    print(f"[dedupe] loaded {len(all_records)} total records", flush=True)
    
    # Dedupe by dedupe_key
    seen_keys = set()
    deduped = []
    dups_by_source = Counter()
    
    for rec in all_records:
        key = rec.get("dedupe_key")
        if not key:
            print(f"[dedupe] WARNING: record {rec.get('record_id')} has no dedupe_key, keeping anyway", flush=True)
            deduped.append(rec)
            continue
        
        if key in seen_keys:
            dups_by_source[rec.get("provenance", {}).get("source", "?")] += 1
            continue
        
        seen_keys.add(key)
        deduped.append(rec)
    
    print(f"[dedupe] kept {len(deduped)} unique, dropped {len(all_records) - len(deduped)} duplicates", flush=True)
    if dups_by_source:
        print(f"[dedupe] duplicates by source: {dict(dups_by_source)}", flush=True)
    
    # Write to deduped/all.v1.jsonl
    DEDUPED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DEDUPED_DIR / "all.v1.jsonl"
    with out_path.open("w") as f:
        for rec in deduped:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
    
    print(f"[dedupe] wrote {out_path}", flush=True)
    
    # Stats
    by_source = Counter(r.get("provenance", {}).get("source", "?") for r in deduped)
    by_split = Counter(r.get("split", "?") for r in deduped)
    by_lang = Counter(r.get("language", "?") for r in deduped)
    by_san = Counter(r["verification"]["sanitizer_type"] for r in deduped)
    
    print(f"\n[dedupe] final corpus stats:")
    print(f"  total: {len(deduped)}")
    print(f"  by source: {dict(by_source)}")
    print(f"  by split: {dict(by_split)}")
    print(f"  by language: {dict(by_lang)}")
    print(f"  by sanitizer: {dict(by_san)}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
