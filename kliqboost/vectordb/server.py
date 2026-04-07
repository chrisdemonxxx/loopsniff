#!/usr/bin/env python3
"""Start ChromaDB server for Render deployment.
Downloads seed data from GitHub release on first boot."""
import os
import subprocess
import sys

data_dir = "/data/chroma"
os.makedirs(data_dir, exist_ok=True)

# Seed data on first boot (persistent disk keeps it across deploys)
marker = os.path.join(data_dir, ".seeded")
if not os.path.exists(marker):
    url = os.environ.get(
        "CHROMA_SEED_URL",
        "https://github.com/chrisdemonxxx/loopsniff/releases/download/rag-data-v1/chroma_data.tar.gz",
    )
    print(f"📥 First boot — downloading seed data from {url}")
    subprocess.run(
        f"curl -fSL '{url}' | tar xz -C '{data_dir}'",
        shell=True, check=True,
    )
    open(marker, "w").write("ok")
    print("✅ Seed data extracted")
else:
    print("✅ Data already seeded")

port = os.environ.get("PORT", "8000")
print(f"🔄 Starting ChromaDB server on port {port}, data: {data_dir}")

sys.argv = [
    "chroma", "run",
    "--host", "0.0.0.0",
    "--port", port,
    "--path", data_dir,
]

from chromadb.cli.cli import app
app()
