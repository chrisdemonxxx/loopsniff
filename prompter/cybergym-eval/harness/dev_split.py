"""w04e dev split — stratified train/dev split for in-training SFT eval.

Splits sft-corpus/deduped/all.v1.jsonl into train.jsonl and dev.jsonl.
Strategy: 90% train / 10% dev, stratified by (source, language, sanitizer_type).
Only splits records with split=='train' (excludes 'excluded' records from eval set).

Usage:
    python -m harness.dev_split
"""
from __future__ import annotations
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEDUPED_DIR = ROOT / "sft-corpus" / "deduped"
ALL_FILE = DEDUPED_DIR / "all.v1.jsonl"
TRAIN_FILE = DEDUPED_DIR / "train.v1.jsonl"
DEV_FILE = DEDUPED_DIR / "dev.v1.jsonl"

TRAIN_RATIO = 0.95
SEED = 20260511


def main() -> int:
    if not ALL_FILE.exists():
        print(f"[split] {ALL_FILE} not found", file=sys.stderr)
        return 1
    
    records = [json.loads(l) for l in ALL_FILE.read_text().splitlines() if l.strip()]
    print(f"[split] loaded {len(records)} records", flush=True)
    
    # Filter to split=='train' only
    trainable = [r for r in records if r.get("split") == "train"]
    excluded = [r for r in records if r.get("split") != "train"]
    print(f"[split] trainable: {len(trainable)}, excluded: {len(excluded)}", flush=True)
    
    # Stratify by (source, language, sanitizer_type)
    strata: dict[tuple, list] = defaultdict(list)
    for r in trainable:
        source = r.get("provenance", {}).get("source", "?")
        lang = r.get("language", "?")
        san = r.get("verification", {}).get("sanitizer_type", "?")
        strata[(source, lang, san)].append(r)
    
    print(f"[split] {len(strata)} strata", flush=True)
    
    rng = random.Random(SEED)
    train = []
    dev = []
    
    for stratum_key, items in strata.items():
        rng.shuffle(items)
        split_idx = int(len(items) * TRAIN_RATIO)
        train.extend(items[:split_idx])
        dev.extend(items[split_idx:])
        if len(items[split_idx:]) > 0:
            print(f"  {stratum_key}: {len(items)} -> train={split_idx}, dev={len(items)-split_idx}", flush=True)
    
    print(f"\n[split] final: train={len(train)}, dev={len(dev)}", flush=True)
    
    # Write
    with TRAIN_FILE.open("w") as f:
        for r in train:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    print(f"[split] wrote {TRAIN_FILE}", flush=True)
    
    with DEV_FILE.open("w") as f:
        for r in dev:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    print(f"[split] wrote {DEV_FILE}", flush=True)
    
    # Verify gate
    if len(train) < 300:
        print(f"\n[split] WARNING: train set has {len(train)} < 300 records!", file=sys.stderr)
        return 2
    
    print(f"\n[split] ✓ GATE PASSED: train set has {len(train)} >= 300 records", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
