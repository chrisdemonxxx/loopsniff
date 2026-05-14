"""Baseten Training config: upload merged Qwen3-Next-80B from baseten checkpoint storage to HF.

Pulls the `merged` checkpoint emitted by job qj7dg2q (148 GiB BF16) via
LoadCheckpointConfig, then uploads it to a private HF repo using hf_transfer.

Compute: 1xH100 — overkill for I/O but guarantees enough disk + network for 148 GiB.
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
from truss_train.definitions import _BasetenNamedCheckpoint, SecretReference
from truss.base.truss_config import AcceleratorSpec

BASE_IMAGE = "pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime"

MERGED_SOURCE_JOB = "qj7dg2q"
MERGED_SOURCE_CHECKPOINT = "merged"
HF_REPO_ID = "chrisdemonxxx/qwen3-next-80b-abliterated-cybergym-sft-r1-merged"

training_runtime = Runtime(
    start_commands=["chmod +x ./run.sh && ./run.sh"],
    cache_config=CacheConfig(enabled=True),
    checkpointing_config=CheckpointingConfig(enabled=False),
    load_checkpoint_config=LoadCheckpointConfig(
        enabled=True,
        checkpoints=[
            _BasetenNamedCheckpoint(
                job_id=MERGED_SOURCE_JOB,
                checkpoint_name=MERGED_SOURCE_CHECKPOINT,
            ),
        ],
        download_folder="/tmp/loaded_checkpoints",
    ),
    environment_variables={
        "HF_REPO_ID": HF_REPO_ID,
        "HF_TOKEN": SecretReference(name="hf_access_token"),
    },
)

training_compute = Compute(
    accelerator=AcceleratorSpec(accelerator="H100", count=1),
)

training_job = TrainingJob(
    image=Image(base_image=BASE_IMAGE),
    compute=training_compute,
    runtime=training_runtime,
)

training_project = TrainingProject(
    name="qwen3-80b-cybergym-sft-merge-upload",
    job=training_job,
)
