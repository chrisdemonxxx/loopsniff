---
name: recon-worker
description: Penetration testing reconnaissance specialist - passive and active intelligence gathering
---

# Reconnaissance Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use this worker for all reconnaissance and intelligence gathering features:
- Passive OSINT gathering (subdomain enumeration, DNS records, historical data)
- Technology stack fingerprinting (WordPress, plugins, server software)
- Network infrastructure mapping (port scanning, service detection)
- Content and endpoint discovery (directory brute-forcing, parameter mining)

## Work Procedure

**CRITICAL: Distinguish passive vs active reconnaissance**

### For Passive Reconnaissance:
1. **Subdomain Enumeration**
   - Run `subfinder -d dutchpoint.org -all -silent` (uses 70+ sources)
   - Cross-reference with crt.sh: `curl -s "https://crt.sh/?q=%.dutchpoint.org&output=json"`
   - Use Amass if passive sources insufficient: `amass enum -passive -d dutchpoint.org`

2. **DNS Infrastructure Mapping**
   - Query DNS records: `dig dutchpoint.org ANY +noall +answer`
   - Check SPF/DMARC/DKIM: `dig dutchpoint.org TXT +noall +answer`
   - Map MX records for email infrastructure

3. **Technology Fingerprinting**
   - Use `whatweb https://dutchpoint.org` for tech stack detection
   - Analyze HTTP headers: `curl -I https://dutchpoint.org`
   - For WordPress: `wpscan --url https://dutchpoint.org --enumerate vp,vt,u` (passive mode only, no aggressive scanning)

4. **Historical Data Collection**
   - Query Wayback Machine: `curl -s "http://web.archive.org/cdx/search/cdx?url=*.dutchpoint.org/*&output=json&collapse=urlkey"`
   - Use Gau for URL discovery: `gau dutchpoint.org`
   - Check Waybackurls: `waybackurls dutchpoint.org`

5. **Document ALL Findings**
   - Create comprehensive report with categorized findings
   - Include tool outputs as evidence
   - Note any high-value targets (admin panels, APIs, authentication endpoints)

### For Active Reconnaissance:
1. **Port Scanning** (only after passive recon complete)
   - Start with Nmap: `nmap -sV -sC -oN nmap_scan.txt <target>`
   - For speed: `rustscan -a <target> -- -sV -sC`
   - Document all open ports and services

2. **Directory/Endpoint Discovery**
   - Use Feroxbuster: `feroxbuster -u https://dutchpoint.org -w /usr/share/wordlists/dirb/common.txt`
   - Use Gobuster: `gobuster dir -u https://dutchpoint.org -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt`
   - Document discovered paths, especially admin panels and APIs

3. **Service Enumeration**
   - For HTTP services: `nikto -h https://<target>`
   - For WordPress: `wpscan --url https://<target> --enumerate ap,at,u --plugins-detection aggressive`
   - For SMB/RPC if discovered: `enum4linux <target>` or `rpcclient -U "" <target>`

4. **Manual Verification**
   - Visit discovered admin panels (screenshot login pages)
   - Test discovered APIs with curl (document responses)
   - Verify technology detection manually (check page source, headers)

## Example Handoff

```json
{
  "salientSummary": "Discovered 31 subdomains via Subfinder, mapped DNS infrastructure (SPF/DKIM/DMARC configured but DMARC p=none), identified WordPress 6.8.3 behind Cloudflare WAF, found 47 endpoints via directory brute-forcing including /wp-admin, /api/v1, /tomcat1/. Nmap scan of primary IP (192.237.146.112) revealed open ports 22, 80, 443, 8080 (Tomcat), 3306 (MySQL, filtered). All findings documented in /home/cjs/dutchpoint.org/RECON_REPORT.md.",
  "whatWasImplemented": "Executed comprehensive reconnaissance: subdomain enumeration (Subfinder, crt.sh), DNS mapping (dig), technology fingerprinting (whatweb, WPScan passive), port scanning (Nmap on 5 key subdomains), content discovery (Feroxbuster with 3 wordlists), and manual verification of high-value endpoints. Created detailed report with 31 subdomains, 47 endpoints, technology stack breakdown, and network topology map.",
  "whatWasLeftUndone": "Amass timed out during execution - results incomplete. Did not scan all 31 subdomains with Nmap (scanned top 5 by priority). API endpoint discovery limited to surface-level - deeper parameter mining pending.",
  "verification": {
    "commandsRun": [
      {
        "command": "subfinder -d dutchpoint.org -all -silent | tee /tmp/subfinder.txt",
        "exitCode": 0,
        "observation": "Discovered 31 unique subdomains in 30 seconds"
      },
      {
        "command": "nmap -sV -sC -oN /tmp/nmap_primary.txt 192.237.146.112",
        "exitCode": 0,
        "observation": "Found 5 open ports: 22 (SSH), 80 (HTTP), 443 (HTTPS), 8080 (Tomcat), 3306 (MySQL filtered)"
      },
      {
        "command": "feroxbuster -u https://dutchpoint.org -w /usr/share/wordlists/dirb/common.txt -o /tmp/ferox.txt",
        "exitCode": 0,
        "observation": "Discovered 47 endpoints including /wp-admin, /api/v1, /xmlrpc.php"
      },
      {
        "command": "wpscan --url https://dutchpoint.org --enumerate vp,vt,u --no-update",
        "exitCode": 0,
        "observation": "WordPress 6.8.3 detected, 3 vulnerable plugins found, theme: astra-child"
      }
    ],
    "interactiveChecks": [
      {
        "action": "Visited https://adfs.dutchpoint.org/adfs/ls/ in browser",
        "observed": "ADFS authentication page loads successfully with Microsoft branding. No certificate warnings. Cloudflare protection active."
      },
      {
        "action": "Tested https://tomcat1.dutchpoint.org:8080/manager/html",
        "observed": "Tomcat manager login page returned 401 Unauthorized. Requires authentication. Server: Apache-Coyote/1.1"
      },
      {
        "action": "Curl GET https://dutchpoint.org/api/v1/status",
        "observed": "Returned 200 OK with JSON: {\"status\":\"healthy\",\"version\":\"1.2.3\"}. No authentication required."
      }
    ]
  },
  "tests": {
    "added": []
  },
  "discoveredIssues": [
    {
      "severity": "MEDIUM",
      "description": "DMARC policy set to p=none (monitoring only) - does not prevent email spoofing",
      "suggestedFix": "Update DMARC policy to p=quarantine or p=reject after monitoring period"
    },
    {
      "severity": "LOW",
      "description": "Tomcat manager exposed on port 8080 - potential brute force target",
      "suggestedFix": "Restrict access to manager via IP whitelist or move behind VPN"
    },
    {
      "severity": "INFO",
      "description": "API endpoint /api/v1/status exposed without authentication",
      "suggestedFix": "Implement rate limiting if not already present, consider authentication for status endpoint"
    }
  ]
}
```

## When to Return to Orchestrator

- Reconnaissance reveals scope creep (e.g., 100+ subdomains, need to prioritize)
- Active scanning triggers WAF/rate limiting (need to adjust approach)
- Discovered services outside agreed scope (need clarification)
- Tool failures prevent completion (e.g., Amass timeout, network errors)
- High-severity vulnerability discovered during recon (need immediate decision on exploitation)
