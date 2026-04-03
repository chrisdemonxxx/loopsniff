#!/usr/bin/env python3
"""
Robust chunked verification runner.
Processes domains in chunks, saves progress after each chunk, can resume.
"""

import asyncio
import aiohttp
import csv
import json
import os
import sys
import re
import time
import logging
from collections import defaultdict
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

# Suppress noisy aiohttp DNS error tracebacks
logging.getLogger('asyncio').setLevel(logging.CRITICAL)
logging.getLogger('aiohttp').setLevel(logging.WARNING)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# Payment gateway signatures
PAYMENT_SIGNATURES = {
    'stripe': ['js.stripe.com', 'stripe.com/v3', 'Stripe('],
    'paypal': ['paypal.com/sdk', 'paypalobjects.com', 'paypal-button'],
    'klarna': ['klarna.com', 'klarna-payments', 'KlarnaOnsiteService'],
    'afterpay': ['afterpay.com', 'afterpay-widget', 'clearpay.com'],
    'square': ['squareup.com', 'square.js', 'square-payment'],
    'braintree': ['braintreegateway.com', 'braintree-web', 'braintree.js'],
    'adyen': ['adyen.com', 'adyen-checkout', 'AdyenCheckout'],
    'shopify_payments': ['shopify-payment', 'Shopify.Checkout'],
    'razorpay': ['razorpay.com', 'Razorpay('],
    'mollie': ['mollie.com', 'js.mollie.com'],
    'authorize_net': ['authorize.net', 'Accept.js'],
}

# Platform signatures
PLATFORM_SIGNATURES = {
    'shopify': ['cdn.shopify.com', 'myshopify.com', 'Shopify.theme', 'shopify-section',
                'shopify-payment', 'Shopify.shop', '/products.json', '_shopify_y'],
    'woocommerce': ['wp-content/plugins/woocommerce', 'woocommerce-page', 'wc-add-to-cart',
                    'wc-block-grid', 'woocommerce-product', 'wc-ajax'],
    'magento': ['Magento_Ui', 'mage/cookies', 'data-mage-init', 'Magento_Customer',
                '/static/version', 'varien/form.js'],
    'prestashop': ['PrestaShop', 'prestashop', 'id_product=', '/modules/ps_',
                   'prestashop-page', 'blockcart'],
    'opencart': ['index.php?route=', 'Powered by OpenCart', 'catalog/view/theme'],
    'bigcommerce': ['BigCommerce', 'data-content-region', 'bigcommerce.com',
                    'stencil-utils', 'cornerstone'],
    'squarespace': ['squarespace.com', 'static.squarespace', 'sqsp.com'],
    'wix': ['wixsite.com', 'parastorage.com', '_wix_browser_sess'],
}


