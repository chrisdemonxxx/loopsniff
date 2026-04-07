#!/bin/bash
set -e

DATA_DIR="/data/chroma"
mkdir -p "$DATA_DIR"

PORT="${PORT:-8000}"
echo "🔄 Starting ChromaDB server on port ${PORT}..."
echo "   Data path: $DATA_DIR"

exec python -m chromadb.cli.cli run \
  --host 0.0.0.0 \
  --port "$PORT" \
  --path "$DATA_DIR" \
  --log-path /dev/stdout
