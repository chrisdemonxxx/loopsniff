# w11-merge — Tier-1.1 LoRA Merge

Merge SFT LoRA adapter (job `wldrkeq`, `checkpoint-210`) into the BF16 base model
`huihui-ai/Huihui-Qwen3-Next-80B-A3B-Instruct-abliterated`. Recovery path for the
vLLM + LoRA + Qwen3-Next-MoE incompatibility documented in `RELEASE_NOTES_TIER1.md`.

## Why

vLLM cannot apply LoRA target modules (q/k/v/o/gate/up/down_proj as trained) to
Qwen3-Next's MoE expert layout — three deploy attempts on H100:4 all hit
`'NoneType' object has no attribute 'shape'` in the LoRA slice loader. Merging
offline produces a flat BF16 model that vLLM serves without `--enable-lora`.

## What this job does

1. Baseten auto-downloads `checkpoint-210` adapter (~13 GB) to `/tmp/loaded_checkpoints`
   via `LoadCheckpointConfig`.
2. Loads base model in BF16 sharded across 4×H100 with `device_map="auto"`.
3. `PeftModel.from_pretrained(base, adapter)` → `merge_and_unload(safe_merge=True)`.
4. Saves merged weights to `$BT_CHECKPOINT_DIR/merged/` as 10-GB-sharded safetensors
   plus tokenizer + chat_template + MERGE_MANIFEST.json.

## Compute

- 4×H100 (320 GiB VRAM total). Base BF16 is ~160 GiB; merge needs base + adapter
  + a temporary copy of each merged layer. 4×H100 leaves comfortable headroom.
- Estimated runtime: ~30–60 min (model load ~10 min, merge ~5 min, save ~15 min).
- Estimated cost: ~$30 at H100:4 list rates.

## Submit

```bash
cd training/w11-merge
truss train push config.py
truss train logs --job-id <new_job_id> --tail
```

## After completion

The job emits a single checkpoint named `merged`. Pull it with:

```bash
truss train download --job-id <new_job_id> --target-directory ./merged_model
# OR fetch presigned URLs for an external_data block:
truss train get_checkpoint_urls --job-id <new_job_id>
```

Then update `prompter/baseten-qwen3next-abliterated/config.yaml`:

- Change `model_metadata.repo_id` (or the `external_data`/`weights.source`
  pointer) to either a private HF repo you upload `./merged_model/merged/` to,
  or to the presigned URL set from `get_checkpoint_urls`.
- Remove `--enable-lora`, `--lora-modules`, `--max-loras`, `--max-lora-rank`
  from `start_command` — none are needed once the LoRA is baked in.
- Keep `tensor-parallel-size 4` and `max-model-len 131072`.

Then `truss push` the serving config and update
`harness/subagents/llm_client.py` to point at the new deployment.
