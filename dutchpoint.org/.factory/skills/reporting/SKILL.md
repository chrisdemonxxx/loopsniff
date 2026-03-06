---
name: reporting-worker
description: Vulnerability report generation, risk assessment, and remediation planning
---

# Reporting Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Use this worker for all reporting and analysis features:
- Vulnerability correlation and attack chain creation
- Risk assessment with CVSS scoring
- Remediation roadmap development
- Executive summary generation

## Work Procedure

### Vulnerability Correlation:
1. **Aggregate All Findings**
   - Collect all confirmed vulnerabilities from previous phases
   - Group by affected system/component
   - Remove duplicates

2. **Identify Attack Chains**
   - Map how vulnerabilities chain together
   - Example: Recon -> SQLi -> Credential theft -> Lateral movement -> Data exfiltration
   - Calculate combined impact

3. **Create Attack Path Diagrams**
   - Use Mermaid.js or similar for visualization
   - Show entry points, pivot points, final targets
   - Document required conditions for each step

### Risk Assessment:
1. **CVSS v3.1 Scoring**
   - Score each vulnerability independently
   - Use CVSS calculator: https://www.first.org/cvss/calculator/3.1
   - Document base metrics (AV, AC, PR, UI, S, C, I, A)

2. **Contextual Risk Adjustment**
   - Consider business context (financial institution = higher impact)
   - Factor in existing controls (WAF, MFA, monitoring)
   - Adjust for data sensitivity (PII, financial data)

3. **Prioritization Matrix**
   - Critical (CVSS 9.0-10.0): Immediate action required
   - High (CVSS 7.0-8.9): Fix within 7 days
   - Medium (CVSS 4.0-6.9): Fix within 30 days
   - Low (CVSS 0.1-3.9): Fix within 90 days

### Remediation Planning:
1. **Specific Technical Fixes**
   - Each vulnerability gets detailed remediation steps
   - Include code snippets where applicable
   - Reference vendor security advisories

2. **Effort Estimation**
   - Quick fix (<1 day), Medium (1-5 days), Large (>5 days)
   - Note dependencies, required testing

3. **Compensating Controls**
   - Immediate mitigations while permanent fixes developed
   - WAF rules, firewall changes, access restrictions

### Report Generation:
1. **Executive Summary**
   - 1-2 page non-technical overview
   - Risk heat map
   - Top 5 critical findings
   - Strategic recommendations

2. **Technical Report**
   - Detailed findings with evidence
   - Reproduction steps
   - CVSS scores and justification
   - Remediation guidance

3. **Appendix**
   - Tool outputs
   - Full scan results
   - Timeline of testing
   - Scope documentation

## Example Handoff

```json
{
  "salientSummary": "Generated comprehensive pentest report: 23 confirmed vulnerabilities (2 critical, 6 high, 9 medium, 6 low), 4 attack chains mapped, CVSS v3.1 scoring complete. Top critical findings: (1) SQLi -> database compromise -> PII access (CVSS 9.8), (2) File upload -> RCE -> root access (CVSS 9.6). Remediation roadmap prioritized by risk, estimated effort: 45-60 days for full remediation. Executive summary + technical report generated.",
  "whatWasImplemented": "Created complete pentest deliverables: (1) Vulnerability correlation report with 23 findings aggregated across all phases, (2) Attack chain analysis showing 4 distinct paths from initial access to critical data, (3) CVSS v3.1 scoring for all vulnerabilities with full metric documentation, (4) Prioritized remediation roadmap with effort estimates and compensating controls, (5) Executive summary (2 pages) for leadership, (6) Technical report (47 pages) with detailed reproduction steps and evidence. All reports in Markdown and PDF formats.",
  "whatWasLeftUndone": "Did not create video demonstrations of exploits (out of scope). No cost-benefit analysis for remediation options. Compliance mapping (PCI-DSS, SOC2) not included - would require separate engagement. Risk acceptance documentation templates not created.",
  "verification": {
    "commandsRun": [
      {
        "command": "cat /home/cjs/dutchpoint.org/reports/vulnerability_summary.md | grep -E '^#' | wc -l",
        "exitCode": 0,
        "observation": "Report contains 23 vulnerability sections (matching confirmed findings)"
      },
      {
        "command": "python3 /tools/cvss_calculator.py --batch /home/cjs/dutchpoint.org/reports/vulns.json",
        "exitCode": 0,
        "observation": "CVSS scores calculated: 2 critical (9.0+), 6 high (7.0-8.9), 9 medium (4.0-6.9), 6 low (<4.0)"
      },
      {
        "command": "markdown-pdf /home/cjs/dutchpoint.org/reports/executive_summary.md -o /home/cjs/dutchpoint.org/reports/executive_summary.pdf",
        "exitCode": 0,
        "observation": "PDF generated successfully (2 pages, 847KB)"
      },
      {
        "command": "markdown-pdf /home/cjs/dutchpoint.org/reports/technical_report.md -o /home/cjs/dutchpoint.org/reports/technical_report.pdf",
        "exitCode": 0,
        "observation": "PDF generated successfully (47 pages, 12.3MB)"
      }
    ],
    "interactiveChecks": [
      {
        "action": "Reviewed attack chain diagram in report",
        "observed": "Attack Chain #1 clearly shows: Public website -> SQLi in /api/v1/users -> database credentials -> lateral movement to HR DB -> PII access. 5 hops documented with screenshots at each stage."
      },
      {
        "action": "Verified remediation steps for critical SQLi vulnerability",
        "observed": "Remediation includes: (1) Code fix with parameterized query example, (2) WAF rule to deploy immediately, (3) Input validation library recommendation, (4) Testing checklist. Estimated effort: 4 hours."
      },
      {
        "action": "Checked executive summary risk heat map",
        "observed": "Visual heat map shows 2 critical (red), 6 high (orange) vulnerabilities. Organized by OWASP category and business impact. Non-technical language used throughout."
      }
    ]
  },
  "tests": {
    "added": []
  },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- Vulnerability count exceeds report template capacity (need to restructure)
- CVSS scoring disputed (need expert review)
- Remediation effort estimates unrealistic (need stakeholder input)
- Report reveals scope gaps (need to expand scope)
- Executive summary requires business context not available (need stakeholder interviews)