async def check_domain(session, domain, semaphore):
    """Check a single domain for e-commerce signals."""
    async with semaphore:
        result = {
            'domain': domain,
            'status': 'unknown',
            'http_status': 0,
            'product_count': 0,
            'product_types': [],
            'tags': [],
            'has_products': False,
            'platform': 'unknown',
            'is_headless': False,
            'detected_payments': [],
            'ecom_signal_count': 0,
            'country': '',
            'min_price': 0,
            'max_price': 0,
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/json',
        }
        timeout = aiohttp.ClientTimeout(total=10, connect=6)

        # Step 1: Try /products.json (fast Shopify check)
        try:
            url = f'https://{domain}/products.json?limit=5'
            async with session.get(url, headers={**headers, 'Accept': 'application/json'},
                                   timeout=timeout, ssl=False, allow_redirects=True) as resp:
                result['http_status'] = resp.status
                if resp.status == 200:
                    try:
                        data = await resp.json(content_type=None)
                        products = data.get('products', [])
                        if products:
                            result['status'] = 'active'
                            result['has_products'] = True
                            result['platform'] = 'shopify'
                            result['product_count'] = len(products)
                            for p in products:
                                pt = p.get('product_type', '').strip()
                                if pt:
                                    result['product_types'].append(pt)
                                tags = p.get('tags', [])
                                if isinstance(tags, list):
                                    result['tags'].extend(tags[:5])
                                elif isinstance(tags, str):
                                    result['tags'].extend([t.strip() for t in tags.split(',')[:5]])
                            prices = []
                            for p in products:
                                for v in p.get('variants', []):
                                    try:
                                        price = float(v.get('price', '0'))
                                        if price > 0:
                                            prices.append(price)
                                    except (ValueError, TypeError):
                                        pass
                            if prices:
                                result['min_price'] = min(prices)
                                result['max_price'] = max(prices)
                            return result
                    except Exception:
                        pass
                elif resp.status == 401:
                    result['status'] = 'password_protected'
                elif resp.status in (429, 430):
                    result['status'] = 'rate_limited'
        except asyncio.TimeoutError:
            pass
        except aiohttp.ClientError:
            pass
        except Exception:
            pass

        # Step 2: Check homepage for e-commerce signals (all platforms)
        try:
            url = f'https://{domain}'
            async with session.get(url, headers=headers, timeout=timeout,
                                   ssl=False, allow_redirects=True) as resp:
                if resp.status != 200:
                    if result['status'] == 'unknown':
                        result['status'] = 'inactive' if resp.status < 500 else 'server_error'
                    return result

                html = await resp.text()
                html_lower = html[:60000].lower()
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}

                # Platform detection
                for platform, sigs in PLATFORM_SIGNATURES.items():
                    for sig in sigs:
                        if sig.lower() in html_lower:
                            result['platform'] = platform
                            break
                    if result['platform'] != 'unknown':
                        break

                # Shopify headless detection
                if 'cdn.shopify.com' in html_lower:
                    result['is_headless'] = True
                    if result['platform'] == 'unknown':
                        result['platform'] = 'shopify'
                if 'x-shopify-stage' in resp_headers:
                    result['is_headless'] = True
                    result['platform'] = 'shopify'

                # E-commerce signal detection
                ecom_signals = 0
                if any(s in html_lower for s in ['add-to-cart', 'add_to_cart', 'addtocart']):
                    ecom_signals += 1
                if any(s in html_lower for s in ['buy-now', 'buy_now', 'buynow', 'buy now']):
                    ecom_signals += 1
                if any(s in html_lower for s in ['/cart', 'shopping-cart', 'cart-count', 'cart-icon', 'minicart']):
                    ecom_signals += 1
                if any(s in html_lower for s in ['/checkout', 'checkout-button', 'proceed-to-checkout']):
                    ecom_signals += 1
                if re.search(r'\$\s*\d+\.?\d*|\d+\.?\d*\s*€|£\s*\d+', html[:20000]):
                    ecom_signals += 1
                if any(s in html_lower for s in ['"@type":"product"', '"@type": "product"', 'schema.org/product']):
                    ecom_signals += 1
                if any(s in html_lower for s in ['product-price', 'product-title', 'product-image', 'product-card']):
                    ecom_signals += 1
                result['ecom_signal_count'] = ecom_signals

                # Payment detection
                for gateway, patterns in PAYMENT_SIGNATURES.items():
                    for pattern in patterns:
                        if pattern.lower() in html_lower:
                            result['detected_payments'].append(gateway)
                            break

                # Country detection
                country_match = re.search(r'Shopify\.country\s*=\s*["\'](\w{2})["\']', html)
                if country_match:
                    result['country'] = country_match.group(1).upper()

                # Determine if active e-commerce
                is_ecommerce = (
                    result['platform'] != 'unknown' or
                    ecom_signals >= 2 or
                    result['is_headless'] or
                    len(result['detected_payments']) > 0
                )

                if is_ecommerce:
                    result['status'] = 'active'
                    result['has_products'] = ecom_signals >= 2
                else:
                    result['status'] = 'not_ecommerce'

        except asyncio.TimeoutError:
            if result['status'] == 'unknown':
                result['status'] = 'timeout'
        except aiohttp.ClientError:
            if result['status'] == 'unknown':
                result['status'] = 'connection_error'
        except Exception:
            if result['status'] == 'unknown':
                result['status'] = 'error'

        return result


