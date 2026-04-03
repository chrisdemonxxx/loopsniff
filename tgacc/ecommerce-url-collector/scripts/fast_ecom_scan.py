#!/usr/bin/env python3
"""Fast e-commerce scanner: lightweight check for /products.json + basic DOM signals.
Designed for high throughput (10-20 req/s) with minimal resource usage.
Runs independently from the main run_verify.py process."""

import asyncio
import aiohttp
import csv
import re
import sys
import time
import argparse
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)
logging.getLogger('asyncio').setLevel(logging.CRITICAL)
logging.getLogger('aiohttp').setLevel(logging.CRITICAL)

# Quick e-commerce DOM signatures (fast regex)
ECOM_RE = re.compile(
    r'(?:add.to.cart|buy.now|checkout|woocommerce|magento|prestashop|opencart|'
    r'bigcommerce|shopify|ecwid|squarespace.*/commerce|snipcart|'
    r'product-price|cart-count|mini-cart|shopping.cart|'
    r'cdn\.shopify\.com|wp-content/plugins/woocommerce|'
    r'/checkout/|/cart/|cart\.js|checkout\.js)',
    re.IGNORECASE
)

PAYMENT_RE = re.compile(
    r'(?:js\.stripe\.com|paypal\.com/sdk|checkout\.stripe\.com|'
    r'pay\.google\.com|apple.pay|klarna|afterpay|clearpay|'
    r'square.*payment|braintree|adyen|razorpay)',
    re.IGNORECASE
)

PLATFORM_MAP = {
    'cdn.shopify.com': 'shopify',
    'myshopify.com': 'shopify',
    'woocommerce': 'woocommerce',
    'wp-content/plugins/woocommerce': 'woocommerce',
    'magento': 'magento',
    'prestashop': 'prestashop',
    'opencart': 'opencart',
    'bigcommerce': 'bigcommerce',
    'ecwid': 'ecwid',
    'squarespace.com/commerce': 'squarespace',
    'snipcart': 'snipcart',
}

async def check_domain(session, domain, semaphore):
    """Fast e-commerce check: /products.json first, then quick DOM scan."""
    async with semaphore:
        result = {
            'domain': domain,
            'status': 'dead',
            'platform': '',
            'has_products': False,
            'product_count': 0,
            'ecom_signals': 0,
            'has_payment': False,
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/json',
        }
        timeout = aiohttp.ClientTimeout(total=8, connect=4)

        # Step 1: Try /products.json (Shopify-specific, very fast check)
        try:
            url = f'https://{domain}/products.json?limit=3'
            async with session.get(url, headers=headers, timeout=timeout,
                                   ssl=False, allow_redirects=True, max_redirects=2) as resp:
                if resp.status == 200:
                    ct = resp.headers.get('content-type', '')
                    if 'json' in ct or 'javascript' in ct:
                        text = await resp.text(errors='ignore')
                        if '"products"' in text[:500]:
                            try:
                                import json
                                data = json.loads(text)
                                products = data.get('products', [])
                                result['status'] = 'active_ecommerce'
                                result['platform'] = 'shopify'
                                result['has_products'] = len(products) > 0
                                result['product_count'] = len(products)
                                result['ecom_signals'] = 5
                                return result
                            except:
                                pass
        except:
            pass

        # Step 2: Quick homepage DOM scan (first 30KB only)
        try:
            url = f'https://{domain}'
            async with session.get(url, headers=headers, timeout=timeout,
                                   ssl=False, allow_redirects=True, max_redirects=3) as resp:
                if resp.status == 200:
                    result['status'] = 'active'
                    # Read only first 30KB for speed
                    chunk = await resp.content.read(30720)
                    html = chunk.decode('utf-8', errors='ignore')

                    # Check e-commerce signals
                    ecom_matches = ECOM_RE.findall(html)
                    result['ecom_signals'] = len(set(ecom_matches))

                    # Detect platform
                    html_lower = html.lower()
                    for sig, platform in PLATFORM_MAP.items():
                        if sig.lower() in html_lower:
                            result['platform'] = platform
                            break

                    # Check payment
                    if PAYMENT_RE.search(html):
                        result['has_payment'] = True

                    # Classify
                    if result['ecom_signals'] >= 2 or result['platform']:
                        result['status'] = 'active_ecommerce'
                        result['has_products'] = True
                elif resp.status in (301, 302, 307, 308):
                    result['status'] = 'redirect'
                else:
                    result['status'] = f'http_{resp.status}'
        except asyncio.TimeoutError:
            result['status'] = 'timeout'
        except:
            pass

        # Step 3: Try HTTP if HTTPS failed
        if result['status'] in ('dead', 'timeout'):
            try:
                url = f'http://{domain}'
                async with session.get(url, headers=headers, timeout=timeout,
                                       allow_redirects=True, max_redirects=3) as resp:
                    if resp.status == 200:
                        result['status'] = 'active'
                        chunk = await resp.content.read(30720)
                        html = chunk.decode('utf-8', errors='ignore')
                        ecom_matches = ECOM_RE.findall(html)
                        result['ecom_signals'] = len(set(ecom_matches))
                        html_lower = html.lower()
                        for sig, platform in PLATFORM_MAP.items():
                            if sig.lower() in html_lower:
                                result['platform'] = platform
                                break
                        if PAYMENT_RE.search(html):
                            result['has_payment'] = True
                        if result['ecom_signals'] >= 2 or result['platform']:
                            result['status'] = 'active_ecommerce'
                            result['has_products'] = True
            except:
                pass

        return result

