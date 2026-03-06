---
name: reporting-worker-phase3
description: Phase 3 reporting specialist - exploitation synthesis, CVSS scoring, and executive summary
---

# Phase 3 Reporting Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use for Phase 3 reporting features:
- Exploitation findings aggregation
- CVSS v3.1 scoring
- Attack chain documentation
- Executive summary generation

## Work Procedure

### Exploitation Aggregation:

1. **Collect All Evidence**
   ```bash
   mkdir -p reports/phase3/evidence
   cp exploits/*.txt reports/phase3/evidence/
   cp exploits/*.png reports/phase3/evidence/
   cp exploits/*.md reports/phase3/evidence/
   ```

2. **Categorize Findings**
   - Critical (CVSS 9.0-10.0)
   - High (CVSS 7.0-8.9)
   - Medium (CVSS 4.0-6.9)
   - Low (CVSS 0.1-3.9)

3. **Create Exploitation Matrix**
   | Vulnerability | Target | Impact | CVSS | Evidence |
   |--------------|--------|--------|------|----------|
   | SQL Injection | /api/v1/users | DB access | 9.8 | sqlmap_output.txt |
   | Reflected XSS | /search?q= | Code exec | 7.5 | xss_proof.png |

### CVSS Scoring:

1. **Score Each Vulnerability**
   Use CVSS v3.1 calculator with metrics:
   - **AV** (Attack Vector): Network, Adjacent, Local, Physical
   - **AC** (Attack Complexity): Low, High
   - **PR** (Privileges Required): None, Low, High
   - **UI** (User Interaction): None, Required
   - **S** (Scope): Unchanged, Changed
   - **C** (Confidentiality Impact): None, Low, High
   - **I** (Integrity Impact): None, Low, High
   - **A** (Availability Impact): None, Low, High

2. **Document Justification**
   ```markdown
   ## SQL Injection (CVE-XXXX-XXXX)
   
   **CVSS Score:** 9.8 CRITICAL
   
   **Metrics:**
   - AV:N (Network) - Remotely exploitable
   - AC:L (Low) - No special conditions
   - PR:N (None) - No authentication required
   - UI:N (None) - No user interaction
   - S:U (Unchanged) - No scope change
   - C:H (High) - Full database access
   - I:H (High) - Can modify data
   - A:H (High) - Can delete data
   
   **Vector String:** CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
   ```

### Attack Chain Creation:

1. **Map Exploit Chains**
   ```
   Recon: Subdomain discovery (vpn.dutchpoint.org)
     ↓
   Vuln: Default credentials or weak auth
     ↓
   Exploit: Successful login
     ↓
   Post-Exploit: Lateral movement to internal DB
     ↓
   Impact: PII access
   ```

2. **Document Each Step**
   - Entry point
   - Vulnerability exploited
   - Access gained
   - Next pivot
   - Final impact

3. **Create Diagram**
   ```mermaid
   graph LR
       A[Public Website] -->|SQLi| B[Database Access]
       B -->|Credentials| C[VPN Login]
       C -->|Network Access| D[Internal DB]
       D -->|PII Dump| E[Data Breach]
   ```

### Executive Summary:

1. **Non-Technical Overview** (1-2 pages)
   - What was tested
   - High-level findings
   - Business impact
   - Top 3 priorities

2. **Risk Heat Map**
   ```
   ┌─────────────────────────────────┐
   │  RISK HEAT MAP                  │
   ├──────────┬──────────┬───────────┤
   │ CRITICAL │   HIGH   │  MEDIUM   │
   │    2     │    3     │     4     │
   ├──────────┴──────────┴───────────┤
   │ LOW: 5  │  INFO: 8               │
   └─────────────────────────────────┘
   ```

3. **Strategic Recommendations**
   - Immediate actions (<24 hours)
   - Short-term fixes (<7 days)
   - Long-term improvements (<90 days)

## Example Handoff

```json
{
  "salientSummary": "Generated Phase 3 exploitation report: 8 confirmed vulnerabilities (2 critical, 3 high, 3 medium), 2 attack chains mapped. Top findings: SQLi in /api/v1/users (CVSS 9.8 - unauthenticated DB access), Reflected XSS in search (CVSS 7.5), WAF bypass via headers (CVSS 6.5). Executive summary created with risk heat map and 30/60/90 day remediation roadmap.",
  "whatWasImplemented": "Aggregated exploitation findings from 5 features, assigned CVSS v3.1 scores with full metric justification, created 2 attack chain diagrams (SQLi->DB access, XSS->session theft), generated technical report (23 pages) and executive summary (2 pages). All reports saved to reports/phase3/.",
  "whatWasLeftUndone": "Did not create video demonstrations (out of scope). Compliance mapping (PCI-DSS) not included. Cost-benefit analysis for remediation options not performed.",
  "verification": {
    "commandsRun": [
      {
        "command": "cat reports/phase3/vulnerability_report.md | grep -E '^## ' | wc -l",
        "exitCode": 0,
        "observation": "Report contains 8 vulnerability sections matching confirmed exploits"
      },
      {
        "command": "ls -la reports/phase3/evidence/ | grep -E \"png|txt|md\"",
        "exitCode": 0,
        "observation": "15 evidence files collected (screenshots, logs, payloads)"
      },
      {
        "command": "markdown-pdf reports/phase3/executive_summary.md -o reports/phase3/executive_summary.pdf",
        "exitCode": 0,
        "observation": "PDF generated (2 pages, 654KB)"
      }
    ],
    "interactiveChecks": [
      {
        "action": "Reviewed CVSS scores for 2 critical vulnerabilities",
        "observed": "Scores correctly reflect impact: SQLi (9.8) allows full DB access, Auth bypass (9.1) grants admin privileges"
      },
      {
        "action": "Verified attack chain diagram shows clear path from recon to impact",
        "observed": "Chain #1 documents: Subdomain discovery -> SQLi in API -> DB credentials -> Lateral movement. 4 hops with screenshots."
      }
    ]
  },
  "tests": {
    "added": [
      {
        "file": "reports/phase3/cvss_scores.md",
        "cases": [
          {
            "name": "SQLi CVSS 9.8 justified",
            "verifies": "Full metric breakdown documented with business context (financial institution)"
          },
          {
            "name": "XSS CVSS 7.5 justified",
            "verifies": "Metrics reflect stored XSS in financial calculator with session theft potential"
          }
        ]
      }
    ]
  },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- Vulnerability count doesn't match exploitation features (need investigation)
- CVSS scores disputed (need expert review)
- Evidence missing for critical findings (need worker re-run)
- Executive summary requires business context (need stakeholder input)
