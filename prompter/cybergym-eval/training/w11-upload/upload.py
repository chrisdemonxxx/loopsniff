"""Upload merged Qwen3-Next-80B BF16 weights from Baseten checkpoint storage to HF private repo.

Pulls 148 GiB from job qj7dg2q's `merged` checkpoint via LoadCheckpointConfig,
then uploads to chrisdemonxxx/qwen3-next-80b-abliterated-cybergym-sft-r1-merged.
"""
import os
import sys
import time
from pathlib import Path

from huggingface_hub import HfApi, create_repo

LORA_DOWNLOAD_ROOT = Path(os.getenv("LORA_DOWNLOAD_ROOT", "/tmp/loaded_checkpoints"))
HF_REPO_ID = os.environ["HF_REPO_ID"]
HF_TOKEN = os.environ["HF_TOKEN"]


def find_merged_dir(root: Path) -> Path:
    candidates = list(root.rglob("model.safetensors.index.json"))
    if not candidates:
        raise FileNotFoundError(f"No model.safetensors.index.json under {root}")
    return candidates[0].parent


def main() -> None:
    print(f"[upload] Target HF repo: {HF_REPO_ID}")
    print(f"[upload] Source root:    {LORA_DOWNLOAD_ROOT}")

    merged_dir = find_merged_dir(LORA_DOWNLOAD_ROOT)
    files = sorted(p for p in merged_dir.iterdir() if p.is_file())
    total_gib = sum(p.stat().st_size for p in files) / 1024**3
    print(f"[upload] Resolved merged dir: {merged_dir}")
    print(f"[upload] {len(files)} files, {total_gib:.2f} GiB")
    for p in files:
        print(f"  {p.name:50s}  {p.stat().st_size / 1024**3:6.2f} GiB")

    api = HfApi(token=HF_TOKEN)
    print(f"[upload] Creating repo {HF_REPO_ID} (private=True, exist_ok=True)...")
    create_repo(HF_REPO_ID, token=HF_TOKEN, private=True, exist_ok=True, repo_type="model")

    print(f"[upload] Starting upload_folder ({total_gib:.1f} GiB)...")
    t0 = time.time()
    api.upload_folder(
        folder_path=str(merged_dir),
        repo_id=HF_REPO_ID,
        repo_type="model",
        commit_message="Initial upload: Qwen3-Next-80B abliterated + CyberGym SFT (LoRA merged from job wldrkeq/checkpoint-210)",
        ignore_patterns=["MERGE_MANIFEST.json.lock", "*.tmp"],
    )
    elapsed = time.time() - t0
    print(f"[upload] DONE in {elapsed/60:.1f} min ({total_gib / (elapsed/60):.1f} GiB/min)")
    print(f"[upload] Repo URL: https://huggingface.co/{HF_REPO_ID}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
