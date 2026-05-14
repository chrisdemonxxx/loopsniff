#!/usr/bin/env python3
"""Subagent dispatcher: route findings to specialized agents."""
import json
from typing import List, Dict, Any
from pathlib import Path
from collections import defaultdict


class SubagentDispatcher:
    """Route findings to specialized subagents based on CWE class."""
    
    # CWE → Subagent mapping
    CWE_TO_AGENT = {
        # SA-1: Memory bugs
        "CWE-119": "sa1",  # Buffer overflow
        "CWE-120": "sa1",  # Classic buffer overflow
        "CWE-122": "sa1",  # Heap overflow
        "CWE-125": "sa1",  # Out-of-bounds read
        "CWE-416": "sa1",  # Use after free
        "CWE-476": "sa1",  # NULL pointer dereference
        "CWE-415": "sa1",  # Double free
        "CWE-401": "sa1",  # Memory leak
        
        # SA-2: Integer bugs
        "CWE-190": "sa2",  # Integer overflow
        "CWE-191": "sa2",  # Integer underflow
        "CWE-369": "sa2",  # Divide by zero
        "CWE-197": "sa2",  # Integer narrowing
        "CWE-680": "sa2",  # Integer overflow to buffer overflow
        
        # SA-3: Injection bugs
        "CWE-89": "sa3",   # SQL injection
        "CWE-78": "sa3",   # OS command injection
        "CWE-611": "sa3",  # XXE
        "CWE-918": "sa3",  # SSRF
        "CWE-639": "sa3",  # Insecure direct object reference
        "CWE-134": "sa3",  # Format string
        "CWE-73": "sa3",   # Path traversal
        
        # SA-4: Crypto bugs
        "CWE-326": "sa4",  # Weak encryption
        "CWE-327": "sa4",  # Broken crypto
        "CWE-330": "sa4",  # Weak random
        "CWE-798": "sa4",  # Hard-coded credentials
        "CWE-287": "sa4",  # Improper authentication
        "CWE-311": "sa4",  # Missing encryption
    }
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("dispatch_queues")
        self.output_dir.mkdir(exist_ok=True)
    
    def dispatch(self, ranked_findings: List[Dict[str, Any]]) -> Dict[str, int]:
        """Route findings to subagent queues.
        
        Args:
            ranked_findings: Output from TriageEngine.triage()
            
        Returns:
            Dict of {agent_id: count} for summary
        """
        # Filter to actionable findings only
        actionable = [f for f in ranked_findings if f["actionable"]]
        
        # Group by agent
        agent_queues = defaultdict(list)
        interprocedural_queue = []
        
        for ranked in actionable:
            finding = ranked["finding"]
            priority = ranked["priority"]
            
            # Check if interprocedural (goes to SA-5)
            if finding.get("metadata", {}).get("interprocedural"):
                interprocedural_queue.append({
                    "finding": finding,
                    "priority": priority,
                })
            
            # Route by CWE
            cwe = finding.get("cwe", "")
            agent_id = self.CWE_TO_AGENT.get(cwe, "sa1")  # Default to SA-1
            
            agent_queues[agent_id].append({
                "finding": finding,
                "priority": priority,
            })
        
        # Add interprocedural to SA-5
        if interprocedural_queue:
            agent_queues["sa5"] = interprocedural_queue
        
        # Write queues to files
        counts = {}
        for agent_id, queue in agent_queues.items():
            # Sort by priority
            queue.sort(key=lambda x: x["priority"], reverse=True)
            
            # Write to file
            queue_file = self.output_dir / f"{agent_id}.jsonl"
            with open(queue_file, 'w') as f:
                for item in queue:
                    f.write(json.dumps(item) + '\n')
            
            counts[agent_id] = len(queue)
            print(f"[Dispatch] {agent_id}: {len(queue)} findings → {queue_file}")
        
        # Summary
        total = sum(counts.values())
        print(f"[Dispatch] Total dispatched: {total} findings across {len(counts)} agents")
        
        return counts
    
    def get_queue(self, agent_id: str) -> List[Dict[str, Any]]:
        """Load a specific agent's queue.
        
        Args:
            agent_id: Agent ID (sa1, sa2, sa3, sa4, sa5)
            
        Returns:
            List of {finding, priority} dicts
        """
        queue_file = self.output_dir / f"{agent_id}.jsonl"
        if not queue_file.exists():
            return []
        
        queue = []
        with open(queue_file) as f:
            for line in f:
                queue.append(json.loads(line))
        
        return queue
    
    def clear_queues(self):
        """Clear all dispatch queues."""
        for queue_file in self.output_dir.glob("*.jsonl"):
            queue_file.unlink()
        print(f"[Dispatch] Cleared all queues in {self.output_dir}")


if __name__ == "__main__":
    # Test with sample findings
    from .layer1_semgrep import Finding
    from .triage import TriageEngine
    
    findings = [
        Finding(
            layer="joern",
            file_path="test.c",
            line_start=10,
            line_end=10,
            rule_id="joern.use_after_free",
            severity="high",
            message="Use after free",
            cwe="CWE-416",
            confidence="high",
        ),
        Finding(
            layer="codeql",
            file_path="test.c",
            line_start=20,
            line_end=20,
            rule_id="codeql.sql_injection",
            severity="high",
            message="SQL injection",
            cwe="CWE-89",
            confidence="high",
            metadata={"interprocedural": True},
        ),
    ]
    
    # Triage
    engine = TriageEngine()
    ranked = engine.triage(findings)
    
    # Dispatch
    dispatcher = SubagentDispatcher()
    counts = dispatcher.dispatch(ranked)
    
    print(f"\nDispatched to {len(counts)} agents:")
    for agent, count in counts.items():
        print(f"  {agent}: {count}")
