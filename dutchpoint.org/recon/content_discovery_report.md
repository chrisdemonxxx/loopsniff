# Content Discovery Report - dutchpoint.org
## Generated: 2026-03-06
## Method: Katana Web Crawler, Browser Verification, Manual Probing
## Assertion: VAL-RECON-004

---

## Executive Summary

Comprehensive content discovery across dutchpoint.org and its subdomains revealed **500+ unique endpoints**, including multiple authentication portals, financial calculators, administrative interfaces, and sensitive file references. The target is heavily protected by **Cloudflare WAF** with active JavaScript challenges on all public-facing endpoints.

---

## Critical Findings

### 🔴 High-Priority Authentication Endpoints

| Endpoint | URL | Status | Notes |
|----------|-----|--------|-------|
| **Q2 Banking Login** | https://secure.dutchpoint.org/dutchpoint/uux.aspx#login | 200 OK | Primary banking authentication - accessible |
| **VPN Login Portal** | https://vpn.dutchpoint.org/logon.html | 200 OK | Cisco ASA SSL VPN login page |
| **Password Reset** | https://secure.dutchpoint.org/dutchpoint/sdk/ForgotUsername | 405 | Q2 password reset endpoint |
| **Auto Enrollment** | https://secure.dutchpoint.org/dutchpoint/sdk/AutoEnrollmentE2E | - | Q2 self-enrollment |
| **Admin Portal** | https://admin.dutchpoint.org/ | 403 (WAF) | Cloudflare protected admin portal |
| **Loans Portal** | https://loans.dutchpoint.org/account-opening | 403 (WAF) | Clutch Partners loan application |

---

## Discovered Endpoints by Category

### Banking Platform (Q2 Digital Banking)

**Main Endpoints:**
- `/dutchpoint/uux.aspx` - Main login interface
- `/dutchpoint/sdk/authenticated/` - Authenticated area
- `/dutchpoint/sdk/ForgotUsername` - Password recovery
- `/dutchpoint/sdk/AutoEnrollmentE2E` - Auto-enrollment
- `/dutchpoint/sdk/e2e.js` - End-to-end JavaScript bundle

**Theme Assets (Platform Version 4.6.1.5F):**
- `/dutchpoint/assets/theme-q2.js`
- `/dutchpoint/assets/theme-blue.js`
- `/dutchpoint/assets/theme-smart.js`
- `/dutchpoint/assets/theme-plum.js`
- `/dutchpoint/assets/theme-glass.js`
- `/dutchpoint/assets/theme-sidedark.js`
- `/dutchpoint/assets/theme-topdark.js`
- `/dutchpoint/assets/theme-central.js`

**Localization:**
- `/dutchpoint/assets/resources/en-us.js`
- `/dutchpoint/assets/resources/es-mx.js`
- `/dutchpoint/assets/resources/zh-cn.js`
- `/dutchpoint/assets/resources/zh-tw.js`
- `/dutchpoint/assets/resources/zh-hk.js`
- `/dutchpoint/assets/resources/pt-br.js`
- `/dutchpoint/assets/resources/i18n.json`

**Mobile/Security Features:**
- `/dutchpoint/assets/stories/touch-id/0-en-us.html`
- `/dutchpoint/assets/stories/four-digit-passcode/0-en-us.html`
- `/dutchpoint/assets/android-plugins.js`
- `/dutchpoint/assets/ios-plugins.js`

### VPN Portal (Cisco ASA)

**Endpoints:**
- `/logon.html` - VPN login page
- `/+CSCOE+/message.html` - Cisco message template
- `/+CSCOE+/sdesktop/wait.html` - Secure desktop wait page
- `/+CSCOE+/sdesktop/wait_quit.html` - Secure desktop quit page

### Main Website Endpoints

**Authentication/Admin Paths:**
- `/admin/` - Admin portal (403 WAF)
- `/about-us/contact-us/` - Contact form
- `/schedule-an-appointment/` - Appointment scheduling

