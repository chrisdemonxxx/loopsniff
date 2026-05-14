#!/usr/bin/env python3
"""RL triage: rank findings by exploitability priority."""
import json
from typing import List, Dict, Any
from pathlib import Path
from collections import defaultdict
from .layer1_semgrep import Finding
from .patch_diff_miner import PatchDiffFinding


class TriageEngine:
    """Rank and deduplicate findings across all layers."""
    
    # Priority scoring rules (will be refined by GRPO later)
    PRIORITY_RULES = {
        # High priority patterns
        "network_size_in_memop": 0.90,
        "external_format_string": 0.85,
        "interprocedural_taint": 0.80,
        "use_after_free": 0.80,
        "patch_diff_incomplete": 0.75,
        "integer_narrowing_external": 0.70,
        
        # Medium priority
        "joern_pattern": 0.65,
        "codeql_single_function": 0.60,
        "custom_ast_high": 0.55,
        
        # Low priority
        "semgrep_pattern": 0.40,
        "custom_ast_low": 0.30,
        
        # Near-filter (log but don't dispatch)
        "string_literal_copy": 0.10,
    }
    
    NEAR_FILTER_THRESHOLD = 0.30
    
    def __init__(self):
        pass
    
    def triage(
        self, 
        findings: List[Finding],
        patch_diff_findings: List[PatchDiffFinding] = None
    ) -> List[Dict[str, Any]]:
        """Rank findings and deduplicate.
        
        Args:
            findings: Combined findings from all layers
            patch_diff_findings: Optional patch-diff findings
            
        Returns:
            Ranked list of findings with priority scores
        """
        # Merge patch-diff findings into Finding objects
        all_findings = findings.copy()
        if patch_diff_findings:
            all_findings.extend(self._convert_patch_diff(patch_diff_findings))
        
        # Deduplicate by (file, line_range, cwe_class)
        deduplicated = self._deduplicate(all_findings)
        print(f"[Triage] Deduplicated {len(all_findings)} → {len(deduplicated)} findings")
        
        # Calculate priority scores
        ranked = []
        for finding in deduplicated:
            priority = self._calculate_priority(finding)
            ranked.append({
                "finding": finding.to_dict(),
                "priority": priority,
                "actionable": priority >= self.NEAR_FILTER_THRESHOLD,
            })
        
        # Sort by priority
        ranked.sort(key=lambda x: x["priority"], reverse=True)
        
        # Stats
        actionable_count = sum(1 for r in ranked if r["actionable"])
        filtered_count = len(ranked) - actionable_count
        
        print(f"[Triage] Ranked {len(ranked)} findings:")
        print(f"  Actionable (≥{self.NEAR_FILTER_THRESHOLD}): {actionable_count}")
        print(f"  Near-filtered (<{self.NEAR_FILTER_THRESHOLD}): {filtered_count}")
        
        return ranked
    
    def _convert_patch_diff(self, patch_findings: List[PatchDiffFinding]) -> List[Finding]:
        """Convert PatchDiffFinding to Finding objects."""
        findings = []
        
        for pf in patch_findings:
            finding = Finding(
                layer="patch_diff",
                file_path=pf.file_path,
                line_start=0,  # Unknown from diff
                line_end=0,
                rule_id="patch_diff.incomplete_fix",
                severity="high",
                message=f"Potential incomplete fix in {pf.changed_function}",
                cwe=pf.suspected_cwe,
                confidence="medium",
                metadata={
                    "commit": pf.commit_sha,
                    "function": pf.changed_function,
                    "diff": pf.diff_excerpt,
                },
            )
            findings.append(finding)
        
        return findings
    
    def _deduplicate(self, findings: List[Finding]) -> List[Finding]:
        """Deduplicate by (file, line_range, cwe)."""
        # Group by file + cwe
        groups = defaultdict(list)
        for f in findings:
            key = (f.file_path, f.cwe)
            groups[key].append(f)
        
        # Within each group, dedupe by overlapping line ranges
        deduplicated = []
        for (file_path, cwe), group_findings in groups.items():
            # Sort by line start
            group_findings.sort(key=lambda x: x.line_start)
            
            # Merge overlapping ranges
            merged = []
            for f in group_findings:
                if not merged:
                    merged.append(f)
                else:
                    last = merged[-1]
                    # Check if overlapping (within 5 lines)
                    if f.line_start <= last.line_end + 5:
                        # Keep higher confidence/severity finding
                        if self._is_better_finding(f, last):
                            merged[-1] = f
                        # else: keep last
                    else:
                        merged.append(f)
            
            deduplicated.extend(merged)
        
        return deduplicated
    
    def _is_better_finding(self, f1: Finding, f2: Finding) -> bool:
        """Compare two findings - return True if f1 is better."""
        # Priority order: confidence > severity > layer
        conf_order = {"high": 3, "medium": 2, "low": 1}
        sev_order = {"high": 3, "error": 3, "warning": 2, "medium": 2, "low": 1}
        layer_order = {"codeql": 4, "joern": 3, "patch_diff": 3, "custom_ast": 2, "semgrep": 1}
        
        c1 = conf_order.get(f1.confidence, 1)
        c2 = conf_order.get(f2.confidence, 1)
        if c1 != c2:
            return c1 > c2
        
        s1 = sev_order.get(f1.severity, 1)
        s2 = sev_order.get(f2.severity, 1)
        if s1 != s2:
            return s1 > s2
        
        l1 = layer_order.get(f1.layer, 0)
        l2 = layer_order.get(f2.layer, 0)
        return l1 > l2
    
    def _calculate_priority(self, finding: Finding) -> float:
        """Calculate priority score for a finding."""
        base_priority = 0.40  # Default
        
        # Check for high-priority patterns
        if finding.layer == "joern":
            if "use_after_free" in finding.rule_id:
                base_priority = self.PRIORITY_RULES["use_after_free"]
            else:
                base_priority = self.PRIORITY_RULES["joern_pattern"]
        
        elif finding.layer == "codeql":
            if finding.metadata.get("interprocedural"):
                base_priority = self.PRIORITY_RULES["interprocedural_taint"]
            else:
                base_priority = self.PRIORITY_RULES["codeql_single_function"]
        
        elif finding.layer == "patch_diff":
            base_priority = self.PRIORITY_RULES["patch_diff_incomplete"]
        
        elif finding.layer == "custom_ast":
            if finding.severity == "high":
                base_priority = self.PRIORITY_RULES["custom_ast_high"]
            else:
                base_priority = self.PRIORITY_RULES["custom_ast_low"]
        
        elif finding.layer == "semgrep":
            base_priority = self.PRIORITY_RULES["semgrep_pattern"]
        
        # Boost for specific patterns
        if "format" in finding.rule_id.lower() and "external" in finding.message.lower():
            base_priority = max(base_priority, self.PRIORITY_RULES["external_format_string"])
        
        if "malloc" in finding.rule_id.lower() and "external" in finding.message.lower():
            base_priority = max(base_priority, self.PRIORITY_RULES["integer_narrowing_external"])
        
        # Boost for high confidence
        if finding.confidence == "high":
            base_priority = min(1.0, base_priority * 1.1)
        
        return round(base_priority, 2)


if __name__ == "__main__":
    # Test with sample findings
    findings = [
        Finding(
            layer="semgrep",
            file_path="test.c",
            line_start=10,
            line_end=10,
            rule_id="test.rule",
            severity="warning",
            message="Test finding",
            cwe="CWE-119",
        ),
    ]
    
    engine = TriageEngine()
    ranked = engine.triage(findings)
    
    print(f"\nRanked {len(ranked)} findings:")
    for r in ranked:
        print(f"  Priority {r['priority']}: {r['finding']['rule_id']}")
