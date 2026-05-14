"""Baseten Training config: merge SFT LoRA (wldrkeq/checkpoint-210) into Qwen3-Next-80B base.

Output: a Baseten training-job checkpoint named 'merged' containing the full
~160 GB BF16 merged model, downloadable via `truss train download` or
referenceable from a serving truss config via presigned URLs.

Compute: 4xH100 (320 GiB VRAM) — base BF16 ~160 GiB + LoRA buffers + headroom.
"""
from truss_train import (
    CacheConfig,
    CheckpointingConfig,
    Compute,
    Image,
    LoadCheckpointConfig,
    Runtime,
    TrainingJob,
    TrainingProject,
)
from truss_train.definitions import _BasetenNamedCheckpoint
from truss.base.truss_config import AcceleratorSpec

BASE_IMAGE = "pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime"

LORA_SOURCE_JOB = "wldrkeq"
LORA_SOURCE_CHECKPOINT = "checkpoint-210"

training_runtime = Runtime(
    start_commands=["chmod +x ./run.sh && ./run.sh"],
    cache_config=CacheConfig(enabled=True),
    checkpointing_config=CheckpointingConfig(enabled=True),
    load_checkpoint_config=LoadCheckpointConfig(
        enabled=True,
        checkpoints=[
            _BasetenNamedCheckpoint(
                job_id=LORA_SOURCE_JOB,
                checkpoint_name=LORA_SOURCE_CHECKPOINT,
            ),
        ],
        download_folder="/tmp/loaded_checkpoints",
    ),
)

training_compute = Compute(
    accelerator=AcceleratorSpec(accelerator="H100", count=4),
)

training_job = TrainingJob(
    image=Image(base_image=BASE_IMAGE),
    compute=training_compute,
    runtime=training_runtime,
)

training_project = TrainingProject(
    name="qwen3-80b-cybergym-sft-merge",
    job=training_job,
)