**Financial Calculators (KJECalc):**
- `/learn/calculators/retirement-planner/`
- `/learn/calculators/reach-your-savings-goal/`
- `/learn/calculators/debt-consolidation-calculator/`
- `/learn/calculators/explore-your-loan-options/`
- `/learn/calculators/auto-loan-refinance-interest-savings-calculator/`
- `/learn/calculators/car-loan-calculator/`
- `/learn/calculators/heloc-interest-calculator/`
- `/learn/calculators/home-equity-availability-calculator/`
- `/learn/calculators/mortgage-qualifier-calculator/`
- `/learn/calculators/mortgage-payment-calculator/

**Banking Services:**
- `/bank/checking-accounts/`
- `/bank/savings-accounts/`
- `/bank/money-market-accounts/`
- `/bank/certificates/`
- `/bank/save-to-win/`
- `/bank/retirement-accounts/`
- `/bank/student-solutions/`

**Loan Services:**
- `/borrow/auto-loans/`
- `/borrow/mortgages/`
- `/borrow/home-equity-loans/`
- `/borrow/personal-loans/`
- `/borrow/flex-line-of-credit/`
- `/borrow/student-loans/`

**Account Management:**
- `/manage/online-banking/`
- `/manage/mobile-banking/`
- `/manage/card-management/`
- `/manage/estatements/`
- `/manage/zelle/`
- `/manage/wire-transfers/`
- `/manage/savvymoney/`

### Technology Stack Detected

**Content Management:**
- Umbraco CMS (ASP.NET)
- App_Plugins/UmbracoForms

**JavaScript Libraries:**
- jQuery / jQuery UI
- FontAwesome Pro
- date-fns
- Google Tag Manager (GTM)
- KJECalc Financial Calculators

**Server/Infrastructure:**
- Cloudflare CDN/WAF
- F5 BIG-IP Load Balancer (on 192.237.146.112)
- Q2 Digital Banking Platform
- Cisco ASA (vpn.dutchpoint.org)

---

## Sensitive File Checks

| Path | Status | Response |
|------|--------|----------|
| `/.git/HEAD` | 403 | Cloudflare challenge |
| `/.git/config` | 403 | Cloudflare challenge |
| `/.env` | 403 | Cloudflare challenge |
| `/robots.txt` | 301 | Redirects to www.dutchpoint.org/robots.txt |
| `/sitemap/` | 200 | Accessible |
| `/Sitemap` | 200 | XML sitemap |
| `/admin` | 403 | Cloudflare challenge |
| `/wp-admin` | 403 | Cloudflare challenge |
| `/administrator` | 403 | Cloudflare challenge |
| `/manager` | 403 | Cloudflare challenge |
| `/phpmyadmin` | 403 | Cloudflare challenge |
| `/api` | 403 | Cloudflare challenge |
| `/api/v1` | 403 | Cloudflare challenge |
| `/graphql` | 403 | Cloudflare challenge |
| `/backup.sql` | 403 | Cloudflare challenge |
| `/backup.zip` | 403 | Cloudflare challenge |

---

## Security Headers Analysis

**Cloudflare WAF Protection:**
```
cf-mitigated: challenge
x-frame-options: SAMEORIGIN
x-content-type-options: nosniff
cross-origin-embedder-policy: require-corp
cross-origin-opener-policy: same-origin
cross-origin-resource-policy: same-origin
permissions-policy: accelerometer=(),camera=(),geolocation=(),microphone=()...
referrer-policy: same-origin
```

**Q2 Platform Headers:**
```
strict-transport-security: max-age=31536000; includeSubDomains; preload
x-content-type-options: nosniff
x-frame-options: SAMEORIGIN
x-xss-protection: 0
```

---

## Attack Surface Summary

### High-Value Targets for Testing

1. **Q2 Banking Authentication**
   - Login page: `/dutchpoint/uux.aspx`
   - Password reset: `/dutchpoint/sdk/ForgotUsername`
   - Enrollment: `/dutchpoint/sdk/AutoEnrollmentE2E`
   
2. **VPN Portal**
   - Cisco ASA SSL VPN login
   - Potential brute force target
   
3. **Financial Calculators**
   - KJECalc JavaScript forms
   - Potential XSS/injection vectors
   
4. **Loan Applications**
   - loans.dutchpoint.org/account-opening
   - Form input testing

5. **Admin Portal**
   - Needs WAF bypass for testing
   - Potential sensitive functionality

### Cloudflare Bypass Requirements

All endpoints are protected by Cloudflare WAF with:
- JavaScript challenge (`cf-mitigated: challenge`)
- Cookie-based bot detection
- Browser fingerprinting

**Recommended Testing Approach:**
1. Use browser automation with JavaScript execution
2. Respect rate limits (10 req/sec maximum)
3. Use legitimate User-Agent strings
4. Maintain session cookies

---

## Files Created

| File | Path |
|------|------|
| Katana Results (www) | `/home/cjs/dutchpoint.org/recon/katana_www.txt` |
| Katana Results (ADFS) | `/home/cjs/dutchpoint.org/recon/katana_adfs.txt` |
| Katana Results (VPN) | `/home/cjs/dutchpoint.org/recon/katana_vpn.txt` |
| Katana Results (Secure) | `/home/cjs/dutchpoint.org/recon/katana_secure.txt` |
| Endpoints Discovery | `/home/cjs/dutchpoint.org/recon/endpoints_discovered.md` |
| Content Discovery Report | `/home/cjs/dutchpoint.org/recon/content_discovery_report.md` |

---

## Statistics

| Metric | Count |
|--------|-------|
| Total Unique Endpoints | 500+ |
| Authentication Endpoints | 6 |
| Financial Calculators | 10 |
| JavaScript Files | 50+ |
| Blog Posts | 30+ |
| Location Pages | 7+ |
| High-Value Targets | 15 |

---

## Next Steps

1. **Phase 2 - Vulnerability Assessment:**
   - Test Q2 authentication for injection vulnerabilities
   - Test VPN login for brute force susceptibility
   - Test calculator inputs for XSS
   - Test loan application forms

2. **WAF Bypass Testing:**
   - Test header manipulation techniques
   - Test encoding bypass methods
   - Test timing-based bypass

3. **API Discovery:**
   - Probe Q2 platform internal APIs
   - Look for undocumented endpoints
   - Test GraphQL introspection

---

*Report generated by reconnaissance worker for VAL-RECON-004 compliance*