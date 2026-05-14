#!/usr/bin/env python3
"""Layer 1: semgrep security analysis.

Uses p/security-audit ruleset for broad vulnerability detection.
"""
import json
import subprocess
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Finding:
    """Structured finding result."""
    layer: str
    file_path: str
    line_start: int
    line_end: int
    rule_id: str
    severity: str
    message: str
    cwe: Optional[str] = None
    confidence: str = "medium"
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "cwe": self.cwe,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class SemgrepAnalyzer:
    """semgrep-based security analysis."""
    
    def __init__(self):
        self.ruleset = "p/security-audit"
        
    def analyze(self, target_dir: Path) -> List[Finding]:
        """Run semgrep on target directory.
        
        Args:
            target_dir: Path to analyze
            
        Returns:
            List of Finding objects
        """
        if not self._check_semgrep_installed():
            print("WARNING: semgrep not installed, skipping Layer 1")
            print("Install: pip install semgrep")
            return []
        
        findings = []
        
        try:
            # Run semgrep with JSON output
            result = subprocess.run(
                [
                    "semgrep",
                    "--config", self.ruleset,
                    "--json",
                    "--quiet",
                    str(target_dir),
                ],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            if result.returncode not in [0, 1]:  # 1 = findings found (success)
                print(f"WARNING: semgrep failed with code {result.returncode}")
                print(f"stderr: {result.stderr}")
                return []
            
            # Parse JSON output
            output = json.loads(result.stdout)
            results = output.get("results", [])
            
            # Convert to Finding objects
            for r in results:
                # Extract CWE from rule metadata if available
                cwe = None
                if "extra" in r and "metadata" in r["extra"]:
                    cwe_list = r["extra"]["metadata"].get("cwe", [])
                    if cwe_list:
                        cwe = cwe_list[0] if isinstance(cwe_list, list) else cwe_list
                
                finding = Finding(
                    layer="semgrep",
                    file_path=r["path"],
                    line_start=r["start"]["line"],
                    line_end=r["end"]["line"],
                    rule_id=r["check_id"],
                    severity=r.get("extra", {}).get("severity", "WARNING").lower(),
                    message=r.get("extra", {}).get("message", ""),
                    cwe=cwe,
                    confidence="medium",
                    metadata={
                        "semgrep_rule": r["check_id"],
                        "fix": r.get("extra", {}).get("fix", ""),
                    },
                )
                findings.append(finding)
            
            # Deduplicate by (file, line_range, rule_id)
            findings = self._deduplicate(findings)
            
            print(f"[semgrep] Found {len(findings)} unique findings")
            
        except subprocess.TimeoutExpired:
            print("WARNING: semgrep timed out after 5 minutes")
        except json.JSONDecodeError as e:
            print(f"WARNING: Failed to parse semgrep JSON output: {e}")
        except Exception as e:
            print(f"WARNING: semgrep analysis failed: {e}")
        
        return findings
    
    def _check_semgrep_installed(self) -> bool:
        """Check if semgrep is installed."""
        try:
            subprocess.run(
                ["semgrep", "--version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def _deduplicate(self, findings: List[Finding]) -> List[Finding]:
        """Deduplicate findings by (file, line_range, rule_id)."""
        seen = set()
        unique = []
        
        for f in findings:
            key = (f.file_path, f.line_start, f.line_end, f.rule_id)
            if key not in seen:
                seen.add(key)
                unique.append(f)
        
        return unique


if __name__ == "__main__":
    # Test on current directory
    import sys
    analyzer = SemgrepAnalyzer()
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    findings = analyzer.analyze(target)
    
    print(f"\nFound {len(findings)} findings:")
    for f in findings[:10]:  # Show first 10
        print(f"  {f.file_path}:{f.line_start} [{f.severity}] {f.rule_id}")
