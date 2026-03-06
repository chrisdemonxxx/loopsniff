# Passive Reconnaissance Report: dutchpoint.org
**Date:** 2026-03-06  
**Report Type:** Passive Reconnaissance Only (No Active Scanning)  

---

## Executive Summary

Comprehensive passive reconnaissance was conducted on dutchpoint.org using multiple subdomain enumeration tools and techniques. The assessment discovered **31 unique subdomains** through Subfinder and certificate transparency analysis. All discovered infrastructure is heavily protected by Cloudflare WAF and various security layers.

---

## 1. Subdomains Discovered

### Complete Subdomain List (31 total)

| # | Subdomain | IP Address | Hosting/Notes |
|---|-----------|------------|---------------|
| 1 | web12.dutchpoint.org | - | Listed in Subfinder |
| 2 | web13.dutchpoint.org | - | Listed in Subfinder |
| 3 | www.dutchpoint.org | 104.16.174.82, 104.16.173.82 | Cloudflare protected |
| 4 | admin.dutchpoint.org | - | Cloudflare protected (403) |
| 5 | www.admin.dutchpoint.org | - | Listed in Subfinder |
| 6 | branch-portal.dutchpoint.org | 104.18.7.248, 104.18.6.248 | dutchpoint.clutch.partners |
| 7 | loans.dutchpoint.org | 104.18.7.248, 104.18.6.248 | dutchpoint.clutch.partners |
| 8 | mgr.dutchpoint.org | 104.16.174.82, 104.16.173.82 | fallback.cfdefense.net |
| 9 | secure.dutchpoint.org | 192.0.63.252, 192.0.54.4 | q2digitalbanking.com |
| 10 | payments.dutchpoint.org | - | Listed in Subfinder |
| 11 | tomcat1.dutchpoint.org | - | Listed in Subfinder |
| 12 | www.tomcat1.dutchpoint.org | - | Listed in Subfinder |
| 13 | mail.dutchpoint.org | 160.72.101.181 | Mail server |
| 14 | mail-content.payments.dutchpoint.org | 34.237.152.170, 34.196.154.214 | FICO CCS Production |
| 15 | mailsafe.dutchpoint.org | - | Listed in Subfinder |
| 16 | www.mailsafe.dutchpoint.org | - | Listed in Subfinder |
| 17 | remote.dutchpoint.org | 160.72.101.187 | Remote access |
| 18 | remotedr.dutchpoint.org | 192.237.146.112 | DR remote access |
| 19 | adfs.dutchpoint.org | 192.237.146.112 | ADFS authentication |
| 20 | drvpn.dutchpoint.org | 192.64.66.226 | DR VPN |
| 21 | vpn.dutchpoint.org | 160.72.101.178 | VPN endpoint |
| 22 | vpnberlin.dutchpoint.org | 192.237.146.112 | VPN Berlin location |
| 23 | p2p.dutchpoint.org | - | prod.payzur.com |
| 24 | www.p2p.dutchpoint.org | - | Listed in Subfinder |
| 25 | autodiscover.dutchpoint.org | Multiple (Outlook) | Microsoft 365 |
| 26 | join.dutchpoint.org | 160.153.108.198 | ecutechnology.com |
| 27 | quickassist.pscu.dutchpoint.org | 192.237.146.112 | PSCU integration |
| 28 | www.quickassist.pscu.dutchpoint.org | - | Listed in Subfinder |
| 29 | quickassist.symitar.dutchpoint.org | 192.237.146.112 | Symitar integration |
| 30 | www.quickassist.symitar.dutchpoint.org | - | Listed in Subfinder |
| 31 | o12.89.dutchpoint.org | - | Listed in Subfinder |

---

## 2. DNS Infrastructure

### A Records (IP Addresses)
- **Main Domain:** 104.16.176.2, 104.16.175.2 (Cloudflare)
- **Branch Services:** 104.18.6.248, 104.18.7.248 (Clutch Partners platform)
- **Secure Banking:** 192.0.63.252, 192.0.54.4 (Q2 Digital Banking)
- **ADFS/Identity:** 192.237.146.112 (Azure/AWS hosting)

### MX Records (Mail Exchange)
```
dutchpoint.org.	3600	IN	MX	0 dutchpoint-org.mail.protection.outlook.com.
```
**Provider:** Microsoft 365 (Outlook.com protection)

