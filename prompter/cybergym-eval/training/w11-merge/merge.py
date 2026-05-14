"""Merge SFT LoRA adapter (job wldrkeq, checkpoint-210) into Huihui-Qwen3-Next-80B base.

Baseten's LoadCheckpointConfig auto-downloads the LoRA adapter to /tmp/loaded_checkpoints
before this script runs. We load the BF16 base model sharded across 4xH100 with
device_map="auto", attach the adapter via PEFT, call merge_and_unload(), then save
the merged model into $BT_CHECKPOINT_DIR/merged/ as sharded safetensors.

Output of the job: a single Baseten checkpoint named "merged" containing the full
~160 GB BF16 model, downloadable via `truss train download --job-id <new>` and
referenced from the serving truss config via presigned URLs.
"""
import gc
import json
import os
import shutil
import sys
import time
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL_ID = "huihui-ai/Huihui-Qwen3-Next-80B-A3B-Instruct-abliterated"
LORA_DOWNLOAD_ROOT = Path(os.getenv("LORA_DOWNLOAD_ROOT", "/tmp/loaded_checkpoints"))
CHECKPOINT_DIR = Path(os.getenv("BT_CHECKPOINT_DIR", "./checkpoints"))
OUTPUT_DIR = CHECKPOINT_DIR / "merged"


def find_adapter_dir(root: Path) -> Path:
    """Locate the directory containing adapter_config.json under root."""
    if not root.exists():
        raise FileNotFoundError(f"LoRA download root missing: {root}")
    candidates = list(root.rglob("adapter_config.json"))
    if not candidates:
        listing = "\n".join(str(p) for p in root.rglob("*") if p.is_file())
        raise FileNotFoundError(
            f"No adapter_config.json under {root}. Files present:\n{listing}"
        )
    if len(candidates) > 1:
        print(f"[merge] Multiple adapter dirs found, using first: {candidates[0]}")
    return candidates[0].parent


def main() -> None:
    print("=" * 78)
    print("LoRA -> Base merge for Qwen3-Next-80B SFT")
    print("=" * 78)
    print(f"[merge] Base model:        {BASE_MODEL_ID}")
    print(f"[merge] LoRA root:         {LORA_DOWNLOAD_ROOT}")
    print(f"[merge] Checkpoint dir:    {CHECKPOINT_DIR}")
    print(f"[merge] Output dir:        {OUTPUT_DIR}")
    print(f"[merge] CUDA devices:      {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        print(f"  cuda:{i}  {props.name}  {props.total_memory / 1024**3:.1f} GiB")

    adapter_dir = find_adapter_dir(LORA_DOWNLOAD_ROOT)
    print(f"[merge] Resolved adapter dir: {adapter_dir}")
    adapter_files = sorted(p.name for p in adapter_dir.iterdir())
    print(f"[merge] Adapter files: {adapter_files}")
    with (adapter_dir / "adapter_config.json").open() as f:
        adapter_cfg = json.load(f)
    print(f"[merge] adapter_config: r={adapter_cfg.get('r')} "
          f"alpha={adapter_cfg.get('lora_alpha')} "
          f"target_modules={adapter_cfg.get('target_modules')}")

    if OUTPUT_DIR.exists():
        print(f"[merge] Removing stale output dir {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[merge] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID, trust_remote_code=True)

    print("[merge] Loading base model in BF16, device_map='auto' (this takes ~10 min)...")
    t0 = time.time()
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    print(f"[merge] Base loaded in {time.time() - t0:.1f}s")
    print(f"[merge] Base param count: {sum(p.numel() for p in base.parameters()):,}")

    print("[merge] Attaching LoRA adapter via PEFT...")
    t0 = time.time()
    peft_model = PeftModel.from_pretrained(
        base,
        str(adapter_dir),
        torch_dtype=torch.bfloat16,
        is_trainable=False,
    )
    print(f"[merge] LoRA attached in {time.time() - t0:.1f}s")

    print("[merge] Calling merge_and_unload()...")
    t0 = time.time()
    merged = peft_model.merge_and_unload(progressbar=True, safe_merge=True)
    print(f"[merge] Merge complete in {time.time() - t0:.1f}s")

    del peft_model
    gc.collect()
    torch.cuda.empty_cache()

    print(f"[merge] Saving merged model to {OUTPUT_DIR} (sharded, max_shard=10GB)...")
    t0 = time.time()
    merged.save_pretrained(
        str(OUTPUT_DIR),
        safe_serialization=True,
        max_shard_size="10GB",
    )
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    # Copy chat template if present in adapter dir
    chat_template_src = adapter_dir / "chat_template.jinja"
    if chat_template_src.exists():
        shutil.copy(chat_template_src, OUTPUT_DIR / "chat_template.jinja")
    print(f"[merge] Saved in {time.time() - t0:.1f}s")

    saved_files = sorted(OUTPUT_DIR.iterdir())
    total_bytes = sum(p.stat().st_size for p in saved_files if p.is_file())
    print(f"[merge] Output size: {total_bytes / 1024**3:.2f} GiB across {len(saved_files)} files")
    for p in saved_files:
        size_gib = p.stat().st_size / 1024**3 if p.is_file() else 0
        print(f"  {p.name:60s}  {size_gib:6.2f} GiB")

    manifest = {
        "base_model": BASE_MODEL_ID,
        "lora_source_job": "wldrkeq",
        "lora_source_checkpoint": "checkpoint-210",
        "lora_config": adapter_cfg,
        "merged_size_gib": round(total_bytes / 1024**3, 2),
        "merged_file_count": len([p for p in saved_files if p.is_file()]),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUTPUT_DIR / "MERGE_MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"[merge] Wrote MERGE_MANIFEST.json")
    print("[merge] DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
