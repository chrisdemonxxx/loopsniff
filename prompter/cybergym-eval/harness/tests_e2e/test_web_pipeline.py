"""End-to-end test for harness.web (w68).

Spins up a deliberately-vulnerable in-process HTTP server, runs the full
WebPipeline against it, and asserts each probe class fires.
"""
from __future__ import annotations

import json
import socket
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.web import (
    WebPipeline, WebCrawler, SQLiProbe, SSRFProbe, SSTIProbe,
    PathTraversalProbe, CommandInjectionProbe, OpenRedirectProbe,
    XXEProbe, IDORDetector,
)


# ---------- vulnerable test server ----------

INDEX_HTML = """<html><body>
<h1>vuln app</h1>
<a href="/search?q=cat">search</a>
<a href="/fetch?url=http://example.com">fetch</a>
<a href="/render?name=guest">render</a>
<a href="/file?path=hello.txt">file</a>
<a href="/ping?host=127.0.0.1">ping</a>
<a href="/redir?next=/home">redir</a>
<form action="/login" method="POST">
  <input name="user"><input name="pass" type="password">
</form>
</body></html>
"""

ETC_PASSWD = "root:x:0:0:root:/root:/bin/bash\nuser:x:1000:1000::/home/user:/bin/bash\n"


class VulnHandler(BaseHTTPRequestHandler):
    def log_message(self, *a, **k): pass

    def _w(self, code, body, ctype="text/html", extra_headers=None):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}
        if u.path in ("/", "/index.html"):
            return self._w(200, INDEX_HTML)
        if u.path == "/search":
            term = q.get("q", "")
            if "'" in term or '"' in term:
                return self._w(500, f"You have an error in your SQL syntax near '{term}'")
            return self._w(200, f"<p>results for {term}</p>")
        if u.path == "/fetch":
            url = q.get("url", "")
            if url.startswith("file://"):
                return self._w(200, ETC_PASSWD, "text/plain")
            if "127.0.0.1" in url or "localhost" in url:
                return self._w(502, "ECONNREFUSED while connecting to internal host")
            return self._w(200, "<p>fetched ok</p>")
        if u.path == "/render":
            name = q.get("name", "guest")
            if "{{" in name and "}}" in name:
                # naive eval of {{a*b}}
                import re as _re
                def _ev(m):
                    try: return str(eval(m.group(1), {"__builtins__": {}}))
                    except Exception: return m.group(0)
                name = _re.sub(r"\{\{(.+?)\}\}", _ev, name)
            return self._w(200, f"<p>Hello {name}</p>")
        if u.path == "/file":
            p = q.get("path", "")
            if "etc/passwd" in p or p.endswith("/passwd"):
                return self._w(200, ETC_PASSWD, "text/plain")
            return self._w(200, "hello world", "text/plain")
        if u.path == "/ping":
            host = q.get("host", "")
            import re as _re
            m = _re.search(r"echo\s+(\S+)", host)
            if m:
                return self._w(200, f"PING result: {m.group(1)}\n", "text/plain")
            return self._w(200, "pong", "text/plain")
        if u.path == "/redir":
            nxt = q.get("next", "/")
            return self._w(302, "", "text/html", {"Location": nxt})
        if u.path == "/secret":
            # only authorized for cookie sid=alice; but we'll *also* serve to anon (the IDOR bug).
            return self._w(200, "TOP SECRET DOCUMENT BODY " * 30, "text/plain")
        return self._w(404, "not found")

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(ln).decode("utf-8", "replace")
        ct = self.headers.get("Content-Type", "")
        if "xml" in ct.lower():
            # Naively process external entity.
            if "/etc/passwd" in body and "ENTITY" in body:
                return self._w(200, ETC_PASSWD, "text/plain")
            if "nonexistent_xxe_canary" in body and "ENTITY" in body:
                return self._w(500, "no such file or directory: /nonexistent_xxe_canary")
        return self._w(200, f"<p>posted {len(body)} bytes</p>")


def _free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p


