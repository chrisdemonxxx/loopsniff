#!/usr/bin/env python3
"""Layer 4: Custom AST rules for C/C++.

Lightweight Python-based AST walker for common vulnerability patterns.
Uses tree-sitter for parsing.
"""
from typing import List, Dict, Any
from pathlib import Path
from .layer1_semgrep import Finding

try:
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


class CustomASTAnalyzer:
    """Custom AST rules using tree-sitter."""
    
    def __init__(self):
        self.parser = None
        if TREE_SITTER_AVAILABLE:
            try:
                # Try to load C language
                self._init_parser()
            except Exception as e:
                print(f"WARNING: Failed to init tree-sitter parser: {e}")
    
    def _init_parser(self):
        """Initialize tree-sitter parser for C."""
        # Note: This requires tree-sitter-c to be built
        # For now, just mark as unavailable if build fails
        pass
    
    def analyze(self, target_dir: Path) -> List[Finding]:
        """Run custom AST rules on C/C++ files.
        
        Args:
            target_dir: Path to analyze
            
        Returns:
            List of Finding objects
        """
        if not TREE_SITTER_AVAILABLE:
            print("WARNING: tree-sitter not installed, skipping Layer 4")
            print("Install: pip install tree-sitter tree-sitter-c")
            return []
        
        # Find C/C++ files
        c_files = list(target_dir.rglob("*.c")) + list(target_dir.rglob("*.cpp"))
        if not c_files:
            print("[CustomAST] No C/C++ files found")
            return []
        
        findings = []
        
        # Run rules on each file
        for file_path in c_files:
            try:
                file_findings = self._analyze_file(file_path)
                findings.extend(file_findings)
            except Exception as e:
                print(f"  WARNING: Failed to analyze {file_path}: {e}")
        
        print(f"[CustomAST] Found {len(findings)} findings")
        
        return findings
    
    def _analyze_file(self, file_path: Path) -> List[Finding]:
        """Analyze a single file with all rules."""
        findings = []
        
        try:
            with open(file_path, 'rb') as f:
                source = f.read()
        except Exception as e:
            print(f"    WARNING: Could not read {file_path}: {e}")
            return []
        
        # For now, use regex-based simple patterns
        # (Full tree-sitter requires language builds which may not be available)
        findings.extend(self._check_format_string(file_path, source))
        findings.extend(self._check_integer_narrowing(file_path, source))
        findings.extend(self._check_unchecked_malloc(file_path, source))
        
        return findings
    
    def _check_format_string(self, file_path: Path, source: bytes) -> List[Finding]:
        """Check for non-literal format strings in printf-family calls."""
        findings = []
        
        # Simple regex patterns for common cases
        import re
        patterns = [
            (r'printf\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*[,)]', "printf with variable format"),
            (r'fprintf\s*\([^,]+,\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*[,)]', "fprintf with variable format"),
            (r'sprintf\s*\([^,]+,\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*[,)]', "sprintf with variable format"),
        ]
        
        source_str = source.decode('utf-8', errors='ignore')
        lines = source_str.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for pattern, desc in patterns:
                if re.search(pattern, line):
                    findings.append(Finding(
                        layer="custom_ast",
                        file_path=str(file_path),
                        line_start=line_num,
                        line_end=line_num,
                        rule_id="custom.format_string",
                        severity="high",
                        message=desc,
                        cwe="CWE-134",
                        confidence="medium",
                        metadata={"pattern": pattern},
                    ))
        
        return findings
    
    def _check_integer_narrowing(self, file_path: Path, source: bytes) -> List[Finding]:
        """Check for narrowing casts of external input."""
        findings = []
        
        # Look for patterns like: short x = (short)read(...)
        import re
        source_str = source.decode('utf-8', errors='ignore')
        lines = source_str.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Simple heuristic: cast to smaller type near read/recv
            if re.search(r'\(\s*(char|short|int8_t|int16_t)\s*\)', line):
                if re.search(r'(read|recv|fread|scanf|getc)', line):
                    findings.append(Finding(
                        layer="custom_ast",
                        file_path=str(file_path),
                        line_start=line_num,
                        line_end=line_num,
                        rule_id="custom.integer_narrowing",
                        severity="medium",
                        message="Integer narrowing cast of external input",
                        cwe="CWE-197",
                        confidence="low",
                        metadata={"line": line.strip()},
                    ))
        
        return findings
    
    def _check_unchecked_malloc(self, file_path: Path, source: bytes) -> List[Finding]:
        """Check for malloc() without bounds check on size."""
        findings = []
        
        import re
        source_str = source.decode('utf-8', errors='ignore')
        lines = source_str.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # malloc(n) where n involves arithmetic
            if 'malloc' in line and any(op in line for op in ['+', '-', '*', '/']):
                # Check if size comes from external input
                if any(func in line for func in ['read', 'recv', 'fread', 'scanf', 'atoi']):
                    findings.append(Finding(
                        layer="custom_ast",
                        file_path=str(file_path),
                        line_start=line_num,
                        line_end=line_num,
                        rule_id="custom.unchecked_alloc",
                        severity="high",
                        message="Allocation size derived from external input without validation",
                        cwe="CWE-789",
                        confidence="low",
                        metadata={"line": line.strip()},
                    ))
        
        return findings


if __name__ == "__main__":
    # Test on current directory
    import sys
    analyzer = CustomASTAnalyzer()
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    findings = analyzer.analyze(target)
    
    print(f"\nFound {len(findings)} custom AST findings:")
    for f in findings[:10]:  # Show first 10
        print(f"  {f.file_path}:{f.line_start} [{f.severity}] {f.rule_id}")
