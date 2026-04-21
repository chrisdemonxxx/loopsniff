"""Blockchain transaction verification for Kliqboost payments.

Validates tx hashes against public blockchain APIs:
  - USDT TRC20: TronGrid
  - USDT ERC20 / ETH: Etherscan
  - BTC: Blockstream

Returns verification result with amount, confirmations, and status.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)

# ── API keys (free tier is fine for verification) ─────────────────────────
TRONGRID_API_KEY = os.getenv("TRONGRID_API_KEY", "")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")

# ── Known wallet addresses (lowercase for comparison) ────────────────────
BTC_ADDRESS = os.getenv("BTC_ADDRESS", "").strip()
ETH_ADDRESS = os.getenv("ETH_ADDRESS", "").strip().lower()
USDT_TRC20_ADDRESS = os.getenv("USDT_TRC20_ADDRESS", "").strip()
USDT_ERC20_ADDRESS = os.getenv("USDT_ERC20_ADDRESS", "").strip().lower()

# USDT contract addresses
USDT_TRC20_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
USDT_ERC20_CONTRACT = "0xdac17f958d2ee523a2206206994597c13d831ec7"

# Minimum confirmations to consider a tx confirmed
MIN_CONFIRMATIONS_BTC = 1
MIN_CONFIRMATIONS_ETH = 6
MIN_CONFIRMATIONS_TRON = 20


class TxChain(Enum):
    BTC = "btc"
    ETH = "eth"
    TRON = "tron"
    UNKNOWN = "unknown"


@dataclass
class TxVerification:
    valid: bool
    chain: TxChain
    tx_hash: str
    amount: float = 0.0
    currency: str = ""
    confirmations: int = 0
    confirmed: bool = False
    to_address: str = ""
    matches_wallet: bool = False
    error: str = ""


# ── TX hash detection ────────────────────────────────────────────────────

# BTC: 64 hex chars
_BTC_TX_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")
# ETH: 0x + 64 hex chars
_ETH_TX_RE = re.compile(r"\b0x[0-9a-fA-F]{64}\b")
# TRON: 64 hex chars (same as BTC, disambiguate by API)


def detect_tx_hash(text: str) -> Optional[tuple[str, TxChain]]:
    """Extract a transaction hash from user message text.
    Returns (hash, chain_hint) or None."""
    # ETH-style first (has 0x prefix)
    m = _ETH_TX_RE.search(text)
    if m:
        return m.group(0), TxChain.ETH

    # BTC / TRON (both 64 hex, we'll try both APIs)
    m = _BTC_TX_RE.search(text)
    if m:
        return m.group(0), TxChain.UNKNOWN  # could be BTC or TRON
    return None


# ── Verification APIs ────────────────────────────────────────────────────

async def _verify_tron(tx_hash: str, session: aiohttp.ClientSession) -> TxVerification:
    """Verify a TRON/TRC20 transaction via TronGrid."""
    url = f"https://api.trongrid.io/v1/transactions/{tx_hash}/events"
    headers = {}
    if TRONGRID_API_KEY:
        headers["TRON-PRO-API-KEY"] = TRONGRID_API_KEY

    try:
        # First get basic tx info
        tx_url = f"https://api.trongrid.io/wallet/gettransactionbyid"
        async with session.post(tx_url, json={"value": tx_hash}, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return TxVerification(valid=False, chain=TxChain.TRON, tx_hash=tx_hash, error=f"TronGrid HTTP {resp.status}")
            tx_data = await resp.json()
            if not tx_data or "txID" not in tx_data:
                return TxVerification(valid=False, chain=TxChain.TRON, tx_hash=tx_hash, error="TX not found on TRON")

        # Get tx info with confirmations
        info_url = f"https://api.trongrid.io/wallet/gettransactioninfobyid"
        async with session.post(info_url, json={"value": tx_hash}, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            info = await resp.json()
            confirmations = info.get("blockNumber", 0)
            # TronGrid doesn't return confirmations directly, but blockNumber > 0 means confirmed
            is_confirmed = confirmations > 0 and info.get("receipt", {}).get("result", "") == "SUCCESS"

        # Get TRC20 transfer events
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            events = await resp.json()
            event_list = events.get("data", [])

            for event in event_list:
                if event.get("event_name") == "Transfer":
                    result = event.get("result", {})
                    to_addr = result.get("to", "")
                    value = int(result.get("value", "0"))
                    # USDT TRC20 has 6 decimals
                    amount = value / 1_000_000
                    contract = event.get("contract_address", "")

                    matches = (
                        to_addr.lower() == USDT_TRC20_ADDRESS.lower()
                        if USDT_TRC20_ADDRESS else False
                    )

                    return TxVerification(
                        valid=True,
                        chain=TxChain.TRON,
                        tx_hash=tx_hash,
                        amount=amount,
                        currency="USDT (TRC20)",
                        confirmations=confirmations,
                        confirmed=is_confirmed,
                        to_address=to_addr,
                        matches_wallet=matches,
                    )

            # Not a TRC20 transfer, might be a TRX transfer
            return TxVerification(
                valid=True,
                chain=TxChain.TRON,
                tx_hash=tx_hash,
                confirmations=confirmations,
                confirmed=is_confirmed,
                currency="TRX",
                error="Not a USDT TRC20 transfer",
            )

    except Exception as e:
        return TxVerification(valid=False, chain=TxChain.TRON, tx_hash=tx_hash, error=str(e))


async def _verify_eth(tx_hash: str, session: aiohttp.ClientSession) -> TxVerification:
    """Verify an ETH/ERC20 transaction via Etherscan."""
    if not ETHERSCAN_API_KEY:
        # Use public Etherscan (rate limited)
        base = "https://api.etherscan.io/api"
    else:
        base = "https://api.etherscan.io/api"

    try:
        # Get tx receipt
        params = {
            "module": "proxy",
            "action": "eth_getTransactionReceipt",
            "txhash": tx_hash,
            "apikey": ETHERSCAN_API_KEY or "YourApiKeyToken",
        }
        async with session.get(base, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            data = await resp.json()
            result = data.get("result")
            if not result or result == "null":
                return TxVerification(valid=False, chain=TxChain.ETH, tx_hash=tx_hash, error="TX not found on Ethereum")

            status = int(result.get("status", "0x0"), 16)
            if status != 1:
                return TxVerification(valid=False, chain=TxChain.ETH, tx_hash=tx_hash, error="TX failed on-chain")

            # Check logs for ERC20 Transfer events
            logs = result.get("logs", [])
            transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

            for log_entry in logs:
                topics = log_entry.get("topics", [])
                if topics and topics[0] == transfer_topic:
                    contract = log_entry.get("address", "").lower()
                    if contract == USDT_ERC20_CONTRACT:
                        # USDT ERC20 transfer
                        to_addr = "0x" + topics[2][-40:] if len(topics) > 2 else ""
                        value = int(log_entry.get("data", "0x0"), 16)
                        amount = value / 1_000_000  # USDT has 6 decimals

                        matches = (
                            to_addr.lower() == USDT_ERC20_ADDRESS.lower()
                            if USDT_ERC20_ADDRESS else False
                        )

                        # Get block number for confirmations
                        block_num = int(result.get("blockNumber", "0x0"), 16)

                        return TxVerification(
                            valid=True,
                            chain=TxChain.ETH,
                            tx_hash=tx_hash,
                            amount=amount,
                            currency="USDT (ERC20)",
                            confirmations=block_num,
                            confirmed=True,
                            to_address=to_addr,
                            matches_wallet=matches,
                        )

            # Plain ETH transfer
            to_addr = result.get("to", "")
            matches = to_addr.lower() == ETH_ADDRESS if ETH_ADDRESS else False

            # Get tx value
            tx_params = {
                "module": "proxy",
                "action": "eth_getTransactionByHash",
                "txhash": tx_hash,
                "apikey": ETHERSCAN_API_KEY or "YourApiKeyToken",
            }
            async with session.get(base, params=tx_params, timeout=aiohttp.ClientTimeout(total=15)) as tx_resp:
                tx_data = await tx_resp.json()
                tx_result = tx_data.get("result", {})
                value_wei = int(tx_result.get("value", "0x0"), 16)
                amount_eth = value_wei / 1e18

            return TxVerification(
                valid=True,
                chain=TxChain.ETH,
                tx_hash=tx_hash,
                amount=amount_eth,
                currency="ETH",
                confirmed=True,
                to_address=to_addr,
                matches_wallet=matches,
            )

    except Exception as e:
        return TxVerification(valid=False, chain=TxChain.ETH, tx_hash=tx_hash, error=str(e))


async def _verify_btc(tx_hash: str, session: aiohttp.ClientSession) -> TxVerification:
    """Verify a BTC transaction via Blockstream API."""
    url = f"https://blockstream.info/api/tx/{tx_hash}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 404:
                return TxVerification(valid=False, chain=TxChain.BTC, tx_hash=tx_hash, error="TX not found on Bitcoin")
            if resp.status != 200:
                return TxVerification(valid=False, chain=TxChain.BTC, tx_hash=tx_hash, error=f"Blockstream HTTP {resp.status}")

            data = await resp.json()
            confirmed = data.get("status", {}).get("confirmed", False)
            block_height = data.get("status", {}).get("block_height", 0)

            # Find output matching our wallet
            for vout in data.get("vout", []):
                addr = vout.get("scriptpubkey_address", "")
                if addr and addr == BTC_ADDRESS:
                    amount_sat = vout.get("value", 0)
                    amount_btc = amount_sat / 1e8
                    return TxVerification(
                        valid=True,
                        chain=TxChain.BTC,
                        tx_hash=tx_hash,
                        amount=amount_btc,
                        currency="BTC",
                        confirmations=block_height,
                        confirmed=confirmed,
                        to_address=addr,
                        matches_wallet=True,
                    )

            # TX exists but not to our address
            total_value = sum(v.get("value", 0) for v in data.get("vout", [])) / 1e8
            return TxVerification(
                valid=True,
                chain=TxChain.BTC,
                tx_hash=tx_hash,
                amount=total_value,
                currency="BTC",
                confirmed=confirmed,
                confirmations=block_height,
                matches_wallet=False,
            )

    except Exception as e:
        return TxVerification(valid=False, chain=TxChain.BTC, tx_hash=tx_hash, error=str(e))


# ── Main verification entry point ────────────────────────────────────────

async def verify_transaction(tx_hash: str, chain_hint: TxChain = TxChain.UNKNOWN) -> TxVerification:
    """Verify a transaction hash against blockchain APIs.

    For unknown chains (64 hex without 0x), tries TRON first, then BTC.
    """
    async with aiohttp.ClientSession() as session:
        if chain_hint == TxChain.ETH:
            return await _verify_eth(tx_hash, session)

        if chain_hint == TxChain.TRON:
            return await _verify_tron(tx_hash, session)

        if chain_hint == TxChain.BTC:
            return await _verify_btc(tx_hash, session)

        # Unknown — try TRON first (most common for USDT), then BTC
        result = await _verify_tron(tx_hash, session)
        if result.valid:
            return result

        result = await _verify_btc(tx_hash, session)
        if result.valid:
            return result

        return TxVerification(
            valid=False,
            chain=TxChain.UNKNOWN,
            tx_hash=tx_hash,
            error="TX not found on TRON, BTC, or ETH",
        )
