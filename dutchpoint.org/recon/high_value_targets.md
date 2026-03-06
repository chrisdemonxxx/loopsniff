# High-Value Targets - dutchpoint.org
# Generated: 2026-03-06
# Priority Assessment for Active Scanning

## CRITICAL PRIORITY (CVSS 9.0+)

### 1. ADFS Authentication Portal
- **Subdomain:** adfs.dutchpoint.org
- **IP:** 192.237.146.112
- **Port:** 443 (HTTPS)
- **Risk:** Authentication bypass, credential harvesting, SSO exploitation
- **Technology:** Microsoft Active Directory Federation Services
- **Recommendation:** Test for ADFS-specific vulnerabilities, password spray protection

### 2. Q2 Digital Banking Platform
- **Subdomain:** secure.dutchpoint.org
- **IP:** 192.0.63.252, 192.0.54.4
- **Port:** 443 (HTTPS)
- **Risk:** Financial data exposure, authentication vulnerabilities
- **Technology:** Q2 Digital Banking (third-party hosted)
- **Recommendation:** Check for Q2 platform known vulnerabilities

## HIGH PRIORITY (CVSS 7.0-8.9)

### 3. Remote Access Portal
- **Subdomain:** remote.dutchpoint.org
- **IP:** 160.72.101.187
- **Port:** Likely 443 (HTTPS)
- **Risk:** Remote access exploitation, authentication bypass
- **Technology:** Unknown remote access platform
- **Recommendation:** Identify platform and test authentication mechanisms

### 4. VPN Endpoints (Multiple)
- **vpn.dutchpoint.org:** 160.72.101.178
- **drvpn.dutchpoint.org:** 192.64.66.226 (DR site)
- **vpnberlin.dutchpoint.org:** 192.237.146.112 (Berlin office)
- **Risk:** VPN credential harvesting, configuration weaknesses
- **Technology:** Likely Cisco, Fortinet, or Pulse Secure
- **Recommendation:** Enumerate VPN type, test for default credentials

### 5. Admin Portal
- **Subdomain:** admin.dutchpoint.org
- **IP:** 104.16.174.82, 104.16.173.82 (Cloudflare protected)
- **Risk:** Administrative access, privilege escalation
- **Technology:** Unknown (Cloudflare 403 observed)
- **Recommendation:** Attempt to bypass Cloudflare WAF, identify backend technology

## MEDIUM PRIORITY (CVSS 4.0-6.9)

### 6. Tomcat Application Server
- **Subdomain:** tomcat1.dutchpoint.org
- **IP:** 192.237.146.112
- **Port:** 8080 (Tomcat Manager likely)
- **Risk:** Tomcat Manager exploitation, WAR deployment
- **Technology:** Apache Tomcat (version unknown)
- **Recommendation:** Test for Tomcat Manager default credentials, CVEs

### 7. PSCU Integration
- **Subdomain:** quickassist.pscu.dutchpoint.org
- **IP:** 192.237.146.112
- **Risk:** Third-party integration vulnerabilities
- **Technology:** PSCU payment processing
- **Recommendation:** Identify integration type and test authentication

### 8. Symitar Core Banking
- **Subdomain:** quickassist.symitar.dutchpoint.org
- **IP:** 192.237.146.112
- **Risk:** Core banking access
- **Technology:** Symitar core banking system
- **Recommendation:** Investigate API endpoints and authentication

### 9. Payment Processing (FICO CCS)
- **Subdomain:** mail-content.payments.dutchpoint.org
- **IP:** 34.196.154.214, 34.237.152.170
- **Risk:** Payment card data exposure
- **Technology:** FICO Card Customer Service
- **Recommendation:** Test for payment card data exposure

## LOW PRIORITY (CVSS 0.1-3.9)

### 10. Member Onboarding (ECU Technology)
- **Subdomain:** join.dutchpoint.org
- **IP:** 160.153.108.198
- **Risk:** Member registration vulnerabilities
- **Technology:** ECU Technology platform
- **Recommendation:** Test registration form for input validation

### 11. Branch Portal (Clutch Partners)
- **Subdomain:** branch-portal.dutchpoint.org
- **IP:** 104.18.6.248, 104.18.7.248
- **Risk:** Branch staff portal access
- **Technology:** Clutch Partners platform
- **Recommendation:** Test for staff portal authentication

### 12. Loan Application Portal
- **Subdomain:** loans.dutchpoint.org
- **IP:** 104.18.6.248, 104.18.7.248 (same as branch-portal)
- **Risk:** Loan application data exposure
- **Technology:** Clutch Partners platform
- **Recommendation:** Test form handling and data validation

### 13. P2P Payments (Payzur)
- **Subdomain:** p2p.dutchpoint.org
- **IP:** prod.payzur.com (CNAME)
- **Risk:** Payment transfer vulnerabilities
- **Technology:** Payzur third-party platform
- **Recommendation:** Review Payzur security posture

## INFORMATIONAL TARGETS

### 14. Internal Infrastructure
- **web12.dutchpoint.org, web13.dutchpoint.org:** Internal web servers
- **mgr.dutchpoint.org:** Management interface (Cloudflare protected)
- **o12.89.dutchpoint.org:** Unknown internal service

### 15. Email Infrastructure
- **mail.dutchpoint.org:** 160.72.101.181 - Mail server
- **mailsafe.dutchpoint.org:** Secure email (GoDaddy)
- **mail-content.payments.dutchpoint.org:** FICO payment notifications

### 16. Disaster Recovery
- **remotedr.dutchpoint.org:** DR remote access (192.237.146.112)
- **drvpn.dutchpoint.org:** DR VPN endpoint (192.64.66.226)

## Attack Surface Summary

| Category | Count | Priority |
|----------|-------|----------|
| Authentication Endpoints | 3 | CRITICAL |
| Remote Access/VPN | 4 | HIGH |
| Financial Services | 3 | HIGH |
| Core Banking | 2 | MEDIUM |
| Third-Party Integrations | 5 | MEDIUM |
| Internal Infrastructure | 4 | LOW |
| **Total High-Value Targets** | **21** | - |

## Recommended Testing Priorities

1. **Phase 1:** ADFS authentication testing (password spray protection)
2. **Phase 2:** VPN endpoint enumeration and credential testing
3. **Phase 3:** Admin portal WAF bypass and authentication testing
4. **Phase 4:** Tomcat Manager exploitation attempts
5. **Phase 5:** Payment processing and core banking API testing
6. **Phase 6:** Branch portal and member onboarding testing