async def process_chunk(domains_chunk, workers=30):
    """Process a chunk of domains."""
    semaphore = asyncio.Semaphore(workers)
    connector = aiohttp.TCPConnector(
        limit=workers, ttl_dns_cache=600, ssl=False,
        enable_cleanup_closed=True, force_close=True
    )

    results = []
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_domain(session, d, semaphore) for d in domains_chunk]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in batch_results:
            if isinstance(res, dict):
                results.append(res)

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default=os.path.join(OUTPUT_DIR, 'mega_merged.csv'))
    parser.add_argument('--output', default=os.path.join(OUTPUT_DIR, 'verified_results.csv'))
    parser.add_argument('--chunk-size', type=int, default=500)
    parser.add_argument('--workers', type=int, default=30)
    parser.add_argument('--max-domains', type=int, default=None)
    parser.add_argument('--resume', action='store_true', help='Resume from previous run')
    args = parser.parse_args()

    # Load all domains
    logger.info(f"Loading domains from {args.input}...")
    all_domains = {}
    with open(args.input, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            d = row.get('domain', '').lower().strip()
            if d:
                all_domains[d] = row

    # Load already-processed domains if resuming
    done = set()
    if args.resume and os.path.exists(args.output):
        with open(args.output, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                done.add(row.get('domain', ''))
        logger.info(f"Resuming: {len(done):,} already processed")

    # Get domains to process
    to_process = [d for d in all_domains.keys() if d not in done]

    # Prioritize: curated > cro_media > tranco_ecom > tranco_top100k > majestic
    def priority(d):
        src = all_domains[d].get('source', '')
        tranco = int(all_domains[d].get('tranco_rank', 0) or 0)
        if src == 'curated':
            return (0, tranco or 999999)
        if src == 'cro_media':
            return (1, tranco or 999999)
        if src == 'tranco_ecom':
            return (2, tranco or 999999)
        if src == 'tranco_top100k':
            return (3, tranco or 999999)
        if tranco > 0:
            return (4, tranco)
        return (5, 999999)

    to_process.sort(key=priority)

    if args.max_domains:
        to_process = to_process[:args.max_domains]

    logger.info(f"Total domains: {len(all_domains):,}")
    logger.info(f"To process: {len(to_process):,}")
    logger.info(f"Workers: {args.workers}, Chunk size: {args.chunk_size}")

    # Setup output file
    fieldnames = ['url', 'domain', 'platform', 'niche', 'country', 'source',
                  'tranco_rank', 'majestic_rank', 'status', 'http_status',
                  'has_products', 'product_count', 'product_types', 'tags',
                  'is_headless', 'detected_payments', 'ecom_signal_count',
                  'min_price', 'max_price']

    write_header = not (args.resume and os.path.exists(args.output))
    f_out = open(args.output, 'a' if args.resume else 'w', newline='', encoding='utf-8')
    writer = csv.DictWriter(f_out, fieldnames=fieldnames, extrasaction='ignore')
    if write_header:
        writer.writeheader()

    total_active = 0
    total_ecommerce = 0
    total_processed = len(done)
    start_time = time.time()

    # Process in chunks
    for chunk_start in range(0, len(to_process), args.chunk_size):
        chunk = to_process[chunk_start:chunk_start + args.chunk_size]
        chunk_num = chunk_start // args.chunk_size + 1
        total_chunks = (len(to_process) + args.chunk_size - 1) // args.chunk_size

        try:
            results = asyncio.run(process_chunk(chunk, workers=args.workers))
        except Exception as e:
            logger.error(f"Chunk {chunk_num} failed: {e}")
            continue

        for res in results:
            domain = res['domain']
            meta = all_domains.get(domain, {})

            row = {**meta, **res}
            row['product_types'] = '|'.join(res.get('product_types', [])[:5])
            row['tags'] = '|'.join(res.get('tags', [])[:10])
            row['detected_payments'] = '|'.join(res.get('detected_payments', []))
            row['has_products'] = str(res.get('has_products', False))
            row['is_headless'] = str(res.get('is_headless', False))
            writer.writerow(row)

            if res.get('status') == 'active':
                total_active += 1
                if res.get('has_products') or res.get('ecom_signal_count', 0) >= 2:
                    total_ecommerce += 1

        f_out.flush()
        total_processed += len(chunk)

        elapsed = time.time() - start_time
        rate = total_processed / max(elapsed, 1)
        remaining = (len(to_process) - chunk_start - len(chunk)) / max(rate, 0.1)

        logger.info(
            f"Chunk {chunk_num}/{total_chunks} | "
            f"Processed: {total_processed:,} | "
            f"Active: {total_active:,} | "
            f"E-commerce: {total_ecommerce:,} | "
            f"Rate: {rate:.0f}/s | "
            f"ETA: {remaining/3600:.1f}h"
        )

    f_out.close()

    # Final stats
    elapsed = time.time() - start_time
    logger.info(f"\n{'='*60}")
    logger.info(f"VERIFICATION COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"  Total processed: {total_processed:,}")
    logger.info(f"  Active: {total_active:,} ({total_active/max(total_processed,1)*100:.1f}%)")
    logger.info(f"  E-commerce: {total_ecommerce:,} ({total_ecommerce/max(total_processed,1)*100:.1f}%)")
    logger.info(f"  Time: {elapsed/3600:.1f} hours")
    logger.info(f"  Output: {args.output}")


if __name__ == '__main__':
    main()