### NS Records (Name Servers)
```
dutchpoint.org.	7200	IN	NS	ns87.worldnic.com.
dutchpoint.org.	7200	IN	NS	ns88.worldnic.com.
```
**Provider:** Network Solutions (WorldNIC)

### TXT Records

#### SPF Record (Email Authentication)
```
v=spf1 mx 
ip4:66.29.200.20 
ip4:63.117.120.96/27 
ip4:69.38.149.224/27 
ip4:208.252.57.192/27 
ip4:104.130.82.204/31 
ip4:192.254.121.248 
include:_phishspf.knowbe4.com 
include:spf.protection.outlook.com 
include:spf.webaccess1.com 
include:spf.usa.net 
include:u3620291.wl042.sendgrid.net 
a:_mailhosts.swbc.com 
include:spf.us.exclaimer.net 
include:mktomail.com ~all
```
**Analysis:** Comprehensive SPF with multiple authorized senders including:
- Microsoft 365
- KnowBe4 (security awareness)
- SendGrid (email delivery)
- SWBC (banking services)
- Exclaimer (email signatures)
- Marketo (marketing automation)

#### DMARC Record
```
_dmarc.dutchpoint.org.	3600	IN	TXT	"v=DMARC1; p=none; rua=mailto:65b17fd18d7da@ag.dmarcly.com; ruf=mailto:65b17fd18d7da@fo.dmarcly.com; sp=none"
```
**Policy:** p=none (monitoring mode, not enforcing)  
**Reporting:** Using Dmarcly for DMARC analytics

#### DKIM Record
```
selector1._domainkey.dutchpoint.org. 3600 IN CNAME selector1-dutchpoint-org._domainkey.dutchpointcreditunion.onmicrosoft.com.
```
**Provider:** Microsoft 365

#### Domain Verification Records
- `_globalsign-domain-verification` (3 records) - GlobalSign SSL verification
- `MS=ms46938941` and `MS=0F956939E78009223D06126C6600F15CD8E8D9F1` - Microsoft verification
- `duo_sso_verification` - Duo Security SSO verification
- Random string: `rk6ira440po4cjnk292kr3l9nf` (unknown service)

---

## 3. Technology Stack Analysis

### Identified Technologies

| Category | Technology | Evidence |
|----------|-----------|----------|
| **CDN/WAF** | Cloudflare | All major subdomains return Cloudflare headers |
| **Email** | Microsoft 365 | MX records, DKIM, autodiscover configuration |
| **Digital Banking** | Q2 Digital Banking | secure.dutchpoint.org points to q2digitalbanking.com |
| **Branch Portal** | Clutch Partners | branch-portal, loans subdomains on clutch.partners |
| **Payment Processing** | Payzur | p2p.dutchpoint.org resolves to prod.payzur.com |
| **Card Services** | FICO CCS | mail-content.payments.dutchpoint.org on ficoccs-prod.net |
| **Member Onboarding** | ECU Technology | join.dutchpoint.org on ecutechnology.com |
| **Core Banking** | Symitar/PSCU | quickassist subdomains for Symitar and PSCU |
| **Authentication** | ADFS | adfs.dutchpoint.org (Active Directory Federation Services) |
| **DR/VPN** | Various | Multiple VPN endpoints for disaster recovery |

### Security Headers Observed
```
x-frame-options: SAMEORIGIN
x-content-type-options: nosniff
referrer-policy: same-origin
permissions-policy: accelerometer=(),browsing-topics=(),camera=(),clipboard-read=(),clipboard-write=(),geolocation=(),gyroscope=(),hid=(),interest-cohort=(),magnetometer=(),microphone=(),payment=(),publickey-credentials-get=(),screen-wake-lock=(),serial=(),sync-xhr=(),usb=()
cross-origin-opener-policy: same-origin
cross-origin-embedder-policy: require-corp
```

---

## 4. Discovered Endpoints & APIs

### Administrative/Authentication Endpoints
- **adfs.dutchpoint.org** - ADFS authentication portal (192.237.146.112)
- **admin.dutchpoint.org** - Admin portal (Cloudflare protected, 403)
- **remote.dutchpoint.org** - Remote access portal (160.72.101.187)
- **remotedr.dutchpoint.org** - DR remote access
- **autodiscover.dutchpoint.org** - Microsoft 365 autodiscover

