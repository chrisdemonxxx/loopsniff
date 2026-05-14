#!/bin/bash
set -eux

pip install --no-cache-dir \
    "peft>=0.17.0" \
    "transformers>=4.55.0" \
    "accelerate>=1.3.0" \
    "safetensors>=0.4.5" \
    "huggingface_hub>=0.24.0"

# Diagnostic: list the auto-downloaded LoRA tree
echo "[run] Loaded checkpoints tree:"
ls -la /tmp/loaded_checkpoints/ || true
find /tmp/loaded_checkpoints -maxdepth 4 -type f | head -50 || true
echo "[run] BT_CHECKPOINT_DIR=$BT_CHECKPOINT_DIR"

python merge.py
