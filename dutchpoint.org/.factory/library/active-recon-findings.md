# Active Reconnaissance Findings - Port Scanning

**Generated:** 2026-03-06
**Feature:** active-recon-port-scanning
**Worker Session:** cd587149-536d-44e5-b018-823482bb89b0

## Key Findings for Future Workers

### Critical Infrastructure

1. **VPN Endpoint (Cisco ASA)**
   - IP: 160.72.101.178
   - Port: 443/tcp (SSL/HTTP)
   - Service: Cisco ASA SSL VPN
   - Certificate: vpn.dutchpoint.org (Thawte TLS RSA CA G1)
   - **High-value target for credential testing**

2. **ADFS Authentication**
   - IP: 192.237.146.112
   - Fronted by F5 BIG-IP load balancer
   - Redirects to: https://www.dutchpoint.org/adfs/ls/
   - Certificate: www.dutchpoint.org (Sectigo RSA Domain Validation)
   - SANs: admin.dutchpoint.org, web12, web13
   - **High-value target for password spray (requires WAF bypass)**

3. **FICO Payment Processing (AWS)**
   - IPs: 34.196.154.214, 34.237.152.170
   - Port: 443/tcp (HTTPS)
   - Certificate: *.ficoccs-prod.net (Amazon RSA 2048 M02)
   - Backend: AWS ELB (awselb/2.0)
   - **Payment card data infrastructure**

### WAF/Firewall Status

| Host | Protection | Bypass Notes |
|------|------------|--------------|
| dutchpoint.org | Cloudflare (cf-mitigated: challenge) | Origin IP exposure possible |
| admin.dutchpoint.org | Cloudflare (cf-mitigated: challenge) | Requires browser with JS |
| secure.dutchpoint.org | Cloudflare | Returns 404, needs Host header |
| vpn.dutchpoint.org | None (direct) | **Accessible for testing** |
| adfs.dutchpoint.org | F5 BIG-IP | Redirects to main site |
| branch-portal.dutchpoint.org | Cloudflare (cf-mitigated: challenge) | Clutch Partners platform |

### Services Not Externally Accessible

| Host | Status | Notes |
|------|--------|-------|
| remote.dutchpoint.org | All ports filtered | Requires VPN or allowlist |
| mail.dutchpoint.org | All ports filtered | Microsoft 365 handles email |
| drvpn.dutchpoint.org | All ports filtered | DR VPN endpoint |
| tomcat1.dutchpoint.org:8080 | Not accessible | F5 BIG-IP redirecting |

### Scanned Ports

Open ports detected (externally accessible):
- 80/tcp - HTTP (Cloudflare/F5)
- 443/tcp - HTTPS (all hosts)
- 8080/tcp - HTTP-Alt (Cloudflare)
- 8443/tcp - HTTPS-Alt (Cloudflare)

Filtered/blocked ports:
- 22/tcp (SSH) - Filtered
- 3306/tcp (MySQL) - Filtered
- 1433/tcp (MSSQL) - Filtered
- 3389/tcp (RDP) - Filtered
- 5432/tcp (PostgreSQL) - Filtered

### Recommendations for Next Workers

1. **VPN Testing (exploitation-worker)**: Target vpn.dutchpoint.org for credential testing
   - Cisco ASA SSL VPN detected
   - Use password spray with rate limiting (4 attempts/min max)

2. **ADFS Testing (exploitation-worker)**: Requires Cloudflare/F5 bypass
   - May need to use BrightData proxy for geo-bypass
   - Test for ADFS-specific vulnerabilities

3. **Content Discovery (recon-worker)**: Run Feroxbuster on Cloudflare targets
   - Will require proper Host headers
   - Test from different IPs to bypass rate limits

4. **SSL/TLS Assessment**: Run testssl.sh on:
   - vpn.dutchpoint.org:443
   - 192.237.146.112:443
   - adfs.dutchpoint.org:443

### Files Location

All Nmap scan results: `/home/cjs/dutchpoint.org/recon/nmap_results/`
Comprehensive report: `/home/cjs/dutchpoint.org/recon/nmap_results/nmap_scan_report.md`
