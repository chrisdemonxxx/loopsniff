#!/bin/bash
# Kliqboost Deployment Script — for Oracle Cloud Free Tier (ARM Ubuntu)
# Run this on the VM after cloning the project

set -e

echo "══════════════════════════════════════════"
echo "  Kliqboost Deployment — Oracle Cloud"
echo "══════════════════════════════════════════"

# ── 1. System packages ──────────────────────────────────────────────────
echo "📦 Installing system packages..."
sudo apt update -qq
sudo apt install -y -qq python3.12 python3.12-venv python3-pip git curl

# ── 2. Project setup ────────────────────────────────────────────────────
PROJECT_DIR="$HOME/kliqboost"
cd "$PROJECT_DIR"

echo "🐍 Creating Python virtual environment..."
python3.12 -m venv venv
source venv/bin/activate

echo "📦 Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# ── 3. Systemd services ────────────────────────────────────────────────
echo "⚙️ Installing systemd services..."

mkdir -p ~/.config/systemd/user

# AI Userbot service
cat > ~/.config/systemd/user/kliqboost-userbot.service << EOF
[Unit]
Description=Kliqboost AI Userbot (Telethon)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR/userbot
ExecStart=$PROJECT_DIR/venv/bin/python admin_autoresponder.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

# Manager Bot service
cat > ~/.config/systemd/user/kliqboost-bot.service << EOF
[Unit]
Description=Kliqboost Manager Bot (aiogram)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR/bot
ExecStart=$PROJECT_DIR/venv/bin/python bot.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

# Enable linger (keep services running after SSH logout)
loginctl enable-linger "$USER"

# Reload systemd
systemctl --user daemon-reload

echo "✅ Services installed!"
echo ""
echo "══════════════════════════════════════════"
echo "  Deployment complete!"
echo "══════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Authenticate userbot:"
echo "     cd $PROJECT_DIR && source venv/bin/activate"
echo "     python auto_setup.py --auth"
echo ""
echo "  2. Run setup (creates channels + bot):"
echo "     python auto_setup.py --setup"
echo ""
echo "  3. Start services:"
echo "     systemctl --user start kliqboost-userbot"
echo "     systemctl --user start kliqboost-bot"
echo "     systemctl --user enable kliqboost-userbot kliqboost-bot"
echo ""
echo "  4. Check status:"
echo "     systemctl --user status kliqboost-userbot kliqboost-bot"
echo ""
echo "  5. View logs:"
echo "     journalctl --user -u kliqboost-userbot -f"
echo "     journalctl --user -u kliqboost-bot -f"
