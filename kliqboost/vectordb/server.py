#!/usr/bin/env python3
"""Start ChromaDB server for Render deployment."""
import os
import sys

# Ensure data directory exists
data_dir = "/data/chroma"
os.makedirs(data_dir, exist_ok=True)

port = os.environ.get("PORT", "8000")
print(f"🔄 Starting ChromaDB server on port {port}, data: {data_dir}")

# Build CLI args as if called from command line
sys.argv = [
    "chroma", "run",
    "--host", "0.0.0.0",
    "--port", port,
    "--path", data_dir,
]

from chromadb.cli.cli import app
app()
