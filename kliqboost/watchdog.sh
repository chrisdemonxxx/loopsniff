#!/bin/bash
# Kliqboost Watchdog — keeps bot + userbot alive via PID files
# Checks every 60 seconds, auto-restarts if down

LOG="/tmp/kliqboost_watchdog.log"
BOT_PID_FILE="/tmp/kliqboost_bot.pid"
USERBOT_PID_FILE="/tmp/kliqboost_userbot.pid"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"
}

is_running() {
    local pidfile="$1"
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

start_bot() {
    log "🔄 Starting @kliqboost_bot..."
    cd /home/cjs/kliqboost/bot
    nohup python3 bot.py >> /tmp/bot.log 2>&1 &
    echo $! > "$BOT_PID_FILE"
    log "✅ Bot started (PID: $!)"
}

start_userbot() {
    log "🔄 Starting @georgekatis userbot..."
    cd /home/cjs/kliqboost/userbot
    nohup python3 admin_autoresponder.py >> /tmp/userbot.log 2>&1 &
    echo $! > "$USERBOT_PID_FILE"
    log "✅ Userbot started (PID: $!)"
}

log "🚀 Watchdog started"

# Initial start
start_bot
sleep 3
start_userbot
sleep 5

while true; do
    if ! is_running "$BOT_PID_FILE"; then
        log "❌ Bot is DOWN"
        start_bot
        sleep 5
    fi

    if ! is_running "$USERBOT_PID_FILE"; then
        log "❌ Userbot is DOWN"
        start_userbot
        sleep 5
    fi

    sleep 60
done