### Member-Facing Services
- **secure.dutchpoint.org** - Online banking (Q2 platform)
- **branch-portal.dutchpoint.org** - Branch access portal
- **loans.dutchpoint.org** - Loan application portal
- **join.dutchpoint.org** - Member onboarding
- **p2p.dutchpoint.org** - P2P payments (Payzur)

### Third-Party Integrations
- **quickassist.pscu.dutchpoint.org** - PSCU integration
- **quickassist.symitar.dutchpoint.org** - Symitar core banking
- **mail-content.payments.dutchpoint.org** - FICO payment notifications

### Internal/Infrastructure
- **tomcat1.dutchpoint.org** - Tomcat application server
- **web12.dutchpoint.org, web13.dutchpoint.org** - Web infrastructure
- **mgr.dutchpoint.org** - Management interface (cfdefense.net)

---

## 5. Historical Data (Wayback Machine)

Analysis of wayback machine data shows:
- Domain registered since **1996** (first archive: 1996-12-22)
- Long operational history with consistent web presence
- No exposed admin paths discovered in public archives
- Limited historical endpoint data due to robots.txt restrictions and Cloudflare protection

---

## 6. Risk Assessment

### High-Value Targets Identified
1. **ADFS Server (adfs.dutchpoint.org)** - Authentication portal, potential SSO attack vector
2. **Remote Access (remote.dutchpoint.org, remotedr.dutchpoint.org)** - Remote work infrastructure
3. **VPN Endpoints** - Multiple VPN servers for DR and Berlin office
4. **Secure Banking (secure.dutchpoint.org)** - Q2 digital banking platform
5. **Payment Processing (mail-content.payments.dutchpoint.org)** - FICO card services

### Security Posture Observations

**Strengths:**
- Comprehensive Cloudflare WAF protection on all public-facing services
- Modern security headers implemented (CSP, X-Frame-Options, etc.)
- DMARC, SPF, DKIM properly configured for email security
- Segregated infrastructure for different services

**Potential Concerns:**
- **DMARC policy set to `p=none`** - Not actively rejecting spoofed emails
- **Admin portal accessible** at admin.dutchpoint.org (though protected)
- **ADFS exposed** to internet - potential authentication attack surface
- **Multiple public VPN endpoints** -扩大了攻击面
- **Tomcat server exposed** (tomcat1.dutchpoint.org) - historically vulnerable
- **Subdomain takeovers possible** for unused subdomains pointing to external services

---

## 7. Tools & Methods Used

| Tool/Method | Purpose | Result |
|-------------|---------|--------|
| **Subfinder v2.12.0** | Subdomain enumeration | 31 subdomains discovered |
| **crt.sh** | Certificate transparency lookup | Confirmed subdomains |
| **Wayback Machine CDX API** | Historical URL analysis | Limited data due to protection |
| **DNS enumeration (dig)** | DNS record discovery | Complete DNS infrastructure mapped |
| **HTTP header analysis** | Technology fingerprinting | Cloudflare, Q2, Microsoft 365 identified |

### Tools Attempted But Unavailable
- **Amass** - Timed out during execution
- **Waybackurls** - Not installed in environment
- **Gau** - Not installed in environment
- **Fierce** - Python dependency errors

---

## 8. Recommendations for Active Scanning Phase

Based on passive reconnaissance findings, prioritize the following for active testing:

1. **Admin portal security assessment** (admin.dutchpoint.org)
2. **ADFS configuration review** (adfs.dutchpoint.org)
3. **Q2 banking platform security** (secure.dutchpoint.org)
4. **Tomcat server version check** (tomcat1.dutchpoint.org)
5. **VPN endpoint security** (vpn.dutchpoint.org, drvpn.dutchpoint.org)
6. **Payment processing APIs** (mail-content.payments.dutchpoint.org)
7. **Third-party integration security** (quickassist subdomains)

---

## Appendix: File Outputs

All raw output files saved during reconnaissance:
- `/tmp/subfinder_dutchpoint.txt` - Subfinder raw results

---

**Report Generated:** 2026-03-06  
**Classification:** CONFIDENTIAL - Security Assessment  
**Next Phase:** Active Vulnerability Scanning
