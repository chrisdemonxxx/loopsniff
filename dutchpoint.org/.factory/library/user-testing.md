# User Testing Guide - Dutch Point Credit Union Pentest

## Mission Overview
This is a penetration testing mission, not a traditional application. "User testing" means validating that reconnaissance was performed correctly and that the discovered intelligence is actionable for exploitation phases.

## Testing Surface
- **Target Application**: dutchpoint.org infrastructure (external)
- **Testing Method**: Evidence validation through file verification and manual checks
- **No Internal Services**: This is testing against an external target, not running our own services

## Reconnaissance Evidence Location

### Subdomain Enumeration Evidence
- `/home/cjs/dutchpoint.org/recon/subdomains.txt` - List of discovered subdomains
- `/home/cjs/dutchpoint.org/recon/subfinder_raw.txt` - Raw subfinder output
- `/home/cjs/dutchpoint.org/recon/crt_sh_raw.json` - Certificate transparency data

### Technology Stack Evidence
- `/home/cjs/dutchpoint.org/recon/technology_stack.md` - Identified technologies per subdomain
- `/home/cjs/dutchpoint.org/recon/high_value_targets.md` - Priority targets for testing

### Network Infrastructure Evidence
- `/home/cjs/dutchpoint.org/recon/nmap_results/` - Port scan results per target
- `/home/cjs/dutchpoint.org/recon/dns_records.txt` - DNS enumeration data

### Content Discovery Evidence
- `/home/cjs/dutchpoint.org/recon/content_discovery_report.md` - Directory/endpoint findings
- `/home/cjs/dutchpoint.org/recon/endpoints_discovered.md` - Discovered endpoints
- `/home/cjs/dutchpoint.org/recon/katana_*.txt` - Web crawling results

## Validation Requirements

### VAL-RECON-001: Subdomain Enumeration
Evidence Required:
- 30+ unique subdomains in subdomains.txt
- Multiple discovery sources (passive sources)
- High-priority targets identified (admin panels, APIs)

Validation Steps:
1. Count subdomains: `wc -l /home/cjs/dutchpoint.org/recon/subdomains.txt`
2. Verify sources: Check subfinder_raw.txt and crt_sh_raw.json
3. Check for high-value: Look for admin.*, api.*, secure.* patterns

### VAL-RECON-002: Technology Stack Fingerprinting
Evidence Required:
- CMS version identification (Note: Target uses Umbraco CMS, not WordPress)
- Server software detection (Nginx/Cloudflare)
- Third-party integrations identified

Validation Steps:
1. Read technology_stack.md for actual CMS details (Umbraco, not WordPress)
2. Check that WordPress testing was attempted but correctly identified as not deployed
3. Verify detection headers via manual curl checks
4. Confirm documentation of actual technology stack

### VAL-RECON-003: Network Infrastructure Mapping
Evidence Required:
- Port scan results for key targets
- Service version detection
- Firewall/WAF identification
- OS fingerprinting where available

Validation Steps:
1. Check nmap_results/ directory for scan files
2. Verify open ports beyond standard 80/443
3. Confirm Cloudflare WAF detection
4. Check service versions

### VAL-RECON-004: Content and Endpoint Discovery
Evidence Required:
- Directory brute force results
- Admin panel discovery
- API endpoint identification
- Sensitive file detection

Validation Steps:
1. Review content_discovery_report.md
2. Check endpoints_discovered.md for admin/API paths
3. Verify accessibility of discovered endpoints
4. Check for exposed config files or backups

## Testing Tools

### Manual Verification
- `curl` - Verify endpoint accessibility, check headers
- `dig` - DNS record verification
- `nmap` - Quick port verification
- Browser inspection - Visual verification of discovered endpoints

### Evidence Collection
- Screenshots for web-based discoveries
- File verification for text-based evidence
- Manual HTTP request/response capture

## Flow Validator Guidance: Reconnaissance Evidence

### Isolation Strategy
Each flow validator gets separate assertion groups since this is evidence validation, not live application testing.

### Shared State Considerations
- All validators read from same evidence files
- No state modification occurs
- Parallel validation is safe (read-only operations)

### Constraints
- Do NOT modify existing evidence files
- Do NOT perform new reconnaissance scans
- Do NOT contact discovered services without explicit instruction
- Focus on EVIDENCE VALIDATION, not new testing
- Note: Cloudflare WAF challenges on most endpoints prevent automated access
- Note: Target uses Umbraco CMS (ASP.NET), not WordPress

### Verification Criteria
- Evidence files exist and are not empty
- Evidence content matches assertion requirements
- Evidence is timestamped and properly formatted
- Discovered information is actionable (leads to exploitation opportunities)

## Setup Requirements

### No Service Dependencies
This validation requires no running services since we're validating completed reconnaissance evidence.

### Test Data
All test data is pre-existing in the /home/cjs/dutchpoint.org/recon/ directory.

### External Dependencies
- Internet access for manual verification of discovered endpoints (optional)
- Screenshot capability for visual evidence (provided by evidence files)
