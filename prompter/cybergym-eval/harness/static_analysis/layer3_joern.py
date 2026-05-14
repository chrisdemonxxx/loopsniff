#!/usr/bin/env python3
"""Layer 3: Joern CFG/PDG analysis for C/C++.

Focus on memory bugs via control/data flow graph queries.
"""
import json
import subprocess
from typing import List, Dict, Any
from pathlib import Path
from .layer1_semgrep import Finding


class JoernAnalyzer:
    """Joern-based CFG/PDG analysis for memory bugs."""
    
    QUERIES = {
        "unsafe_copy": """
            // memcpy/strcpy with size from external input
            cpg.call.name("memcpy|strcpy|strncpy|memset").where(
                _.argument.order(2).reachableBy(cpg.call.name("read|recv|fread|gets"))
            ).location.l
        """,
        
        "use_after_free": """
            // free() followed by dereference in same function
            cpg.method.ast.isCall.name("free").inAst.isIdentifier.flatMap { freed =>
                freed.refsTo.flatMap { local =>
                    local.referencingIdentifiers.where(_.inCall.name(".*").inAst.isMethod == freed.inAst.isMethod)
                }
            }.location.l
        """,
        
        "pointer_arithmetic": """
            // Pointer arithmetic on values from external input
            cpg.call.name("\\+|\\-").where(
                _.argument.order(1).typ.name(".*\\*.*")
            ).where(
                _.argument.reachableBy(cpg.call.name("read|recv|fread|scanf"))
            ).location.l
        """,
    }
    
    def __init__(self):
        pass
    
    def analyze(self, target_dir: Path) -> List[Finding]:
        """Run Joern on target directory (C/C++ only).
        
        Args:
            target_dir: Path to analyze
            
        Returns:
            List of Finding objects
        """
        if not self._check_joern_installed():
            print("WARNING: Joern not installed, skipping Layer 3")
            print("Install: https://joern.io/")
            return []
        
        # Check for C/C++ files
        c_cpp_files = list(target_dir.rglob("*.c")) + list(target_dir.rglob("*.cpp"))
        if not c_cpp_files:
            print("[Joern] No C/C++ files found, skipping")
            return []
        
        findings = []
        
        # Create CPG
        cpg_path = target_dir / ".joern-cpg"
        if not self._create_cpg(target_dir, cpg_path):
            return []
        
        # Run each query
        for query_name, query_code in self.QUERIES.items():
            print(f"[Joern] Running query: {query_name}")
            query_findings = self._run_query(cpg_path, query_name, query_code, target_dir)
            findings.extend(query_findings)
        
        print(f"[Joern] Found {len(findings)} CFG/PDG findings")
        
        return findings
    
    def _check_joern_installed(self) -> bool:
        """Check if Joern is installed."""
        try:
            subprocess.run(
                ["joern", "--version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def _create_cpg(self, target_dir: Path, cpg_path: Path) -> bool:
        """Create Code Property Graph."""
        if cpg_path.exists():
            print(f"  Using existing CPG: {cpg_path}")
            return True
        
        try:
            result = subprocess.run(
                [
                    "joern-parse",
                    str(target_dir),
                    "--output", str(cpg_path),
                ],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            if result.returncode != 0:
                print(f"  WARNING: CPG creation failed: {result.stderr}")
                return False
            
            return True
            
        except subprocess.TimeoutExpired:
            print(f"  WARNING: CPG creation timed out after 5 minutes")
            return False
    
    def _run_query(
        self, 
        cpg_path: Path, 
        query_name: str, 
        query_code: str,
        target_dir: Path
    ) -> List[Finding]:
        """Run a Joern query and parse results."""
        try:
            # Write query to temp file
            query_file = cpg_path.parent / f"query-{query_name}.sc"
            query_file.write_text(query_code)
            
            # Run query via joern script
            result = subprocess.run(
                [
                    "joern",
                    "--script", str(query_file),
                    "--cpg", str(cpg_path),
                    "--out-format", "json",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if result.returncode != 0:
                print(f"    WARNING: Query {query_name} failed: {result.stderr}")
                return []
            
            # Parse JSON output
            locations = json.loads(result.stdout) if result.stdout.strip() else []
            
            findings = []
            for loc in locations:
                finding = Finding(
                    layer="joern",
                    file_path=loc.get("filename", ""),
                    line_start=loc.get("lineNumber", 1),
                    line_end=loc.get("lineNumberEnd", loc.get("lineNumber", 1)),
                    rule_id=f"joern.{query_name}",
                    severity="high",
                    message=self._get_query_description(query_name),
                    cwe=self._get_query_cwe(query_name),
                    confidence="high",
                    metadata={
                        "joern_query": query_name,
                        "method": loc.get("methodFullName", ""),
                    },
                )
                findings.append(finding)
            
            return findings
            
        except subprocess.TimeoutExpired:
            print(f"    WARNING: Query {query_name} timed out")
            return []
        except json.JSONDecodeError as e:
            print(f"    WARNING: Failed to parse query output: {e}")
            return []
    
    def _get_query_description(self, query_name: str) -> str:
        """Get human-readable description for query."""
        descriptions = {
            "unsafe_copy": "Memory copy with size derived from external input",
            "use_after_free": "Pointer dereference after free() in same function",
            "pointer_arithmetic": "Pointer arithmetic on external input",
        }
        return descriptions.get(query_name, query_name)
    
    def _get_query_cwe(self, query_name: str) -> str:
        """Map query to CWE."""
        cwe_map = {
            "unsafe_copy": "CWE-119",  # Buffer overflow
            "use_after_free": "CWE-416",  # Use after free
            "pointer_arithmetic": "CWE-823",  # Incorrect pointer scaling
        }
        return cwe_map.get(query_name, "")


if __name__ == "__main__":
    # Test on current directory
    import sys
    analyzer = JoernAnalyzer()
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    findings = analyzer.analyze(target)
    
    print(f"\nFound {len(findings)} Joern findings:")
    for f in findings[:10]:  # Show first 10
        print(f"  {f.file_path}:{f.line_start} [{f.severity}] {f.rule_id}")