async def process_chunk(domains, workers):
    """Process a chunk of domains."""
    semaphore = asyncio.Semaphore(workers)
    connector = aiohttp.TCPConnector(
        limit=workers + 10,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
        force_close=True,
    )
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_domain(session, d, semaphore) for d in domains]
        return await asyncio.gather(*tasks)

def main():
    parser = argparse.ArgumentParser(description='Fast e-commerce scanner')
    parser.add_argument('--input', default='output/remaining_candidates.csv')
    parser.add_argument('--output', default='output/verified_remaining.csv')
    parser.add_argument('--workers', type=int, default=20)
    parser.add_argument('--chunk-size', type=int, default=500)
    parser.add_argument('--max-domains', type=int, default=0, help='Max domains to process (0=all)')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()

    # Load domains
    domains = []
    with open(args.input) as f:
        reader = csv.DictReader(f)
        for row in reader:
            domains.append(row['domain'])
    log.info(f"Loaded {len(domains):,} domains from {args.input}")

    # Resume
    already_done = set()
    if args.resume and os.path.exists(args.output):
        with open(args.output) as f:
            reader = csv.DictReader(f)
            for row in reader:
                already_done.add(row.get('domain', ''))
        log.info(f"Resuming: {len(already_done):,} already done")
        domains = [d for d in domains if d not in already_done]

    if args.max_domains > 0:
        domains = domains[:args.max_domains]

    log.info(f"To process: {len(domains):,}")
    log.info(f"Workers: {args.workers}, Chunk size: {args.chunk_size}")

    # Process
    fieldnames = ['domain', 'status', 'platform', 'has_products', 'product_count',
                  'ecom_signals', 'has_payment']
    
    write_header = not args.resume or not os.path.exists(args.output)
    outfile = open(args.output, 'a' if args.resume else 'w', newline='')
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    if write_header:
        writer.writeheader()

    total_active = 0
    total_ecom = 0
    total_processed = 0
    start_time = time.time()

    for i in range(0, len(domains), args.chunk_size):
        chunk = domains[i:i + args.chunk_size]
        chunk_num = i // args.chunk_size + 1
        total_chunks = (len(domains) + args.chunk_size - 1) // args.chunk_size

        results = asyncio.run(process_chunk(chunk, args.workers))

        for r in results:
            if 'active' in r['status']:
                total_active += 1
            if r['status'] == 'active_ecommerce':
                total_ecom += 1
            writer.writerow(r)

        total_processed += len(chunk)
        elapsed = time.time() - start_time
        rate = total_processed / elapsed if elapsed > 0 else 0
        eta_h = (len(domains) - total_processed) / rate / 3600 if rate > 0 else 0

        log.info(
            f"Chunk {chunk_num}/{total_chunks} | "
            f"Processed: {total_processed:,} | "
            f"Active: {total_active:,} | "
            f"E-commerce: {total_ecom:,} ({total_ecom*100/max(1,total_processed):.1f}%) | "
            f"Rate: {rate:.0f}/s | "
            f"ETA: {eta_h:.1f}h"
        )
        outfile.flush()

    outfile.close()
    elapsed = time.time() - start_time
    log.info(f"DONE in {elapsed:.0f}s. Processed: {total_processed:,}")
    log.info(f"Active: {total_active:,} | E-commerce: {total_ecom:,}")

if __name__ == '__main__':
    main()
