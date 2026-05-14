"""Subagent orchestrator: parallel dispatch across SA-1..SA-4."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .base import BaseSubagent, EnrichedFinding, SubagentResult
from .llm_client import LLMClient, MockLLMClient, estimate_cost_usd
from .sa1_memory import SA1Memory
from .sa2_integer import SA2Integer
from .sa3_injection import SA3Injection
from .sa4_crypto import SA4Crypto
from .sa5_interproc import SA5Interprocedural


AGENT_REGISTRY: Dict[str, Type[BaseSubagent]] = {
    "sa1": SA1Memory,
    "sa2": SA2Integer,
    "sa3": SA3Injection,
    "sa4": SA4Crypto,
    "sa5": SA5Interprocedural,
}


class SubagentOrchestrator:
    """Run dispatch queues through their assigned subagents in parallel."""

    def __init__(self, llm_client=None, model_name: str = "q415dj1",
                 budget_usd: float = 50.0, max_findings_per_agent: int = 25,
                 output_dir: Optional[Path] = None):
        self.llm = llm_client or MockLLMClient()
        self.model_name = model_name
        self.budget_usd = budget_usd
        self.max_findings_per_agent = max_findings_per_agent
        self.output_dir = Path(output_dir) if output_dir else Path("subagent_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._spend_usd = 0.0

    def _build_agent(self, agent_id: str) -> BaseSubagent:
        cls = AGENT_REGISTRY.get(agent_id)
        if cls is None:
            raise ValueError(f"Unknown agent_id: {agent_id}")
        return cls(self.llm, model_name=self.model_name)

    def _run_one_agent(self, agent_id: str, queue: List[Dict[str, Any]]) -> SubagentResult:
        agent = self._build_agent(agent_id)
        enriched: List[EnrichedFinding] = []
        errors = 0
        spent = 0.0
        t0 = time.time()
        capped = queue[: self.max_findings_per_agent]
        for item in capped:
            if self._spend_usd + spent >= self.budget_usd:
                enriched.append(EnrichedFinding.error_record(
                    agent_id, item, f"budget_exceeded:{self.budget_usd}"))
                errors += 1
                continue
            rec = agent.analyze(item)
            cost = estimate_cost_usd(rec.tokens_in, rec.tokens_out)
            spent += cost
            enriched.append(rec)
            if rec.error is not None:
                errors += 1
        elapsed = time.time() - t0
        return SubagentResult(
            agent_id=agent_id,
            total=len(capped),
            enriched=enriched,
            errors=errors,
            elapsed_s=elapsed,
            estimated_cost_usd=spent,
        )

    def run_from_dispatch_dir(self, dispatch_dir: Path,
                              agents: Optional[List[str]] = None) -> Dict[str, SubagentResult]:
        dispatch_dir = Path(dispatch_dir)
        agents = agents or list(AGENT_REGISTRY.keys())
        queues: Dict[str, List[Dict[str, Any]]] = {}
        for aid in agents:
            qf = dispatch_dir / f"{aid}.jsonl"
            if not qf.is_file():
                queues[aid] = []
                continue
            items = []
            for line in qf.read_text(errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            queues[aid] = items
        return self.run(queues)

    def run(self, queues: Dict[str, List[Dict[str, Any]]]) -> Dict[str, SubagentResult]:
        results: Dict[str, SubagentResult] = {}
        active = {aid: q for aid, q in queues.items() if q}
        if not active:
            print("[Orchestrator] No findings to process in any queue.")
            return results

        with ThreadPoolExecutor(max_workers=max(len(active), 1)) as pool:
            future_to_aid = {pool.submit(self._run_one_agent, aid, q): aid
                             for aid, q in active.items()}
            for fut in as_completed(future_to_aid):
                aid = future_to_aid[fut]
                try:
                    res = fut.result()
                except Exception as e:
                    print(f"[Orchestrator] {aid} crashed: {e}")
                    continue
                self._spend_usd += res.estimated_cost_usd
                results[aid] = res
                self._write_results(res)
                print(f"[Orchestrator] {aid}: {res.to_summary()}")

        for aid in queues:
            if aid not in results:
                results[aid] = SubagentResult(agent_id=aid, total=0, enriched=[],
                                              errors=0, elapsed_s=0.0, estimated_cost_usd=0.0)
        return results

    def _write_results(self, res: SubagentResult) -> None:
        out = self.output_dir / f"{res.agent_id}_enriched.jsonl"
        with out.open("w") as f:
            for e in res.enriched:
                f.write(e.to_json() + "\n")
        summary = self.output_dir / f"{res.agent_id}_summary.json"
        summary.write_text(json.dumps(res.to_summary(), indent=2))

    @property
    def total_spend_usd(self) -> float:
        return self._spend_usd


def main():
    import argparse
    p = argparse.ArgumentParser(description="Run SA-1..SA-4 subagents over dispatch queues.")
    p.add_argument("--dispatch-dir", required=True, type=Path)
    p.add_argument("--output-dir", default=Path("subagent_results"), type=Path)
    p.add_argument("--mock", action="store_true", help="Use MockLLMClient (free, no Baseten).")
    p.add_argument("--budget-usd", type=float, default=50.0)
    p.add_argument("--max-per-agent", type=int, default=25)
    p.add_argument("--agents", default="sa1,sa2,sa3,sa4,sa5")
    args = p.parse_args()

    client = MockLLMClient() if args.mock else LLMClient()
    orch = SubagentOrchestrator(
        llm_client=client,
        budget_usd=args.budget_usd,
        max_findings_per_agent=args.max_per_agent,
        output_dir=args.output_dir,
    )
    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    results = orch.run_from_dispatch_dir(args.dispatch_dir, agents=agents)

    print("\n=== Orchestrator summary ===")
    for aid, res in results.items():
        print(json.dumps(res.to_summary(), indent=2))
    print(f"Total estimated spend: ${orch.total_spend_usd:.4f}")


if __name__ == "__main__":
    main()
