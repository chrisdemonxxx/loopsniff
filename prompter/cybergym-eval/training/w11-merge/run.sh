#!/bin/bash
set -eux

# Pinned versions: peft 0.17.0 introduced transformers_weight_conversion.py which
# calls WeightConverter(distributed_operation=...) — incompatible with transformers
# < 4.57 (see prior failed job qj7d9pq). Pin to the pair used at SFT training time
# (peft 0.16.x + transformers 4.55.x) which uses the legacy direct adapter load
# path and is known to round-trip the wldrkeq adapter without the converter.
pip install --no-cache-dir \
    "peft==0.16.0" \
    "transformers==4.55.2" \
    "accelerate==1.3.0" \
    "safetensors>=0.4.5" \
    "huggingface_hub>=0.24.0"

# Diagnostic: list the auto-downloaded LoRA tree
echo "[run] Loaded checkpoints tree:"
ls -la /tmp/loaded_checkpoints/ || true
find /tmp/loaded_checkpoints -maxdepth 4 -type f | head -50 || true
echo "[run] BT_CHECKPOINT_DIR=$BT_CHECKPOINT_DIR"

python merge.py
