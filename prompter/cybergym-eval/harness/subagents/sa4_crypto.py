"""SA-4: Crypto / auth subagent.

Handles CWE-326, CWE-327, CWE-330, CWE-798, CWE-287, CWE-311.
"""
from __future__ import annotations
from .base import BaseSubagent


class SA4Crypto(BaseSubagent):
    AGENT_ID = "sa4"
    CWE_CLASS = "crypto_auth"

    def cwe_specific_guidance(self) -> str:
        return (
            "## SA-4 (crypto / auth) checklist\n"
            "1. CWE-326 / CWE-327 (weak / broken crypto): MD5, SHA-1 (for security), DES, RC4, "
            "ECB mode, static IV/nonce, CBC without MAC, RSA without OAEP/PSS, custom crypto.\n"
            "2. CWE-330 (insufficient randomness): rand(), srand(time(NULL)), Math.random(), "
            "predictable seed for tokens/keys/IVs. CSPRNG required for security uses.\n"
            "3. CWE-798 (hard-coded credentials): API keys, passwords, JWT secrets, SSH keys, "
            "DB passwords embedded in source. Test/example values count if shipped to prod.\n"
            "4. CWE-287 (improper authentication): missing auth check, broken token validation, "
            "always-true comparisons, JWT alg=none, JWT key confusion.\n"
            "5. CWE-311 (missing encryption): sensitive data sent over plaintext (HTTP), stored "
            "unencrypted at rest, logged in cleartext.\n"
            "Be skeptical: many crypto findings are false positives in test/non-security code "
            "(e.g., MD5 for cache keys, rand() for non-security simulation). Inspect the call "
            "site's purpose. If the value is clearly used as a security primitive, raise "
            "severity; if it's a hash table key or random shuffle, drop to LOW.\n"
            "Severity heuristics: hard-coded prod credential => critical; broken auth check => "
            "critical; weak crypto on sensitive data => high; predictable token => high; "
            "missing TLS => high; weak hash for non-password use => low/medium.\n"
            "PoC stub: a CLI command (e.g., curl/openssl) or python snippet demonstrating the "
            "weakness (forging a token, recovering the key, etc.)."
        )
