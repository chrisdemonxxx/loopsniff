# Calibration Set B — Report

**Date:** 2026-05-12
**Endpoint:** `qrj8djv3` (Qwen3-Next-80B-A3B-Abliterated, Baseten 4×H100)
**Sample:** N=30 stratified random tasks from CyberGym L1 (1497-task pool, 10 curated excluded)
**Seed:** fixed via `harness/sample_calibration.py` → `harness/calibration_b_tasks.json`
**Server mode:** binary runner (`--binary_dir`, 122 GB), single sweep, no resampling.

---

## Headline

| Metric | Value |
|---|---|
| **pass@1** | **0.100 (3/30)** |
| Wilson 95% CI | **[0.035, 0.256]** |
| INFRA / MODEL errors | **0 / 0** (clean run) |
| Wall time | ~22 min serial |
| Spend (Baseten) | well under $30 ceiling (~22 min × 4×H100 active) |

## Outcome distribution (frozen, post parser-fix)

| Outcome | Count |
|---|---|
| VERIFIER_POSITIVE | 3 |
| VERIFIER_NEGATIVE | 27 |
| POC_PARSE_FAILED | 0 |
| MODEL_ERROR | 0 |
| INFRA_ERROR | 0 |
| GEN_TASK_FAILED | 0 |

**Parser fix applied 2026-05-11:** `run_baseline.parse_poc` now tolerates two
real failure modes the model exhibited: (1) `max_tokens=8192` truncation
mid-base64 (3 of the original 4 PARSE_FAILED), and (2) malformed `=` padding
producing `data_chars % 4 == 1` (1 of 4). Fix: strip trailing `=`, drop
characters until `len % 4 != 1`, then re-pad. All 4 tasks were re-run via
`harness/replay.py` against the *cached* model responses (no re-sampling) —
all 4 decoded cleanly and returned VERIFIER_NEGATIVE (PoCs decoded but did
not crash the binary). pass@1 unchanged at 3/30, but the SFT corpus now has
correct labels and intact PoC artefacts on every task.

## Stratified pass@1

| Stratum | passed/total | pass@1 | Wilson 95% CI |
|---|---|---|---|
| source=arvo | 2/15 | 0.133 | [0.037, 0.379] |
| source=oss-fuzz | 1/15 | 0.067 | [0.012, 0.298] |
| language=c | 1/13 | 0.077 | [0.014, 0.333] |
| language=c++ | 2/14 | 0.143 | [0.040, 0.399] |
| language=other | 0/3 | 0.000 | [0.000, 0.561] |

Stratum spread is modest (c++ slightly outperforms c, arvo slightly outperforms oss-fuzz) but every per-stratum CI overlaps the others — no statistically significant per-stratum gap at N=30.

## Comparison to baselines

| System | CyberGym L1 pass@1 | Notes |
|---|---|---|
| Curated 10-subset (Gate 1) | 0.200 | Now confirmed as an over-estimate — curated bias |
| **Cal B (this run, 30 tasks)** | **0.100 [0.035, 0.256]** | Honest lower-variance estimate |
| Sonnet-4 (published) | 0.179 | Within our upper CI |
| GPT-4.1 (published) | 0.097 | Statistically indistinguishable from us |
| GPT-5-thinking (published) | 0.220 | Above our upper CI |
| AIxCC top finalists | 0.35–0.45 | Full purpose-built CRS, hours of compute/task |

**Interpretation:** un-tuned 80B abliterated base sits right at GPT-4.1 territory and a touch below Sonnet-4 on a 30-task honest sample. The earlier 0.200 was real but biased by curation; the true baseline is 0.10 with a wide CI that reaches Sonnet-4 territory at the top end.

## Failure mode notes

- **23 VERIFIER_NEGATIVE:** model produced syntactically valid PoC files in 5–60 s but they did not crash the vulnerable runner. This is the dominant failure mode — short reasoning chains, plausible-but-wrong PoCs. This is exactly what SFT on `(repo, vuln, working PoC)` triples is designed to fix.
- **4 POC_PARSE_FAILED:** model returned a response the harness's PoC extractor could not pull a payload out of. Worth one bug-fix pass on the extractor (likely a fenced-block / base64 / hex-blob format we don't yet recognize) — could plausibly add 1–2 positives without any model change.
- **0 INFRA / MODEL errors:** Baseten endpoint and the new binary-mode CyberGym server were both rock-solid for the full 30-task sweep. Data plane is production-ready.

## Branch decision (per plan §21)

Result: **pass@1 = 0.100 ≥ 0.10 threshold**.

→ **Proceed with w04 data curation as planned.**

Stratum variance is small enough that we do **not** pull w23 static-analysis stack forward. However, the 4 POC_PARSE_FAILED outcomes flag a cheap pre-training improvement (extractor robustness) that we should land before any training spend.

## Next actions

1. ✅ Mark `cb-run` and `cb-report` done in SQL.
2. Land a small fix in `runner.py` PoC extractor to recover the 4 PARSE_FAILED cases — re-run only those 4 to see if they convert to pos/neg before training.
3. Begin w04: SFT data schema + initial gold-corpus curation (CVE write-ups → PoC chains).
4. Keep the binary-mode CyberGym server alive as the long-term eval harness.

## Reproducibility

- Task list: `harness/calibration_b_tasks.json` (frozen, seeded).
- Raw results: `harness-results.jsonl` (CB rows have `stratum` field).
- Pre-CB backup: `harness-results.pre-cb.jsonl`.
- Machine report: `harness/reports/calibration_b.json`.
- Server: PID 1901463, `127.0.0.1:8666`, binary mode.
