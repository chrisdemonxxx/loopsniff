"""Stage 4: Web pipeline (w68).

Crawler → parameter extraction → active probes → IDOR → Findings.

Findings emitted use the same schema as static_analysis.layer1_semgrep.Finding
(layer="web") so they flow through the existing Verifier + ReportWriter.
"""
from .crawler import WebCrawler, CrawlResult, Endpoint
from .probes import (
    ProbeResult,
    SQLiProbe,
    SSRFProbe,
    XXEProbe,
    SSTIProbe,
    PathTraversalProbe,
    CommandInjectionProbe,
    OpenRedirectProbe,
    ALL_PROBES,
)
from .idor import IDORDetector
from .orchestrator import WebPipeline, WebPipelineStats

__all__ = [
    "WebCrawler", "CrawlResult", "Endpoint",
    "ProbeResult",
    "SQLiProbe", "SSRFProbe", "XXEProbe", "SSTIProbe",
    "PathTraversalProbe", "CommandInjectionProbe", "OpenRedirectProbe",
    "ALL_PROBES",
    "IDORDetector",
    "WebPipeline", "WebPipelineStats",
]
