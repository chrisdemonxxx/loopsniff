#!/usr/bin/env python3
"""Layer 2: CodeQL interprocedural analysis.

Uses the security-and-quality query suite for cross-function taint tracking.
"""
import json
import subprocess
from typing import List, Dict, Any, Optional
from pathlib import Path
from .layer1_semgrep import Finding


class CodeQLAnalyzer:
    """CodeQL-based interprocedural analysis."""
    
    SUPPORTED_LANGUAGES = {"c", "cpp", "python", "java", "javascript", "go"}
    
    def __init__(self):
        self.query_suite = "security-and-quality"
        
    def analyze(self, target_dir: Path, compile_commands: Optional[Path] = None) -> List[Finding]:
        """Run CodeQL on target directory.
        
        Args:
            target_dir: Path to analyze
            compile_commands: Optional path to compile_commands.json for C/C++
            
        Returns:
            List of Finding objects
        """
        if not self._check_codeql_installed():
            print("WARNING: CodeQL not installed, skipping Layer 2")
            print("Install: https://github.com/github/codeql-cli-binaries/releases")
            return []
        
        # Detect languages
        languages = self._detect_languages(target_dir)
        if not languages:
            print("WARNING: No supported languages detected for CodeQL")
            return []
        
        findings = []
        
        # Create database for each language
        db_dir = target_dir / ".codeql-db"
        db_dir.mkdir(exist_ok=True)
        
        for lang in languages:
            print(f"[CodeQL] Analyzing {lang}...")
            
            try:
                # Create database
                db_path = db_dir / f"db-{lang}"
                if not self._create_database(target_dir, db_path, lang, compile_commands):
                    continue
                
                # Run queries
                lang_findings = self._run_queries(db_path, lang, target_dir)
                findings.extend(lang_findings)
                
            except Exception as e:
                print(f"WARNING: CodeQL analysis failed for {lang}: {e}")
        
        print(f"[CodeQL] Found {len(findings)} interprocedural findings")
        
        return findings
    
    def _check_codeql_installed(self) -> bool:
        """Check if CodeQL CLI is installed."""
        try:
            subprocess.run(
                ["codeql", "version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def _detect_languages(self, target_dir: Path) -> List[str]:
        """Detect languages in target directory."""
        extensions = {
            ".c": "cpp",
            ".h": "cpp",
            ".cpp": "cpp",
            ".hpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".py": "python",
            ".java": "java",
            ".js": "javascript",
            ".ts": "javascript",
            ".go": "go",
        }
        
        found_langs = set()
        for ext, lang in extensions.items():
            if list(target_dir.rglob(f"*{ext}")):
                found_langs.add(lang)
        
        return list(found_langs & self.SUPPORTED_LANGUAGES)
    
    def _create_database(
        self, 
        target_dir: Path, 
        db_path: Path, 
        language: str,
        compile_commands: Optional[Path]
    ) -> bool:
        """Create CodeQL database."""
        if db_path.exists():
            print(f"  Using existing database: {db_path}")
            return True
        
        cmd = [
            "codeql", "database", "create",
            str(db_path),
            f"--language={language}",
            f"--source-root={target_dir}",
        ]
        
        # Add compile commands for C/C++
        if language == "cpp" and compile_commands and compile_commands.exists():
            cmd.extend([f"--command={compile_commands}"])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )
            
            if result.returncode != 0:
                print(f"  WARNING: Database creation failed: {result.stderr}")
                return False
            
            return True
            
        except subprocess.TimeoutExpired:
            print(f"  WARNING: Database creation timed out after 10 minutes")
            return False
    
    def _run_queries(self, db_path: Path, language: str, target_dir: Path) -> List[Finding]:
        """Run CodeQL queries on database."""
        results_file = db_path.parent / f"results-{language}.sarif"
        
        try:
            # Run analysis
            result = subprocess.run(
                [
                    "codeql", "database", "analyze",
                    str(db_path),
                    self.query_suite,
                    "--format=sarif-latest",
                    f"--output={results_file}",
                ],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )
            
            if result.returncode != 0:
                print(f"  WARNING: Query execution failed: {result.stderr}")
                return []
            
            # Parse SARIF output
            return self._parse_sarif(results_file, target_dir)
            
        except subprocess.TimeoutExpired:
            print(f"  WARNING: Query execution timed out after 10 minutes")
            return []
    
    def _parse_sarif(self, sarif_file: Path, target_dir: Path) -> List[Finding]:
        """Parse SARIF output to Finding objects."""
        if not sarif_file.exists():
            return []
        
        findings = []
        
        try:
            with open(sarif_file) as f:
                sarif = json.load(f)
            
            for run in sarif.get("runs", []):
                for result in run.get("results", []):
                    # Extract location
                    locations = result.get("locations", [])
                    if not locations:
                        continue
                    
                    loc = locations[0]["physicalLocation"]
                    file_path = loc["artifactLocation"]["uri"]
                    region = loc.get("region", {})
                    
                    # Extract CWE from rule
                    rule_id = result["ruleId"]
                    cwe = self._extract_cwe_from_rule(result, run)
                    
                    # Check if interprocedural
                    is_interprocedural = len(result.get("codeFlows", [])) > 0
                    
                    finding = Finding(
                        layer="codeql",
                        file_path=str(target_dir / file_path),
                        line_start=region.get("startLine", 1),
                        line_end=region.get("endLine", region.get("startLine", 1)),
                        rule_id=rule_id,
                        severity=result.get("level", "warning"),
                        message=result.get("message", {}).get("text", ""),
                        cwe=cwe,
                        confidence="high" if is_interprocedural else "medium",
                        metadata={
                            "interprocedural": is_interprocedural,
                            "codeql_rule": rule_id,
                        },
                    )
                    findings.append(finding)
        
        except Exception as e:
            print(f"  WARNING: Failed to parse SARIF: {e}")
        
        return findings
    
    def _extract_cwe_from_rule(self, result: Dict, run: Dict) -> Optional[str]:
        """Extract CWE from SARIF rule metadata."""
        rule_id = result["ruleId"]
        
        # Look up rule in run.tool.driver.rules
        rules = run.get("tool", {}).get("driver", {}).get("rules", [])
        for rule in rules:
            if rule["id"] == rule_id:
                # Check properties for CWE tags
                props = rule.get("properties", {})
                tags = props.get("tags", [])
                for tag in tags:
                    if tag.startswith("external/cwe/cwe-"):
                        return tag.replace("external/cwe/cwe-", "CWE-")
        
        return None


if __name__ == "__main__":
    # Test on current directory
    import sys
    analyzer = CodeQLAnalyzer()
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    findings = analyzer.analyze(target)
    
    print(f"\nFound {len(findings)} CodeQL findings:")
    for f in findings[:10]:  # Show first 10
        interproc = " [INTERPROC]" if f.metadata.get("interprocedural") else ""
        print(f"  {f.file_path}:{f.line_start} [{f.severity}] {f.rule_id}{interproc}")
