"""LLM client wrappers.

LLMClient   — calls deployed Baseten model q415dj1 via OpenAI-compatible /v1/chat/completions
MockLLMClient — offline scriptable client used in tests + dry-runs (free)

Both expose: chat(messages, model=..., temperature=..., max_tokens=...) -> dict
with keys: text, model, tokens_in, tokens_out, raw
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import urllib.request
import urllib.error


def _load_baseten_api_key() -> Optional[str]:
    """Load API key from env, then ~/.trussrc."""
    key = os.environ.get("BASETEN_API_KEY")
    if key:
        return key
    rc = Path.home() / ".trussrc"
    if rc.is_file():
        for line in rc.read_text().splitlines():
            line = line.strip()
            if line.startswith("api_key"):
                _, _, value = line.partition("=")
                value = value.strip().strip('"').strip("'")
                if value:
                    return value
    return None


# Pricing assumption for q415dj1 (4xH100 dedicated). Adjust if Baseten dashboard differs.
# Conservative: $0.0015 / 1K input tokens, $0.006 / 1K output tokens
_DEFAULT_PRICE_IN_PER_1K = float(os.environ.get("LLM_PRICE_IN_PER_1K", "0.0015"))
_DEFAULT_PRICE_OUT_PER_1K = float(os.environ.get("LLM_PRICE_OUT_PER_1K", "0.006"))


def estimate_cost_usd(tokens_in: int, tokens_out: int,
                      price_in: float = _DEFAULT_PRICE_IN_PER_1K,
                      price_out: float = _DEFAULT_PRICE_OUT_PER_1K) -> float:
    return (tokens_in / 1000.0) * price_in + (tokens_out / 1000.0) * price_out


class LLMClient:
    """Real Baseten client for the deployed SFT model."""

    # NOTE: As of 2026-05-14, the SFT-tuned deployment (wx42gg6q/q415dj1) is in
    # DEPLOY_FAILED state because it was provisioned on a 40 GB H100 MIG slice
    # which cannot fit the 80B model. The base abliterated model qrj8djv3 is
    # deployable on H100:4 (currently SCALED_TO_ZERO; first call cold-starts).
    # Re-deploy the SFT model on H100:4 to recover SFT gains.
    DEFAULT_ENDPOINT = "https://model-qrj8djv3.api.baseten.co/environments/production/sync/v1/chat/completions"

    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None,
                 timeout: int = 600, default_model: str = "Qwen3-Next-80B-A3B-Abliterated"):
        self.endpoint = endpoint or os.environ.get("BASETEN_ENDPOINT") or self.DEFAULT_ENDPOINT
        self.api_key = api_key or _load_baseten_api_key()
        if not self.api_key:
            raise RuntimeError(
                "BASETEN_API_KEY not set and no api_key in ~/.trussrc. "
                "Set BASETEN_API_KEY env var or use MockLLMClient."
            )
        self.timeout = timeout
        self.default_model = default_model

    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None,
             temperature: float = 0.2, max_tokens: int = 1500) -> Dict[str, Any]:
        body = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Api-Key {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")[:500] if hasattr(e, "read") else ""
            raise RuntimeError(f"baseten_http_{e.code}: {err_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"baseten_url_error: {e}") from e
        elapsed = time.time() - t0

        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"baseten_bad_json: {raw[:300]}") from e

        text = ""
        try:
            text = obj["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            text = obj.get("text") or ""

        usage = obj.get("usage") or {}
        return {
            "text": text or "",
            "model": obj.get("model", model or self.default_model),
            "tokens_in": int(usage.get("prompt_tokens", 0) or 0),
            "tokens_out": int(usage.get("completion_tokens", 0) or 0),
            "elapsed_s": elapsed,
            "raw": obj,
        }


class MockLLMClient:
    """Offline client. Returns a deterministic JSON envelope based on the finding.

    Useful for:
      - free local development
      - integration tests that should not hit Baseten
      - estimating throughput before paying
    """

    def __init__(self, severity_for_priority: bool = True,
                 always_return_real: bool = True,
                 fixed_text: Optional[str] = None):
        self.severity_for_priority = severity_for_priority
        self.always_return_real = always_return_real
        self.fixed_text = fixed_text
        self.calls = 0

    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None,
             temperature: float = 0.2, max_tokens: int = 1500) -> Dict[str, Any]:
        self.calls += 1
        if self.fixed_text is not None:
            text = self.fixed_text
        else:
            sys_msg = messages[0]["content"] if messages else ""
            user = messages[-1]["content"] if messages else ""
            cwe = "CWE-?"
            for line in user.splitlines():
                if line.strip().startswith("- cwe:"):
                    cwe = line.split(":", 1)[1].strip()
                    break
            severity = "high" if "CWE-416" in cwe or "CWE-122" in cwe or "CWE-89" in cwe else "medium"
            # Detect verifier prompt by signature in the system message.
            if "SKEPTICAL vulnerability verifier" in sys_msg:
                obj = {
                    "verified": self.always_return_real,
                    "confidence": 0.7,
                    "cvss": 8.0 if severity == "high" else 5.0,
                    "severity": severity,
                    "reason": f"Mock verifier verdict for {cwe}: confirmed plausible based on the dataflow described.",
                }
            else:
                obj = {
                    "is_real_bug": self.always_return_real,
                    "severity": severity,
                    "confidence": 0.65,
                    "false_positive_likelihood": 0.35,
                    "exploit_path": f"Mock exploit path for {cwe}: attacker triggers the reported sink with controlled input.",
                    "preconditions": ["attacker can reach the entry point", "input validation absent"],
                    "poc_stub": "# mock poc\nprint('triggering ' + '" + cwe + "')",
                    "reasoning": "Mock reasoning. Replace with real LLMClient for actual analysis.",
                }
            text = "```json\n" + json.dumps(obj) + "\n```"
        # Cheap token estimate: 1 token per 4 chars
        tin = sum(len(m.get("content", "")) for m in messages) // 4
        tout = len(text) // 4
        return {
            "text": text,
            "model": model or "mock",
            "tokens_in": tin,
            "tokens_out": tout,
            "elapsed_s": 0.001,
            "raw": {"mock": True},
        }
