#!/bin/bash
set -e

DATA_DIR="/data/chroma"
mkdir -p "$DATA_DIR"

echo "🔄 Starting ChromaDB server on port ${PORT:-8000}..."
echo "   Data path: $DATA_DIR"

exec chroma run \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --path "$DATA_DIR" \
  --log-path /dev/stdout
