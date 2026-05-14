#!/bin/bash
set -eux

pip install --no-cache-dir "huggingface_hub>=0.24.0" "hf_transfer>=0.1.9"

export HF_HUB_ENABLE_HF_TRANSFER=1

echo "[run] Loaded checkpoints tree:"
ls -la /tmp/loaded_checkpoints/ || true
find /tmp/loaded_checkpoints -maxdepth 4 -type f | head -30 || true
echo "[run] HF_REPO_ID=$HF_REPO_ID"
echo "[run] HF_TOKEN length: ${#HF_TOKEN}"

python upload.py
