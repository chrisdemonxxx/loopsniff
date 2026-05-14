"""Subagent framework for vulnerability finding enrichment.

Subagents consume findings from harness/static_analysis/dispatch_queues/
and enrich them with LLM-driven analysis: severity assessment, exploit
path reasoning, PoC stub generation, and false-positive likelihood.

Module map:
- base.py            BaseSubagent + EnrichedFinding schema
- llm_client.py      Wrapper around Baseten model q415dj1
- sa1_memory.py      CWE-119/120/122/125/416/476/415/401
- sa2_integer.py     CWE-190/191/369/197/680
- sa3_injection.py   CWE-89/78/611/918/639/134/73
- sa4_crypto.py      CWE-326/327/330/798/287/311
- orchestrator.py    Async parallel dispatch across all 4 agents
"""

from .base import BaseSubagent, EnrichedFinding, SubagentResult
from .llm_client import LLMClient, MockLLMClient
from .sa1_memory import SA1Memory
from .sa2_integer import SA2Integer
from .sa3_injection import SA3Injection
from .sa4_crypto import SA4Crypto
from .sa5_interproc import SA5Interprocedural
from .verifier import Verifier, VerificationResult
from .orchestrator import SubagentOrchestrator

__all__ = [
    "BaseSubagent",
    "EnrichedFinding",
    "SubagentResult",
    "LLMClient",
    "MockLLMClient",
    "SA1Memory",
    "SA2Integer",
    "SA3Injection",
    "SA4Crypto",
    "SA5Interprocedural",
    "Verifier",
    "VerificationResult",
    "SubagentOrchestrator",
]
