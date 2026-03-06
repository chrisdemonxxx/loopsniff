# Technology Stack Analysis - dutchpoint.org
# Generated: 2026-03-06
# Method: HTTP Header Analysis, DNS Records, Certificate Transparency

## Identified Technologies

### 1. Content Delivery Network (CDN) & Security
| Technology | Evidence | Risk Level |
|------------|----------|------------|
| **Cloudflare WAF** | HTTP headers (cf-ray, server: cloudflare) | LOW (protective) |
| **Cloudflare DNS** | All major subdomains use Cloudflare IPs | LOW |
| **HINFO record** | RFC8482 DNS record | INFO |

### 2. Email Infrastructure
| Technology | Evidence | Risk Level |
|------------|----------|------------|
| **Microsoft 365** | MX records to outlook.com protection | LOW |
| **SPF configured** | Comprehensive SPF record with 15+ includes | LOW |
| **DKIM enabled** | CNAME to onmicrosoft.com | LOW |
| **DMARC monitoring** | p=none policy (not enforcing) | MEDIUM |

### 3. Digital Banking Platform
| Technology | Evidence | Risk Level |
|------------|----------|------------|
| **Q2 Digital Banking** | secure.dutchpoint.org -> q2digitalbanking.com | INFO |
| **Clutch Partners** | branch-portal, loans -> clutch.partners | INFO |
| **Payzur (P2P)** | p2p.dutchpoint.org -> prod.payzur.com | INFO |

### 4. Core Banking Systems
| Technology | Evidence | Risk Level |
|------------|----------|------------|
| **Symitar/PSCU** | quickassist.symitar/pscu subdomains | INFO |
| **FICO CCS** | mail-content.payments -> ficoccs-prod.net | INFO |

### 5. Authentication & Identity
| Technology | Evidence | Risk Level |
|------------|----------|------------|
| **ADFS (Active Directory Federation Services)** | adfs.dutchpoint.org | HIGH |
| **Duo Security SSO** | duo_sso_verification TXT record | INFO |
| **Microsoft Entra ID** | MS= verification records | INFO |

### 6. Web Technologies
| Technology | Evidence | Risk Level |
|------------|----------|------------|
| **Apache Tomcat** | tomcat1.dutchpoint.org on port 8080 | MEDIUM |
| **Cloudflare Bot Protection** | cf-mitigated: challenge header | INFO |

### 7. SSL/TLS Certificates
| Certificate Authority | Subdomains | Coverage |
|----------------------|------------|----------|
| **Google Trust Services** | www, admin, secure, loans, mgr | Primary Let's Encrypt issuer |
| **Let's Encrypt** | branch-portal | Automated renewal |
| **GoDaddy** | mailsafe, tomcat1 | Long-term certificates |
| **DigiCert/Thawte** | mail, remote, vpn, drvpn | Extended validation |
| **Amazon RSA** | mail-content.payments | AWS infrastructure |

## HTTP Security Headers Observed

```
x-frame-options: SAMEORIGIN
x-content-type-options: nosniff
referrer-policy: same-origin
cross-origin-embedder-policy: require-corp
cross-origin-opener-policy: same-origin
cross-origin-resource-policy: same-origin
origin-agent-cluster: ?1
permissions-policy: accelerometer=(),browsing-topics=(),camera=(),clipboard-read=(),clipboard-write=(),geolocation=(),gyroscope=(),hid=(),interest-cohort=(),magnetometer=(),microphone=(),payment=(),publickey-credentials-get=(),screen-wake-lock=(),serial=(),sync-xhr=(),usb=()
```

**Analysis:** Strong security headers are implemented. The site uses comprehensive CSP-like protections with COOP, COEP, and CORP headers.

## Third-Party Service Integrations

| Service | Purpose | Subdomain Integration |
|---------|---------|----------------------|
| **Microsoft 365** | Email & Productivity | autodiscover.dutchpoint.org |
| **KnowBe4** | Security Awareness Training | SPF include |
| **SendGrid** | Transactional Email | SPF include |
| **SWBC** | Banking Services | SPF include |
| **Exclaimer** | Email Signatures | SPF include |
| **Marketo** | Marketing Automation | SPF include |
| **GlobalSign** | SSL Verification | TXT verification |
| **ECU Technology** | Member Onboarding | join.dutchpoint.org |

## Network Infrastructure Analysis

### Primary IP Ranges
- **192.237.146.112** - ADFS, Tomcat (Azure/AWS region)
- **160.72.101.x** - VPN, Mail, Remote Access (Rackspace/Carrier)
- **192.0.63.x, 192.0.54.x** - Q2 Digital Banking Platform
- **104.16.x.x, 104.18.x.x** - Cloudflare CDN
- **34.196.x.x, 34.237.x.x** - FICO/AWS Payment Services

### Certificate Transparency Observations
- Certificates are automatically renewed via ACME (Let's Encrypt)
- Long-term DigiCert certificates for critical infrastructure (mail, vpn)
- GoDaddy certificates for payment-related services

## Security Posture Assessment

### Strengths
1. Comprehensive Cloudflare WAF protection
2. Strong HTTP security headers
3. SPF/DKIM/DMARC implemented (though DMARC p=none)
4. Segregated infrastructure for different services
5. Modern TLS certificates with auto-renewal

### Concerns
1. **DMARC policy p=none** - Not actively rejecting spoofed emails
2. **ADFS exposed to internet** - Authentication attack surface
3. **Tomcat manager potentially accessible** - Port 8080 (needs verification)
4. **Multiple VPN endpoints** - Expanded attack surface
5. **Subdomain takeover risk** - Unused subdomains pointing to external services

### Recommended Further Investigation
1. Test ADFS brute force protection
2. Verify Tomcat manager authentication
3. Test VPN endpoint security (vpn.dutchpoint.org, drvpn.dutchpoint.org, vpnberlin.dutchpoint.org)
4. Investigate payment processing APIs (mail-content.payments.dutchpoint.org)
5. Review third-party integration security (PSCU, Symitar, Payzur)
