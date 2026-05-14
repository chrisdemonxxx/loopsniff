"""Glue: crawl → probe → IDOR → emit Findings → write dispatch queue.

Findings are written in the format the existing static_analysis dispatch
+ subagents + verifier + reports pipeline understands. Web findings are
routed to subagent 'sa3' (the application-logic / behavioral agent) by
default.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Type

import requests

from .crawler import CrawlResult, Endpoint, WebCrawler
from .idor import IDORDetector
from .probes import ALL_PROBES, ProbeResult, _BaseProbe


@dataclass
class WebPipelineStats:
    base_url: str
    pages_visited: int = 0
    endpoints_discovered: int = 0
    probes_run: int = 0
    findings_total: int = 0
    findings_by_probe: Dict[str, int] = field(default_factory=dict)
    crawl_errors: List[str] = field(default_factory=list)
    elapsed_s: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


class WebPipeline:
    def __init__(
        self,
        base_url: str,
        out_dir: Path,
        max_pages: int = 30,
        max_depth: int = 3,
        cookies: Optional[Dict[str, str]] = None,
        probes: Optional[List[Type[_BaseProbe]]] = None,
        idor: Optional[IDORDetector] = None,
        timeout: float = 5.0,
        dispatch_agent: str = "sa3",
    ):
        self.base_url = base_url
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.cookies = cookies
        self.probe_classes = probes or ALL_PROBES
        self.idor = idor
        self.timeout = timeout
        self.dispatch_agent = dispatch_agent

    def run(self) -> WebPipelineStats:
        t0 = time.time()
        stats = WebPipelineStats(base_url=self.base_url)

        crawler = WebCrawler(
            base_url=self.base_url,
            max_pages=self.max_pages,
            max_depth=self.max_depth,
            cookies=self.cookies,
            timeout=self.timeout,
        )
        crawl: CrawlResult = crawler.crawl()
        stats.pages_visited = len(crawl.visited)
        stats.endpoints_discovered = len(crawl.endpoints)
        stats.crawl_errors = crawl.errors[:20]
        (self.out_dir / "crawl.json").write_text(json.dumps({
            "base_url": crawl.base_url,
            "visited": sorted(crawl.visited),
            "endpoints": [asdict(e) for e in crawl.endpoints],
            "out_of_scope_count": crawl.out_of_scope,
            "errors": crawl.errors,
        }, indent=2))

        # Run probes.
        sess = requests.Session()
        if self.cookies:
            sess.cookies.update(self.cookies)
        all_results: List[ProbeResult] = []
        for cls in self.probe_classes:
            probe = cls(session=sess, timeout=self.timeout)
            for ep in crawl.endpoints:
                stats.probes_run += 1
                hits = probe.run(ep)
                all_results.extend(hits)

        # IDOR (optional).
        if self.idor is not None:
            all_results.extend(self.idor.scan(crawl.endpoints))

        # Tally + persist.
        for r in all_results:
            stats.findings_by_probe[r.probe] = stats.findings_by_probe.get(r.probe, 0) + 1
        stats.findings_total = len(all_results)

        with (self.out_dir / "web_findings.jsonl").open("w") as fh:
            for r in all_results:
                fh.write(json.dumps(r.to_finding_dict()) + "\n")

        # Emit a dispatch-queue entry per finding so the rest of the
        # pipeline (subagents → verifier → reports) can consume it.
        dispatch_dir = self.out_dir / "dispatch_queues"
        dispatch_dir.mkdir(exist_ok=True)
        with (dispatch_dir / f"{self.dispatch_agent}.jsonl").open("a") as fh:
            for r in all_results:
                priority = min(0.5 + r.confidence / 2.0, 0.99)
                fh.write(json.dumps({"finding": r.to_finding_dict(),
                                     "priority": priority}) + "\n")

        stats.elapsed_s = round(time.time() - t0, 3)
        (self.out_dir / "web_pipeline_stats.json").write_text(
            json.dumps(stats.to_dict(), indent=2))
        return stats


# CLI entry-point.
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-pages", type=int, default=30)
    ap.add_argument("--max-depth", type=int, default=3)
    ap.add_argument("--cookie", action="append", default=[],
                    help="name=value (repeatable)")
    args = ap.parse_args()
    cookies = {}
    for c in args.cookie:
        if "=" in c:
            k, v = c.split("=", 1); cookies[k] = v
    s = WebPipeline(args.base_url, Path(args.out),
                    max_pages=args.max_pages, max_depth=args.max_depth,
                    cookies=cookies or None).run()
    print(json.dumps(s.to_dict(), indent=2))
