"""Quick status + project-distribution check for the ARVO harvest.

Usage: python -m harness.harvest_status
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSONL = ROOT / "sft-corpus" / "raw" / "from_arvo.v1.jsonl"
REJECT = ROOT / "sft-corpus" / "raw" / "from_arvo.rejections.csv"
STATE = ROOT / "sft-corpus" / "raw" / "from_arvo.state.json"


def main() -> int:
    if STATE.exists():
        s = json.loads(STATE.read_text())
        print(f"[state] attempts={s.get('attempts')} successes={s.get('successes')} "
              f"target={s.get('target')} elapsed={s.get('elapsed_sec',0)//60}m "
              f"finished={s.get('finished', False)}")

    if not JSONL.exists():
        print("[corpus] no records yet")
        return 0
    recs = [json.loads(l) for l in JSONL.read_text().splitlines() if l.strip()]
    print(f"[corpus] total records: {len(recs)}")
    by_proj = Counter(r["project"] for r in recs)
    by_split = Counter(r["split"] for r in recs)
    by_san = Counter(r["verification"]["sanitizer_type"] for r in recs)
    by_lang = Counter(r["language"] for r in recs)
    dedupes = Counter(r["dedupe_key"] for r in recs)

    print(f"[split] {dict(by_split)}")
    print(f"[lang]  {dict(by_lang)}")
    print(f"[san]   {dict(by_san)}")

    train_count = by_split.get("train", 0)
    print(f"\n[gate]  train={train_count}/300 ({train_count/3:.0f}%)")

    print(f"\n[projects] {len(by_proj)} distinct, top 15:")
    for proj, n in by_proj.most_common(15):
        pct = 100.0 * n / len(recs)
        flag = "  <-- skew" if pct > 8 else ""
        print(f"  {proj:24s} {n:4d}  {pct:5.1f}%{flag}")

    dups = sum(1 for v in dedupes.values() if v > 1)
    if dups:
        print(f"\n[dedupe] {dups} dedupe_keys with duplicates "
              f"({sum(v-1 for v in dedupes.values() if v>1)} extra records)")
    else:
        print("\n[dedupe] no duplicate keys")

    if REJECT.exists():
        import csv
        with REJECT.open() as f:
            r = list(csv.DictReader(f))
        print(f"\n[rejects] {len(r)} total")
        rc = Counter(row["reason"] for row in r)
        for reason, n in rc.most_common():
            print(f"  {reason:20s} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
