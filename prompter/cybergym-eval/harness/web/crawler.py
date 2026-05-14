"""Web crawler with form/parameter extraction.

Default backend: requests + BeautifulSoup (offline-friendly, no browser).
Optional Playwright backend for JS-heavy SPAs (auto-detected, falls back).
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urldefrag, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


@dataclass
class Endpoint:
    """A discovered HTTP endpoint with its parameters."""
    url: str
    method: str = "GET"
    params: Dict[str, str] = field(default_factory=dict)   # query / form fields
    headers: Dict[str, str] = field(default_factory=dict)
    content_type: str = ""
    source: str = "link"   # link | form | href-template

    def key(self) -> str:
        # Identity for deduplication (ignores values, keeps shape).
        p = urlparse(self.url)
        path = f"{p.scheme}://{p.netloc}{p.path}"
        param_keys = ",".join(sorted(self.params.keys()))
        return f"{self.method.upper()} {path}?{param_keys}"


@dataclass
class CrawlResult:
    base_url: str
    endpoints: List[Endpoint] = field(default_factory=list)
    visited: Set[str] = field(default_factory=set)
    errors: List[str] = field(default_factory=list)
    out_of_scope: int = 0


class WebCrawler:
    """Polite same-origin crawler.

    - Honors a max page count and depth.
    - Stays on the registered host (and optional extra hosts).
    - Extracts <a href>, <form>, plus any URL-looking strings in JSON bodies.
    """

    _URL_RE = re.compile(r"https?://[^\s\"'<>]+")

    def __init__(
        self,
        base_url: str,
        max_pages: int = 50,
        max_depth: int = 4,
        timeout: float = 5.0,
        cookies: Optional[Dict[str, str]] = None,
        extra_hosts: Optional[List[str]] = None,
        user_agent: str = "harness-web-crawler/1.0",
    ):
        self.base_url = base_url.rstrip("/")
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.timeout = timeout
        self.session = requests.Session()
        if cookies:
            self.session.cookies.update(cookies)
        self.session.headers["User-Agent"] = user_agent
        parsed = urlparse(self.base_url)
        self._allowed_hosts = {parsed.netloc} | set(extra_hosts or [])

    # ----- public API -----

    def crawl(self) -> CrawlResult:
        result = CrawlResult(base_url=self.base_url)
        queue: deque[Tuple[str, int]] = deque([(self.base_url, 0)])
        seen_keys: Set[str] = set()

        while queue and len(result.visited) < self.max_pages:
            url, depth = queue.popleft()
            url, _ = urldefrag(url)
            if url in result.visited:
                continue
            if not self._in_scope(url):
                result.out_of_scope += 1
                continue
            try:
                resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            except requests.RequestException as e:
                result.errors.append(f"GET {url}: {type(e).__name__}: {e}")
                continue
            result.visited.add(url)

            ep = self._endpoint_from_url(url, source="link")
            if ep.key() not in seen_keys:
                seen_keys.add(ep.key())
                result.endpoints.append(ep)

            if depth >= self.max_depth:
                continue

            ctype = resp.headers.get("Content-Type", "")
            body = resp.text or ""
            for link in self._extract_links(url, body, ctype):
                if link not in result.visited:
                    queue.append((link, depth + 1))
            for form in self._extract_forms(url, body, ctype):
                if form.key() not in seen_keys:
                    seen_keys.add(form.key())
                    result.endpoints.append(form)

        return result

    # ----- scope -----

    def _in_scope(self, url: str) -> bool:
        try:
            host = urlparse(url).netloc
        except Exception:
            return False
        return host in self._allowed_hosts

    # ----- extraction -----

    def _endpoint_from_url(self, url: str, source: str) -> Endpoint:
        p = urlparse(url)
        params = dict(parse_qsl(p.query, keep_blank_values=True))
        clean = urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
        return Endpoint(url=clean, method="GET", params=params, source=source)

    def _extract_links(self, base: str, body: str, ctype: str) -> List[str]:
        out: List[str] = []
        if "html" in ctype.lower() or "<html" in body.lower():
            soup = BeautifulSoup(body, "html.parser")
            for tag in soup.find_all(["a", "link", "script", "img", "iframe"]):
                href = tag.get("href") or tag.get("src")
                if href:
                    out.append(urljoin(base, href))
        # JSON / arbitrary body: regex hunt for URLs.
        for m in self._URL_RE.findall(body[:200_000]):
            out.append(m)
        return out

    def _extract_forms(self, base: str, body: str, ctype: str) -> List[Endpoint]:
        if "html" not in ctype.lower():
            return []
        eps: List[Endpoint] = []
        soup = BeautifulSoup(body, "html.parser")
        for form in soup.find_all("form"):
            action = urljoin(base, form.get("action") or base)
            method = (form.get("method") or "GET").upper()
            inputs: Dict[str, str] = {}
            for el in form.find_all(["input", "textarea", "select"]):
                name = el.get("name")
                if not name:
                    continue
                val = el.get("value") or "test"
                inputs[name] = val
            ct = "application/x-www-form-urlencoded"
            enctype = form.get("enctype")
            if enctype:
                ct = enctype
            eps.append(Endpoint(
                url=action, method=method, params=inputs,
                content_type=ct, source="form",
            ))
        return eps
