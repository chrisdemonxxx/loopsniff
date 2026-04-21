# Oracle Cloud Free Tier — Setup Guide

## Step 1: Create Oracle Cloud Account

1. Go to https://cloud.oracle.com
2. Click "Sign Up" → "Start for Free"
3. Enter email, name, country
4. **Credit card required** (verification only — you will NOT be charged)
5. Select home region: **US East (Ashburn)** recommended
6. Complete signup

## Step 2: Create ARM VM (Always Free)

1. Go to Compute → Instances → Create Instance
2. Settings:
   - **Name**: kliqboost-server
   - **Image**: Ubuntu 22.04 (or 24.04) — **Ampere (ARM)**
   - **Shape**: VM.Standard.A1.Flex
   - **OCPU**: 2 (out of 4 free)
   - **RAM**: 12 GB (out of 24 free)
   - **Boot volume**: 50 GB (out of 200 free)
3. **SSH key**: Upload your public key or generate new
   - On your local machine: `ssh-keygen -t ed25519 -f ~/.ssh/oracle`
   - Upload `~/.ssh/oracle.pub`
4. Click **Create**
5. Wait 2-5 minutes for provisioning

> ⚠️ If you see "Out of host capacity" — try a different Availability Domain
> or wait a few hours. This is common in popular regions.

## Step 3: SSH into VM

```bash
ssh -i ~/.ssh/oracle ubuntu@<VM_PUBLIC_IP>
```

## Step 4: Upload Project

Option A: Git clone (if you push to private repo)
```bash
git clone https://github.com/YOUR_USER/kliqboost.git
```

Option B: SCP from local machine
```bash
# From your local machine:
scp -i ~/.ssh/oracle -r /home/cjs/kliqboost ubuntu@<VM_IP>:~/
```

## Step 5: Run Deployment

```bash
cd ~/kliqboost
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

## Step 6: Authenticate & Setup

```bash
cd ~/kliqboost
source venv/bin/activate

# Auth (paste OTP when prompted)
python auto_setup.py --auth

# Full setup (creates channels, bot, content)
python auto_setup.py --setup
```

## Step 7: Start Services

```bash
# Start both bots
systemctl --user start kliqboost-userbot
systemctl --user start kliqboost-bot

# Enable auto-start on boot
systemctl --user enable kliqboost-userbot kliqboost-bot

# Verify running
systemctl --user status kliqboost-userbot kliqboost-bot
```

## Step 8: Monitor

```bash
# Live logs — AI userbot
journalctl --user -u kliqboost-userbot -f

# Live logs — Manager bot
journalctl --user -u kliqboost-bot -f

# Check both status
systemctl --user status kliqboost-userbot kliqboost-bot
```

## Maintenance

```bash
# Restart a service
systemctl --user restart kliqboost-userbot

# Stop a service
systemctl --user stop kliqboost-bot

# Update code
cd ~/kliqboost && git pull  # if using git
systemctl --user restart kliqboost-userbot kliqboost-bot
```

## Security: Firewall

Oracle Cloud has a built-in firewall (Security Lists). By default:
- SSH (port 22) is open
- Everything else is blocked
- You don't need to expose any ports for TG bots (they connect outbound)
