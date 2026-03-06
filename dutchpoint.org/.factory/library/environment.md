# Environment

Pentest mission environment configuration and external dependencies.

**What belongs here:** Required environment variables, external API keys, pentest tool configurations, and setup notes.  
**What does NOT belong here:** Service ports/commands (those are in `.factory/services.yaml`).

---

## External API Keys

**WPScan API Token:**
```bash
export WPSCAN_API_TOKEN="your_api_token_here"
```
Required for WPScan vulnerability database lookups. Get free token at: https://wpscan.com/api

**BrightData Proxy:**
```bash
export BRIGHTDATA_PROXY="http://customer-xxxxx:xxxxx@brd.superproxy.io:22225"
```
Optional: For geo-specific testing or WAF circumvention.

---

## Required Pentest Tools

**Installation (Kali Linux):**
```bash
apt-get update
apt-get install -y \
  subfinder \
  amass \
  wpscan \
  nuclei \
  nmap \
  sqlmap \
  feroxbuster \
  gobuster \
  hydra \
  hashcat \
  testssl.sh \
  nikto \
  enum4linux \
  searchsploit
```

**Installation (Ubuntu/Debian):**
```bash
# Subfinder
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest

# Nuclei
go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest

# Feroxbuster
wget https://github.com/epi052/feroxbuster/releases/latest/download/feroxbuster_x86_64-linux-musl.tar.gz
tar -xvf feroxbuster_x86_64-linux-musl.tar.gz
mv feroxbuster /usr/local/bin/
```

---

## Wordlists

**Default Locations:**
```
/usr/share/wordlists/rockyou.txt      - Password wordlist
/usr/share/wordlists/dirb/common.txt  - Directory brute-force
/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt
/usr/share/wordlists/seclists/Discovery/Web-Content/raft-medium-*.txt
```

**Custom Wordlists:**
```
/home/cjs/dutchpoint.org/wordlists/
├── users.txt         - Usernames from recon
├── passwords.txt     - Common passwords (top 1000)
├── endpoints.txt     - API endpoints to test
└── payloads.txt      - XSS/SQLi payloads
```

---

## Tool Configuration

**Nmap Timing:**
- T2 (polite): `--max-rate 10` - Use for all scans to avoid WAF blocking
- T3 (normal): Default - Only if T2 too slow

**Nuclei Rate Limiting:**
```yaml
# ~/.config/nuclei/config.yaml
rate-limit: 10
timeout: 10
retries: 2
```

**SQLMap Tamper Scripts:**
```bash
--tamper=space2comment,between,equaltolike
```
Use tamper scripts to bypass WAF when detected.

---

## Logging

**Log Directory:**
```bash
mkdir -p /home/cjs/dutchpoint.org/logs
```

**Log Format:**
```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] <action>" >> logs/pentest.log
```

**Mandatory Logging:**
- All commands with timestamps
- All vulnerabilities discovered
- All exploitation attempts
- All service interactions (start/stop/cleanup)

---

## Cleanup Requirements

**End of Session:**
```bash
# Remove test files from target
curl -X DELETE "https://dutchpoint.org/wp-content/uploads/2024/12/test_shell.php"

# Remove local test artifacts
rm -rf /tmp/pentest_*.tmp

# Clear browser cache (if browser automation used)
```

**Verify No Persistence:**
- Check for any uploaded test files
- Verify database has no test entries
- Confirm no modified configurations
- Ensure no created user accounts remain

---

## Emergency Contacts

**If Service Degradation Detected:**
1. STOP all active scanning immediately
2. Return to orchestrator
3. Document what was happening when issue occurred
4. Wait for authorization to resume

**If Security Team Contacts You:**
1. STOP all testing
2. Return to orchestrator immediately
3. Provide authorization documentation if requested
4. Do not continue without explicit authorization

---

## Platform Notes

**Operating System:** Linux 6.17.0-14-generic  
**Python Version:** 3.12.3  
**Git:** 2.43.0  
**Ripgrep:** 14.1.0  

**Network:** Standard outbound connectivity (no proxy required unless specified)

---
