#!/bin/bash
# Pentest mission initialization script
# This script is idempotent - safe to run multiple times

set -e

echo "=== Dutch Point Pentest Mission Initialization ==="

# Create required directories
mkdir -p /home/cjs/dutchpoint.org/recon
mkdir -p /home/cjs/dutchpoint.org/vulnerabilities
mkdir -p /home/cjs/dutchpoint.org/exploits
mkdir -p /home/cjs/dutchpoint.org/post-exploit
mkdir -p /home/cjs/dutchpoint.org/reports

# Check for required tools (optional - document if missing)
echo "Checking for pentest tools..."

command -v subfinder >/dev/null 2>&1 || echo "WARNING: subfinder not found"
command -v wpscan >/dev/null 2>&1 || echo "WARNING: wpscan not found"
command -v nuclei >/dev/null 2>&1 || echo "WARNING: nuclei not found"
command -v nmap >/dev/null 2>&1 || echo "WARNING: nmap not found"
command -v sqlmap >/dev/null 2>&1 || echo "WARNING: sqlmap not found"

# Create wordlist symlinks if available
if [ -d /usr/share/wordlists ]; then
    ln -sf /usr/share/wordlists /home/cjs/dutchpoint.org/wordlists 2>/dev/null || true
fi

echo "=== Initialization Complete ==="
