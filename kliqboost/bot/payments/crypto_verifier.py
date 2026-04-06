"""On-chain crypto transaction verification for BTC, ETH, and USDT (ERC-20).

Uses free public APIs:
  - BTC:  Blockstream  (blockstream.info)
  - ETH:  Etherscan    (api.etherscan.io)
  - USDT: Etherscan token-transfer events
  - Prices: CoinGecko  (api.coingecko.com)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)

# ── Price cache (avoid hammering CoinGecko) ──────────────────────────────
_price_cache: dict[str, tuple[float, float]] = {}  # coin -> (price_usd, timestamp)
PRICE_TTL = 120  # seconds


@dataclass
class TxResult:
    verified: bool = False
    status: str = "not_found"  # confirmed | pending | not_found | amount_mismatch | error
    amount_crypto: float = 0.0
    amount_usd: float = 0.0
    confirmations: int = 0
    from_address: str = ""
    to_address: str = ""
    currency: str = ""
    error: str = ""


# ── Helpers ──────────────────────────────────────────────────────────────

async def _get(session: aiohttp.ClientSession, url: str, **kw) -> dict | list | None:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15), **kw) as r:
            if r.status == 200:
                return await r.json()
            log.warning("API %s returned %d", url[:80], r.status)
    except Exception as exc:
        log.warning("API call failed %s: %s", url[:80], exc)
    return None


async def get_crypto_price(coin: str = "bitcoin") -> float:
    """Fetch USD price from CoinGecko (cached 2 min)."""
    now = time.time()
    cached = _price_cache.get(coin)
    if cached and now - cached[1] < PRICE_TTL:
        return cached[0]
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd"
    async with aiohttp.ClientSession() as s:
        data = await _get(s, url)
    if data and coin in data:
        price = float(data[coin]["usd"])
        _price_cache[coin] = (price, now)
        return price
    # Fallback: return cached even if stale
    if cached:
        return cached[0]
    return 0.0


def _normalize_hash(tx_hash: str) -> str:
    h = tx_hash.strip()
    if h.startswith("0x"):
        return h
    return h


# ── BTC verification (Blockstream) ──────────────────────────────────────

async def verify_btc(
    tx_hash: str,
    expected_address: str,
    min_amount_usd: float = 0,
) -> TxResult:
    """Verify a BTC transaction via Blockstream API."""
    result = TxResult(currency="BTC")
    h = _normalize_hash(tx_hash)

    async with aiohttp.ClientSession() as session:
        data = await _get(session, f"https://blockstream.info/api/tx/{h}")
        if not data:
            result.status = "not_found"
            return result

        # Confirmations
        if data.get("status", {}).get("confirmed"):
            tip = await _get(session, "https://blockstream.info/api/blocks/tip/height")
            block_h = data["status"].get("block_height", 0)
            result.confirmations = (int(tip) - block_h + 1) if tip else 1
        else:
            result.confirmations = 0

        # Find output to our address
        total_sats = 0
        for vout in data.get("vout", []):
            addr = vout.get("scriptpubkey_address", "")
            if addr.lower() == expected_address.lower():
                total_sats += vout.get("value", 0)
                result.to_address = addr

        if total_sats == 0:
            result.status = "amount_mismatch"
            result.error = f"No output to {expected_address}"
            return result

        result.amount_crypto = total_sats / 1e8  # satoshis → BTC

        # Sender (first input)
        vin = data.get("vin", [])
        if vin and vin[0].get("prevout"):
            result.from_address = vin[0]["prevout"].get("scriptpubkey_address", "")

        # USD conversion
        btc_price = await get_crypto_price("bitcoin")
        result.amount_usd = result.amount_crypto * btc_price

        # Amount check
        if min_amount_usd > 0 and result.amount_usd < min_amount_usd * 0.95:
            result.status = "amount_mismatch"
            result.error = f"Expected ~${min_amount_usd:.0f}, got ${result.amount_usd:.2f}"
            return result

        result.verified = result.confirmations >= 1
        result.status = "confirmed" if result.verified else "pending"
        return result


# ── ETH verification (Etherscan) ─────────────────────────────────────────

async def verify_eth(
    tx_hash: str,
    expected_address: str,
    min_amount_usd: float = 0,
) -> TxResult:
    """Verify a native ETH transaction via Etherscan."""
    result = TxResult(currency="ETH")
    h = tx_hash.strip()
    if not h.startswith("0x"):
        h = "0x" + h

    async with aiohttp.ClientSession() as session:
        url = (
            "https://api.etherscan.io/api"
            f"?module=proxy&action=eth_getTransactionByHash&txhash={h}"
        )
        data = await _get(session, url)
        if not data or data.get("result") in (None, ""):
            result.status = "not_found"
            return result

        tx = data["result"]
        to_addr = (tx.get("to") or "").lower()
        if to_addr != expected_address.lower():
            result.status = "amount_mismatch"
            result.error = f"Sent to {to_addr}, expected {expected_address}"
            return result

        result.to_address = to_addr
        result.from_address = tx.get("from", "")

        # Value in wei → ETH
        value_hex = tx.get("value", "0x0")
        value_wei = int(value_hex, 16)
        result.amount_crypto = value_wei / 1e18

        # Check receipt for confirmation
        receipt_url = (
            "https://api.etherscan.io/api"
            f"?module=proxy&action=eth_getTransactionReceipt&txhash={h}"
        )
        receipt = await _get(session, receipt_url)
        if receipt and receipt.get("result"):
            status = receipt["result"].get("status")
            block_num = receipt["result"].get("blockNumber")
            if status == "0x1" and block_num:
                # Get current block for confirmation count
                blk_url = "https://api.etherscan.io/api?module=proxy&action=eth_blockNumber"
                blk = await _get(session, blk_url)
                if blk and blk.get("result"):
                    current = int(blk["result"], 16)
                    tx_block = int(block_num, 16)
                    result.confirmations = current - tx_block + 1
                else:
                    result.confirmations = 1
            elif status == "0x0":
                result.status = "error"
                result.error = "Transaction reverted"
                return result

        # USD conversion
        eth_price = await get_crypto_price("ethereum")
        result.amount_usd = result.amount_crypto * eth_price

        if min_amount_usd > 0 and result.amount_usd < min_amount_usd * 0.95:
            result.status = "amount_mismatch"
            result.error = f"Expected ~${min_amount_usd:.0f}, got ${result.amount_usd:.2f}"
            return result

        result.verified = result.confirmations >= 1
        result.status = "confirmed" if result.verified else "pending"
        return result


# ── USDT ERC-20 verification (Etherscan token events) ────────────────────

USDT_CONTRACT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

async def verify_usdt_erc20(
    tx_hash: str,
    expected_address: str,
    min_amount_usd: float = 0,
) -> TxResult:
    """Verify a USDT ERC-20 transfer via Etherscan token-tx API."""
    result = TxResult(currency="USDT")
    h = tx_hash.strip()
    if not h.startswith("0x"):
        h = "0x" + h

    async with aiohttp.ClientSession() as session:
        # Check recent token transfers to our address
        url = (
            "https://api.etherscan.io/api"
            f"?module=account&action=tokentx"
            f"&contractaddress={USDT_CONTRACT}"
            f"&address={expected_address}"
            f"&sort=desc&page=1&offset=50"
        )
        data = await _get(session, url)
        if not data or data.get("status") != "1":
            # Fallback: check transaction receipt directly
            return await _verify_usdt_from_receipt(session, h, expected_address, min_amount_usd, result)

        # Find matching tx hash in token transfers
        for tx in data.get("result", []):
            if tx.get("hash", "").lower() == h.lower():
                result.from_address = tx.get("from", "")
                result.to_address = tx.get("to", "")
                # USDT has 6 decimals
                raw_value = int(tx.get("value", "0"))
                result.amount_crypto = raw_value / 1e6
                result.amount_usd = result.amount_crypto  # USDT ≈ $1

                confirmations = int(tx.get("confirmations", "0"))
                result.confirmations = confirmations

                if min_amount_usd > 0 and result.amount_usd < min_amount_usd * 0.95:
                    result.status = "amount_mismatch"
                    result.error = f"Expected ~${min_amount_usd:.0f}, got ${result.amount_usd:.2f}"
                    return result

                result.verified = confirmations >= 1
                result.status = "confirmed" if result.verified else "pending"
                return result

        # Hash not found in recent transfers
        return await _verify_usdt_from_receipt(session, h, expected_address, min_amount_usd, result)


async def _verify_usdt_from_receipt(
    session: aiohttp.ClientSession,
    tx_hash: str,
    expected_address: str,
    min_amount_usd: float,
    result: TxResult,
) -> TxResult:
    """Fallback: check tx receipt logs for USDT Transfer event."""
    url = (
        "https://api.etherscan.io/api"
        f"?module=proxy&action=eth_getTransactionReceipt&txhash={tx_hash}"
    )
    data = await _get(session, url)
    if not data or not data.get("result"):
        result.status = "not_found"
        return result

    receipt = data["result"]
    if receipt.get("status") == "0x0":
        result.status = "error"
        result.error = "Transaction reverted"
        return result

    # Parse Transfer(address,address,uint256) logs
    # Topic0 for Transfer: 0xddf252ad...
    TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    for log_entry in receipt.get("logs", []):
        if (
            log_entry.get("address", "").lower() == USDT_CONTRACT.lower()
            and len(log_entry.get("topics", [])) >= 3
            and log_entry["topics"][0].lower() == TRANSFER_TOPIC
        ):
            # Decode: topics[1]=from, topics[2]=to, data=amount
            to_raw = "0x" + log_entry["topics"][2][-40:]
            if to_raw.lower() == expected_address.lower():
                from_raw = "0x" + log_entry["topics"][1][-40:]
                result.from_address = from_raw
                result.to_address = to_raw
                amount_hex = log_entry.get("data", "0x0")
                result.amount_crypto = int(amount_hex, 16) / 1e6
                result.amount_usd = result.amount_crypto

                if min_amount_usd > 0 and result.amount_usd < min_amount_usd * 0.95:
                    result.status = "amount_mismatch"
                    result.error = f"Expected ~${min_amount_usd:.0f}, got ${result.amount_usd:.2f}"
                    return result

                result.verified = True
                result.status = "confirmed"
                result.confirmations = 1
                return result

    result.status = "not_found"
    result.error = "No USDT transfer to expected address found in tx"
    return result


# ── Dispatcher ───────────────────────────────────────────────────────────

async def verify_transaction(
    tx_hash: str,
    currency: str,
    expected_address: str,
    min_amount_usd: float = 0,
) -> TxResult:
    """Route verification to the correct chain handler."""
    cur = currency.upper().strip()
    if cur == "BTC":
        return await verify_btc(tx_hash, expected_address, min_amount_usd)
    elif cur == "ETH":
        return await verify_eth(tx_hash, expected_address, min_amount_usd)
    elif cur in ("USDT", "USDT_ERC20", "USDT-ERC20"):
        return await verify_usdt_erc20(tx_hash, expected_address, min_amount_usd)
    else:
        return TxResult(status="error", error=f"Unsupported currency: {currency}")
