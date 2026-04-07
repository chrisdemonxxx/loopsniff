#!/bin/bash
set -e

# Decode Telethon session from base64 env var
if [ -n "$TG_SESSION_B64" ]; then
    mkdir -p "$(dirname "$0")/sessions"
    echo "$TG_SESSION_B64" | base64 -d > "$(dirname "$0")/sessions/tg_19414034041.session"
    echo "✅ Session file decoded"
fi

# Create bridge directory for deal rooms DB
mkdir -p "$(dirname "$0")/../bridge"

exec python3 "$(dirname "$0")/admin_autoresponder.py"