def _start_server():
    port = _free_port()
    srv = HTTPServer(("127.0.0.1", port), VulnHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)
    return srv, port


# ---------------- tests ----------------

def test_crawler_discovers_endpoints_and_form():
    srv, port = _start_server()
    try:
        r = WebCrawler(f"http://127.0.0.1:{port}", max_pages=20, max_depth=3).crawl()
        urls = {e.url for e in r.endpoints}
        assert any("/search" in u for u in urls)
        assert any("/login" in u for u in urls)
        assert any(e.method == "POST" and e.source == "form" for e in r.endpoints)
        # form fields extracted
        login = [e for e in r.endpoints if "/login" in e.url][0]
        assert "user" in login.params and "pass" in login.params
        print(f"  test_crawler_discovers_endpoints_and_form: OK ({len(r.endpoints)} eps)")
    finally:
        srv.shutdown()


def test_pipeline_finds_all_probe_classes():
    srv, port = _start_server()
    try:
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "out"
            stats = WebPipeline(
                base_url=f"http://127.0.0.1:{port}",
                out_dir=out, max_pages=20, max_depth=3,
                probes=[SQLiProbe, SSRFProbe, SSTIProbe, PathTraversalProbe,
                        CommandInjectionProbe, OpenRedirectProbe],
            ).run()
            assert stats.findings_total >= 6, stats.findings_by_probe
            for expected in ["sqli", "ssrf", "ssti", "path_traversal",
                             "cmd_injection", "open_redirect"]:
                assert expected in stats.findings_by_probe, \
                    f"missing {expected}: {stats.findings_by_probe}"

            # Findings file exists and entries match Finding schema.
            lines = [l for l in (out / "web_findings.jsonl").read_text().splitlines() if l.strip()]
            assert lines
            sample = json.loads(lines[0])
            for k in ["layer", "file_path", "rule_id", "severity", "cwe",
                      "confidence", "metadata", "message"]:
                assert k in sample, k
            assert sample["layer"] == "web"

            # Dispatch queue written.
            dq = out / "dispatch_queues" / "sa3.jsonl"
            assert dq.is_file() and dq.stat().st_size > 0
            entry = json.loads(dq.read_text().splitlines()[0])
            assert "finding" in entry and "priority" in entry

            # Stats serializable.
            parsed = json.loads((out / "web_pipeline_stats.json").read_text())
            assert parsed["findings_total"] == stats.findings_total
            print(f"  test_pipeline_finds_all_probe_classes: OK "
                  f"(findings={stats.findings_total}, by_probe={stats.findings_by_probe})")
    finally:
        srv.shutdown()


def test_xxe_probe_fires_when_xml_accepted():
    srv, port = _start_server()
    try:
        from harness.web.crawler import Endpoint
        ep = Endpoint(url=f"http://127.0.0.1:{port}/login", method="POST",
                      params={"body": "<x/>"}, content_type="application/xml")
        hits = XXEProbe().run(ep)
        assert hits, "XXE probe did not fire on xml endpoint"
        assert hits[0].cwe == "CWE-611"
        print(f"  test_xxe_probe_fires_when_xml_accepted: OK ({len(hits)} hits)")
    finally:
        srv.shutdown()


def test_idor_detects_unauth_access():
    import requests
    srv, port = _start_server()
    try:
        sa = requests.Session(); sa.cookies.set("sid", "alice")
        from harness.web.crawler import Endpoint
        eps = [Endpoint(url=f"http://127.0.0.1:{port}/secret", method="GET", params={})]
        det = IDORDetector(user_a_session=sa)
        hits = det.scan(eps)
        assert hits, "IDOR not flagged for /secret"
        assert hits[0].cwe == "CWE-639"
        print(f"  test_idor_detects_unauth_access: OK")
    finally:
        srv.shutdown()


def main():
    print("=== w68 web pipeline tests ===")
    test_crawler_discovers_endpoints_and_form()
    test_pipeline_finds_all_probe_classes()
    test_xxe_probe_fires_when_xml_accepted()
    test_idor_detects_unauth_access()
    print("=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
