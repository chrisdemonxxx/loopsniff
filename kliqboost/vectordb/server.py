#!/usr/bin/env python3
"""Start ChromaDB server for Render deployment.
Downloads seed data on first boot from CHROMA_SEED_URL."""
import os
import subprocess
import sys

# Use persistent disk if available, otherwise local dir
data_dir = os.environ.get("CHROMA_DATA_DIR", "/data/chroma")
os.makedirs(data_dir, exist_ok=True)

# Seed data on first boot (persistent disk keeps it across deploys)
marker = os.path.join(data_dir, ".seeded")
if not os.path.exists(marker):
    seed_url = os.environ.get(
        "CHROMA_SEED_URL",
        "https://temp.sh/GZAOZ/chroma_data.tar.gz",
    )
    print(f"📥 First boot — downloading seed data from {seed_url}", flush=True)
    try:
        subprocess.run(
            ["bash", "-c", f"curl -fSL '{seed_url}' | tar xz -C '{data_dir}'"],
            check=True,
        )
        open(marker, "w").write("ok")
        print("✅ Seed data extracted", flush=True)
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Seed download failed: {e} — starting with empty DB", flush=True)
else:
    print("✅ Data already seeded", flush=True)

port = os.environ.get("PORT", "8000")
print(f"🔄 Starting ChromaDB server on port {port}, data: {data_dir}", flush=True)

# List data dir contents for debugging
for f in os.listdir(data_dir):
    print(f"  📄 {f}", flush=True)

sys.argv = [
    "chroma", "run",
    "--host", "0.0.0.0",
    "--port", port,
    "--path", data_dir,
]

from chromadb.cli.cli import app
app()
