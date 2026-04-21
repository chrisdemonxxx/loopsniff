#!/bin/bash
set -e

PHONE_RAW="${TG_PHONE:-}"
PHONE_NORM="${PHONE_RAW#+}"
SESSION_DIR="$(dirname "$0")/sessions"
SESSION_PATH="${SESSION_DIR}/tg_${PHONE_NORM}.session"

# Validate critical env for deterministic startup
if [ -z "$PHONE_RAW" ]; then
  echo "❌ TG_PHONE is required"
  exit 1
fi

# Decode Telethon session from base64 env var
if [ -n "$TG_SESSION_B64" ]; then
    mkdir -p "$SESSION_DIR"
    echo "$TG_SESSION_B64" | base64 -d > "$SESSION_PATH"
    if [ ! -s "$SESSION_PATH" ]; then
      echo "❌ Decoded session file is empty: $SESSION_PATH"
      exit 1
    fi
    echo "✅ Session file decoded to $SESSION_PATH"
elif [ ! -s "$SESSION_PATH" ]; then
    echo "❌ Missing session file and TG_SESSION_B64 not set: $SESSION_PATH"
    exit 1
fi

# Telethon session schema compatibility patch:
# older sessions can have 5 columns in `sessions`; newer Telethon expects 6.
SESSION_PATH="$SESSION_PATH" python3 - <<'PY'
import sqlite3
import os
from pathlib import Path
path = Path(os.environ["SESSION_PATH"])
if not path.exists():
    raise SystemExit(0)
conn = sqlite3.connect(str(path))
try:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()]
    if "tmp_auth_key" not in cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN tmp_auth_key BLOB")
        conn.commit()
        print("✅ Patched Telethon session schema: added tmp_auth_key")
finally:
    conn.close()
PY

# Create bridge directory for deal rooms DB
mkdir -p "$(dirname "$0")/../bridge"

exec python3 "$(dirname "$0")/admin_autoresponder.py"
