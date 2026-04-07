#!/bin/bash
set -e

DATA_DIR="/data/chroma"
mkdir -p "$DATA_DIR"

echo "🔄 Starting ChromaDB server..."
exec python vectordb/server.py
