#!/bin/bash
set -eux

# Pinned versions chosen to satisfy two constraints simultaneously:
#   1. transformers must know `qwen3_next` model_type (added in 4.57+).
#   2. peft must NOT call WeightConverter(distributed_operation=...) which is
#      what peft >= 0.17 does and breaks adapter loading on currently-released
#      transformers (failed jobs qj7d9pq with peft 0.17, then 32zpox3 with
#      transformers 4.55.2 not knowing qwen3_next).
# Adapter target_modules are q/k/v/o_proj only (standard attention, no MoE FFN),
# so peft 0.16's architecture-agnostic LoRA injection round-trips it cleanly
# even though 0.16 predates Qwen3-Next.
pip install --no-cache-dir \
    "peft==0.16.0" \
    "transformers==4.57.0" \
    "accelerate==1.3.0" \
    "safetensors>=0.4.5" \
    "huggingface_hub>=0.24.0"

# Diagnostic: list the auto-downloaded LoRA tree
echo "[run] Loaded checkpoints tree:"
ls -la /tmp/loaded_checkpoints/ || true
find /tmp/loaded_checkpoints -maxdepth 4 -type f | head -50 || true
echo "[run] BT_CHECKPOINT_DIR=$BT_CHECKPOINT_DIR"

python merge.py
