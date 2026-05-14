#!/usr/bin/env python3
"""Patch-diff mining: extract vulnerability patterns from git history."""
import json
import subprocess
import re
from typing import List, Dict, Any
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class PatchDiffFinding:
    """A potential incomplete fix found via git history."""
    commit_sha: str
    commit_message: str
    changed_function: str
    file_path: str
    suspected_cwe: str
    diff_excerpt: str
    confidence: float = 0.75  # Default priority for patch-diff findings


class PatchDiffMiner:
    """Mine git history for security-related patches."""
    
    SECURITY_KEYWORDS = [
        r'CVE',
        r'vuln',
        r'vulnerability',
        r'fix',
        r'security',
        r'overflow',
        r'uaf',
        r'use.after.free',
        r'oob',
        r'out.of.bounds',
        r'sanitizer',
        r'asan',
        r'ubsan',
        r'buffer',
        r'heap',
        r'stack',
        r'integer',
        r'crash',
    ]
    
    CWE_PATTERNS = {
        r'overflow|buffer': 'CWE-119',
        r'use.after.free|uaf|double.free': 'CWE-416',
        r'null.pointer|nullptr': 'CWE-476',
        r'integer|narrowing': 'CWE-190',
        r'format.string': 'CWE-134',
        r'injection|sql|command': 'CWE-89',
    }
    
    def __init__(self):
        pass
    
    def mine(self, target_dir: Path) -> List[PatchDiffFinding]:
        """Mine git history for security-related patches.
        
        Args:
            target_dir: Git repository root
            
        Returns:
            List of PatchDiffFinding objects
        """
        if not self._is_git_repo(target_dir):
            print("[PatchDiff] Not a git repository, skipping")
            return []
        
        findings = []
        
        # Get commit log
        commits = self._get_security_commits(target_dir)
        print(f"[PatchDiff] Found {len(commits)} security-related commits")
        
        # Analyze each commit
        for commit in commits:
            try:
                commit_findings = self._analyze_commit(target_dir, commit)
                findings.extend(commit_findings)
            except Exception as e:
                print(f"  WARNING: Failed to analyze commit {commit['sha'][:8]}: {e}")
        
        print(f"[PatchDiff] Extracted {len(findings)} potential incomplete fixes")
        
        return findings
    
    def _is_git_repo(self, target_dir: Path) -> bool:
        """Check if directory is a git repository."""
        git_dir = target_dir / ".git"
        return git_dir.exists()
    
    def _get_security_commits(self, target_dir: Path) -> List[Dict[str, str]]:
        """Get commits with security-related messages."""
        # Build grep pattern
        pattern = '|'.join(self.SECURITY_KEYWORDS)
        
        try:
            # Get commit log with messages
            result = subprocess.run(
                [
                    "git", "-C", str(target_dir),
                    "log",
                    "--format=%H|||%s|||%b",
                    f"--grep={pattern}",
                    "-i",  # Case insensitive
                    "--all",
                    "-n", "100",  # Limit to last 100 matching commits
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                print(f"  WARNING: git log failed: {result.stderr}")
                return []
            
            # Parse commits
            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('|||')
                if len(parts) >= 2:
                    commits.append({
                        "sha": parts[0],
                        "subject": parts[1],
                        "body": parts[2] if len(parts) > 2 else "",
                    })
            
            return commits
            
        except subprocess.TimeoutExpired:
            print("  WARNING: git log timed out")
            return []
    
    def _analyze_commit(self, target_dir: Path, commit: Dict[str, str]) -> List[PatchDiffFinding]:
        """Analyze a single commit for vulnerability patterns."""
        findings = []
        
        # Get diff
        diff = self._get_commit_diff(target_dir, commit["sha"])
        if not diff:
            return []
        
        # Extract changed functions
        changed_functions = self._extract_changed_functions(diff)
        
        # Infer CWE from commit message
        suspected_cwe = self._infer_cwe(commit["subject"] + " " + commit["body"])
        
        # Create findings for each changed function
        for func in changed_functions:
            finding = PatchDiffFinding(
                commit_sha=commit["sha"],
                commit_message=commit["subject"],
                changed_function=func["function"],
                file_path=func["file"],
                suspected_cwe=suspected_cwe,
                diff_excerpt=func["diff_excerpt"],
            )
            findings.append(finding)
        
        return findings
    
    def _get_commit_diff(self, target_dir: Path, sha: str) -> str:
        """Get diff for a commit."""
        try:
            result = subprocess.run(
                [
                    "git", "-C", str(target_dir),
                    "show",
                    sha,
                    "--format=",  # No commit message
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                return ""
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            return ""
    
    def _extract_changed_functions(self, diff: str) -> List[Dict[str, str]]:
        """Extract function names from diff."""
        functions = []
        
        current_file = ""
        current_func = ""
        diff_lines = []
        
        for line in diff.split('\n'):
            # Track current file
            if line.startswith('--- a/'):
                current_file = line[6:]
            elif line.startswith('+++ b/'):
                current_file = line[6:]
            
            # Extract function context from diff
            if line.startswith('@@'):
                # Format: @@ -10,7 +10,7 @@ function_name
                match = re.search(r'@@.*@@ (.+)', line)
                if match:
                    current_func = match.group(1).strip()
                    diff_lines = []
            
            # Collect diff lines
            if line.startswith(('+', '-')) and not line.startswith(('+++', '---')):
                diff_lines.append(line)
            
            # Save function on next @@ or end
            if line.startswith('@@') and current_func and diff_lines:
                excerpt = '\n'.join(diff_lines[:10])  # First 10 lines
                functions.append({
                    "file": current_file,
                    "function": current_func,
                    "diff_excerpt": excerpt,
                })
                diff_lines = []
        
        return functions
    
    def _infer_cwe(self, text: str) -> str:
        """Infer CWE from commit message text."""
        text_lower = text.lower()
        
        for pattern, cwe in self.CWE_PATTERNS.items():
            if re.search(pattern, text_lower):
                return cwe
        
        return "CWE-unknown"


if __name__ == "__main__":
    # Test on current directory
    import sys
    miner = PatchDiffMiner()
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    findings = miner.mine(target)
    
    print(f"\nFound {len(findings)} patch-diff findings:")
    for f in findings[:10]:  # Show first 10
        print(f"  {f.commit_sha[:8]} {f.file_path} {f.changed_function} [{f.suspected_cwe}]")
