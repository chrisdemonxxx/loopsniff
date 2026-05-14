"""Static analysis pipeline for vulnerability detection.

This module implements the 4-layer static analysis stack:
- Layer 1: semgrep (security-audit ruleset)
- Layer 2: CodeQL (security-and-quality suite)
- Layer 3: Joern (CFG/PDG analysis for C/C++)
- Layer 4: Custom AST rules (lightweight Python walker)

Plus patch-diff mining and RL-based triage.
"""
from .layer1_semgrep import SemgrepAnalyzer
from .layer2_codeql import CodeQLAnalyzer
from .layer3_joern import JoernAnalyzer
from .layer4_custom_ast import CustomASTAnalyzer
from .patch_diff_miner import PatchDiffMiner
from .triage import TriageEngine
from .dispatch import SubagentDispatcher

__all__ = [
    "SemgrepAnalyzer",
    "CodeQLAnalyzer",
    "JoernAnalyzer",
    "CustomASTAnalyzer",
    "PatchDiffMiner",
    "TriageEngine",
    "SubagentDispatcher",
]
