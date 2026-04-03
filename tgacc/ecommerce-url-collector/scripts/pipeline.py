#!/usr/bin/env python3
"""
E-Commerce Intelligence Pipeline — Master Orchestrator
Integrates all data sources, runs verification, enrichment, and quality scoring.

Usage:
    python pipeline.py --phase ingest     # Phase 1: Merge & normalize all sources
    python pipeline.py --phase verify     # Phase 2: Primary /products.json verification
    python pipeline.py --phase enrich     # Phase 3: Payment, niche, geo enrichment
    python pipeline.py --phase score      # Phase 4: Quality Score computation
    python pipeline.py --phase export     # Phase 5: Filter & export golden list
    python pipeline.py --phase all        # Run all phases sequentially
"""

import asyncio
import aiohttp
import csv
import json
import os
import sys
import re
import time
import random
import logging
import hashlib
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output', 'pipeline.log')),
    ]
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# NICHE TAXONOMY — Maps product_type/tags to categories
# ============================================================
NICHE_MAP = {
    'fashion': ['apparel', 'clothing', 'fashion', 'wear', 'dress', 'shirt', 'pant', 'jeans',
                'jacket', 'coat', 'sweater', 'hoodie', 'blouse', 'skirt', 'suit', 'uniform',
                't-shirt', 'tshirt', 'outerwear', 'activewear', 'streetwear', 'denim'],
    'shoes': ['shoe', 'sneaker', 'boot', 'sandal', 'heel', 'loafer', 'slipper', 'footwear',
              'trainer', 'pump', 'flat', 'clog', 'mule', 'oxford'],
    'beauty': ['beauty', 'cosmetic', 'makeup', 'skincare', 'fragrance', 'perfume', 'nail',
               'lipstick', 'foundation', 'serum', 'moisturizer', 'concealer', 'mascara'],
    'health': ['health', 'vitamin', 'supplement', 'wellness', 'nutrition', 'protein',
               'collagen', 'probiotic', 'omega', 'cbd', 'hemp', 'essential oil'],
    'electronics': ['electronic', 'tech', 'gadget', 'phone', 'computer', 'laptop', 'tablet',
                    'camera', 'audio', 'speaker', 'headphone', 'charger', 'cable', 'adapter'],
    'home': ['home', 'furniture', 'decor', 'interior', 'kitchen', 'bath', 'bed', 'mattress',
             'pillow', 'rug', 'curtain', 'lamp', 'candle', 'towel', 'storage'],
    'food': ['food', 'grocery', 'gourmet', 'snack', 'candy', 'chocolate', 'cheese', 'meat',
             'seafood', 'bakery', 'spice', 'sauce', 'condiment', 'organic', 'gluten-free'],
    'jewelry': ['jewelry', 'jewellery', 'ring', 'necklace', 'bracelet', 'earring', 'pendant',
                'gem', 'diamond', 'gold', 'silver', 'pearl', 'watch', 'timepiece'],
    'sports': ['sport', 'fitness', 'gym', 'outdoor', 'camping', 'hiking', 'cycling', 'yoga',
               'golf', 'tennis', 'swimming', 'running', 'athletic', 'workout'],
    'pets': ['pet', 'dog', 'cat', 'fish', 'bird', 'aquarium', 'treat', 'leash', 'collar',
             'toy', 'bed', 'carrier', 'grooming'],
    'kids': ['baby', 'kid', 'child', 'toy', 'game', 'nursery', 'infant', 'toddler',
             'playroom', 'stroller', 'diaper'],
    'automotive': ['auto', 'car', 'motor', 'tire', 'vehicle', 'truck', 'motorcycle',
                   'accessory', 'part', 'toolbox', 'garage'],
    'garden': ['garden', 'plant', 'seed', 'flower', 'pot', 'lawn', 'landscape', 'outdoor',
               'patio', 'greenhouse', 'herb'],
    'art': ['art', 'craft', 'paint', 'drawing', 'sculpture', 'gallery', 'print', 'poster',
            'canvas', 'brush', 'ink', 'origami'],
    'coffee': ['coffee', 'espresso', 'roast', 'brew', 'bean', 'cafe', 'latte', 'cappuccino'],
    'wine': ['wine', 'beer', 'spirit', 'liquor', 'whisky', 'vodka', 'rum', 'cocktail',
             'champagne', 'cellar', 'vineyard'],
    'accessories': ['bag', 'handbag', 'wallet', 'belt', 'scarf', 'hat', 'glove', 'sunglasses',
                    'backpack', 'luggage', 'umbrella', 'keychain'],
    'luxury': ['luxury', 'designer', 'premium', 'haute', 'couture', 'exclusive', 'bespoke'],
    'office': ['office', 'desk', 'chair', 'stationery', 'pen', 'notebook', 'planner',
               'organizer', 'filing', 'paper'],
    'books': ['book', 'novel', 'comic', 'manga', 'reading', 'ebook', 'audiobook', 'publishing'],
}

# CVR niche multipliers (based on industry conversion rates)
CVR_MULTIPLIERS = {
    'food': 1.5,       # ~6.11% avg CVR
    'beauty': 1.3,     # ~3.5% avg CVR
    'health': 1.2,     # ~3.0% avg CVR
    'fashion': 1.0,    # ~2.5% avg CVR (baseline)
    'shoes': 1.0,
    'electronics': 0.9,
    'home': 0.9,
    'sports': 0.9,
    'pets': 1.1,
    'kids': 1.0,
    'coffee': 1.4,
    'jewelry': 0.6,    # ~1.19% avg CVR
    'luxury': 0.5,
    'art': 0.7,
    'wine': 1.1,
    'accessories': 0.9,
    'automotive': 0.8,
    'garden': 0.9,
    'office': 0.8,
    'books': 1.0,
    'general': 0.8,
}

# Payment gateway detection patterns
PAYMENT_SIGNATURES = {
    'stripe': ['js.stripe.com', 'stripe.js', 'Stripe(', 'stripe-payment', 'stripe_publishable_key'],
    'paypal': ['paypal.com/sdk', 'paypal-checkout', 'paypal-button', 'paypal.Buttons', 'PayPalScriptProvider'],
    'klarna': ['klarna.com', 'klarna-placement', 'klarna-inline', 'KlarnaOnsiteService'],
    'afterpay': ['afterpay.com', 'afterpay-placement', 'afterpay.js', 'clearpay.com', 'afterpay-widget'],
    'square': ['squareup.com', 'square-payment', 'web-payments-sdk'],
    'braintree': ['braintreegateway.com', 'braintree.client', 'braintree-web'],
    'adyen': ['adyen.com', 'adyen-checkout', 'AdyenCheckout'],
    'shopify_payments': ['shopifypaymentstoken', 'shopify-payment', 'Shopify.Checkout'],
    'apple_pay': ['apple-pay', 'ApplePaySession', 'payment-request-api'],
    'google_pay': ['google-pay', 'google.payments', 'gpay-button'],
    'razorpay': ['razorpay.com', 'Razorpay('],
    'checkout_com': ['checkout.com', 'cko-cdn'],
}

# Platform detection (expanded)
PLATFORM_SIGNATURES = {
    'shopify': ['cdn.shopify.com', 'myshopify.com', 'Shopify.theme', 'shopify-section',
                'shopify-payment', 'Shopify.shop', '/products.json', '_shopify_y'],
    'woocommerce': ['wp-content/plugins/woocommerce', 'woocommerce-page', 'wc-add-to-cart',
                    'wc-block-grid', 'woocommerce-product', 'wc-ajax'],
    'magento': ['Magento_Ui', 'mage/cookies', 'data-mage-init', 'Magento_Customer',
                '/static/version', 'varien/form.js'],
    'prestashop': ['PrestaShop', 'prestashop', 'id_product=', '/modules/ps_',
                   'prestashop-page', 'blockcart'],
    'opencart': ['index.php?route=', 'Powered by OpenCart', 'catalog/view/theme',
                 'opencart-', 'getURLVar'],
    'bigcommerce': ['BigCommerce', 'data-content-region', 'bigcommerce.com',
                    'stencil-utils', 'cornerstone'],
    'squarespace': ['squarespace.com', 'static.squarespace', 'sqsp.com',
                    'squarespace-cdn', 'sqs-block'],
    'wix': ['wixsite.com', 'parastorage.com', '_wix_browser_sess',
            'wix-code-sdk', 'static.wixstatic.com'],
    'volusion': ['Volusion', 'volusion.com', 'a/vo/', 'vspfiles'],
    'shift4shop': ['3dcart', 'shift4shop', 'shift4shop.com'],
    'ecwid': ['ecwid.com', 'ec.cart', 'ecwid-shopping-cart'],
    'weebly': ['weebly.com', 'editmysite.com', 'weebly-footer'],
    'gumroad': ['gumroad.com', 'gumroad-overlay'],
    'sellfy': ['sellfy.com', 'sellfy-embed'],
    'etsy': ['etsy.com', 'etsy-pattern', 'etsystatic.com'],
}


# ============================================================
# PHASE 1: DATA INGESTION & NORMALIZATION
# ============================================================

def load_csv_domains(filepath, source_override=None):
    """Load domains from a CSV file."""
    domains = {}
    if not os.path.exists(filepath):
        logger.warning(f"File not found: {filepath}")
        return domains

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get('domain', row.get('Domain', '')).lower().strip()
            if domain and '.' in domain:
                if domain.startswith('www.'):
                    domain = domain[4:]
                domains[domain] = {
                    'url': row.get('url', f'https://{domain}'),
                    'domain': domain,
                    'platform': row.get('platform', 'unknown'),
                    'niche': row.get('niche', ''),
                    'country': row.get('country', ''),
                    'source': source_override or row.get('source', 'unknown'),
                }
    return domains


def load_ranking_index(filepath, rank_field='GlobalRank', domain_field='Domain'):
    """Load a ranking CSV into a domain->rank dict."""
    index = {}
    if not os.path.exists(filepath):
        return index

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            # Tranco format: rank,domain (no header)
            f.seek(0)
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    try:
                        rank = int(parts[0])
                        domain = parts[1].lower().strip()
                        index[domain] = rank
                    except ValueError:
                        continue
        else:
            for row in reader:
                domain = row.get(domain_field, '').lower().strip()
                try:
                    rank = int(row.get(rank_field, 0))
                except ValueError:
                    rank = 0
                if domain:
                    index[domain] = rank
    return index


def load_tranco_index(filepath):
    """Load Tranco CSV (no header, format: rank,domain)."""
    index = {}
    if not os.path.exists(filepath):
        return index

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                try:
                    rank = int(parts[0])
                    domain = parts[1].lower().strip()
                    index[domain] = rank
                except ValueError:
                    continue
    return index


def phase_ingest():
    """Phase 1: Merge all data sources into unified database."""
    logger.info("=" * 60)
    logger.info("PHASE 1: DATA INGESTION & NORMALIZATION")
    logger.info("=" * 60)

    all_domains = {}
    source_counts = defaultdict(int)

    # 1. Load existing database
    existing_path = os.path.join(OUTPUT_DIR, 'ecommerce_100k_urls.csv')
    existing = load_csv_domains(existing_path)
    all_domains.update(existing)
    source_counts['existing'] = len(existing)
    logger.info(f"Existing database: {len(existing):,} domains")

    # 2. Load CRO.media scraped data
    cro_path = os.path.join(OUTPUT_DIR, 'cro_media_shopify.csv')
    cro = load_csv_domains(cro_path, source_override='cro_media')
    for d, data in cro.items():
        if d not in all_domains:
            all_domains[d] = data
    source_counts['cro_media'] = len(cro)
    logger.info(f"CRO.media: {len(cro):,} domains")

    # 3. Load MyIP.ms scraped data
    myip_path = os.path.join(OUTPUT_DIR, 'myip_shopify.csv')
    myip = load_csv_domains(myip_path, source_override='myip_ms')
    for d, data in myip.items():
        if d not in all_domains:
            all_domains[d] = data
    source_counts['myip_ms'] = len(myip)
    logger.info(f"MyIP.ms: {len(myip):,} domains")

    # 4. Load Tranco ranking
    tranco_path = os.path.join(DATA_DIR, 'top-1m.csv')
    tranco_index = load_tranco_index(tranco_path)
    logger.info(f"Tranco index: {len(tranco_index):,} domains")

    # 5. Load Majestic ranking
    majestic_path = os.path.join(DATA_DIR, 'majestic_million.csv')
    majestic_index = load_ranking_index(majestic_path, rank_field='GlobalRank', domain_field='Domain')
    logger.info(f"Majestic index: {len(majestic_index):,} domains")

    # 6. Enrich with ranking data
    for domain, data in all_domains.items():
        data['tranco_rank'] = tranco_index.get(domain, 0)
        data['majestic_rank'] = majestic_index.get(domain, 0)

    # Export merged database
    merged_path = os.path.join(OUTPUT_DIR, 'merged_all_domains.csv')
    fieldnames = ['url', 'domain', 'platform', 'niche', 'country', 'source',
                  'tranco_rank', 'majestic_rank']

    with open(merged_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for d in sorted(all_domains.values(), key=lambda x: x['domain']):
            writer.writerow(d)

    logger.info(f"\nMerged database: {len(all_domains):,} unique domains → {merged_path}")
    logger.info(f"Source breakdown: {dict(source_counts)}")
    logger.info(f"Domains with Tranco rank: {sum(1 for d in all_domains.values() if d.get('tranco_rank', 0) > 0):,}")
    logger.info(f"Domains with Majestic rank: {sum(1 for d in all_domains.values() if d.get('majestic_rank', 0) > 0):,}")

    # Save indexes for later phases
    json.dump(
        {'tranco': {k: v for k, v in list(tranco_index.items())[:500000]},
         'domain_count': len(all_domains)},
        open(os.path.join(OUTPUT_DIR, 'ranking_meta.json'), 'w')
    )

    return all_domains


# ============================================================
# PHASE 2: PRIMARY VERIFICATION (async /products.json)
# ============================================================

async def verify_shopify_store(session, domain, semaphore, proxy=None):
    """Verify a single Shopify store via /products.json."""
    async with semaphore:
        result = {
            'domain': domain,
            'status': 'unknown',
            'http_status': 0,
            'product_count': 0,
            'product_types': [],
            'tags': [],
            'has_products': False,
            'platform_confirmed': False,
            'is_headless': False,
        }

        url = f'https://{domain}/products.json?limit=5'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'application/json',
        }

        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20, connect=10),
                                   ssl=False, allow_redirects=True) as resp:
                result['http_status'] = resp.status

                if resp.status == 200:
                    try:
                        data = await resp.json(content_type=None)
                        products = data.get('products', [])

                        if products:
                            result['status'] = 'active'
                            result['has_products'] = True
                            result['platform_confirmed'] = True
                            result['product_count'] = len(products)

                            # Extract product types and tags
                            for p in products:
                                pt = p.get('product_type', '').strip()
                                if pt:
                                    result['product_types'].append(pt)
                                tags = p.get('tags', [])
                                if isinstance(tags, list):
                                    result['tags'].extend(tags[:5])
                                elif isinstance(tags, str):
                                    result['tags'].extend([t.strip() for t in tags.split(',')[:5]])

                            # Extract price range
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
                        else:
                            result['status'] = 'empty_store'
                    except Exception:
                        # JSON parse failed — might be HTML redirect
                        text = await resp.text()
                        if 'password' in text.lower():
                            result['status'] = 'password_protected'
                        else:
                            result['status'] = 'not_shopify'

                elif resp.status == 401:
                    result['status'] = 'password_protected'
                elif resp.status == 404:
                    result['status'] = 'not_shopify'
                elif resp.status in (429, 430):
                    result['status'] = 'rate_limited'
                elif resp.status >= 500:
                    result['status'] = 'server_error'
                else:
                    result['status'] = 'inactive'

        except asyncio.TimeoutError:
            result['status'] = 'timeout'
        except aiohttp.ClientError:
            result['status'] = 'connection_error'
        except Exception as e:
            result['status'] = 'error'

        return result


async def verify_headless_store(session, domain, semaphore):
    """Secondary verification for headless Shopify stores."""
    async with semaphore:
        result = {
            'domain': domain,
            'is_headless': False,
            'has_cdn': False,
            'has_shopify_cookie': False,
            'has_storefront_api': False,
            'payment_settings': {},
            'country': '',
            'detected_payments': [],
        }

        url = f'https://{domain}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
        }

        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15),
                                   ssl=False, allow_redirects=True) as resp:
                if resp.status != 200:
                    return result

                html = await resp.text()
                html_lower = html[:50000].lower()
                resp_headers = dict(resp.headers)

                # Check Shopify CDN fingerprint
                if 'cdn.shopify.com' in html_lower:
                    result['has_cdn'] = True
                    result['is_headless'] = True

                # Check Shopify cookies
                cookies_str = resp_headers.get('Set-Cookie', '')
                if '_shopify_y' in cookies_str or '_shopify_s' in cookies_str:
                    result['has_shopify_cookie'] = True

                # Check X-Shopify-Stage header
                if 'x-shopify-stage' in {k.lower(): v for k, v in resp_headers.items()}:
                    result['is_headless'] = True

                # Check for Storefront API calls
                if 'graphql.json' in html_lower and 'storefront' in html_lower:
                    result['has_storefront_api'] = True
                    result['is_headless'] = True

                # Payment detection from DOM
                for gateway, patterns in PAYMENT_SIGNATURES.items():
                    for pattern in patterns:
                        if pattern.lower() in html_lower:
                            result['detected_payments'].append(gateway)
                            break

                # Platform detection fallback
                detected_platform = 'unknown'
                for platform, sigs in PLATFORM_SIGNATURES.items():
                    for sig in sigs:
                        if sig.lower() in html_lower:
                            detected_platform = platform
                            break
                    if detected_platform != 'unknown':
                        break
                result['detected_platform'] = detected_platform

                # Country detection
                country_match = re.search(r'Shopify\.country\s*=\s*["\'](\w{2})["\']', html)
                if country_match:
                    result['country'] = country_match.group(1).upper()

                # E-commerce signal detection
                ecom_signals = 0
                if any(s in html_lower for s in ['add-to-cart', 'add_to_cart', 'addtocart']):
                    ecom_signals += 1
                if any(s in html_lower for s in ['buy-now', 'buy_now', 'buynow']):
                    ecom_signals += 1
                if any(s in html_lower for s in ['/cart', 'shopping-cart', 'cart-count']):
                    ecom_signals += 1
                if any(s in html_lower for s in ['/checkout', 'checkout-button']):
                    ecom_signals += 1
                if re.search(r'\$\s*\d+\.?\d*|\d+\.?\d*\s*€|£\s*\d+', html[:20000]):
                    ecom_signals += 1
                if any(s in html_lower for s in ['"@type":"product"', '"@type": "product"', 'schema.org/product']):
                    ecom_signals += 1

                result['ecom_signal_count'] = ecom_signals

        except Exception:
            pass

        return result


async def phase_verify(input_file=None, max_domains=None, workers=80):
    """Phase 2: Run primary /products.json verification."""
    logger.info("=" * 60)
    logger.info("PHASE 2: PRIMARY VERIFICATION ENGINE")
    logger.info("=" * 60)

    if not input_file:
        # Use mega merged if available, otherwise standard merged
        mega_path = os.path.join(OUTPUT_DIR, 'mega_merged.csv')
        if os.path.exists(mega_path):
            input_file = mega_path
        else:
            input_file = os.path.join(OUTPUT_DIR, 'merged_all_domains.csv')

    # Load domains
    domains_data = load_csv_domains(input_file)
    domains = list(domains_data.keys())

    if max_domains:
        # Prioritize: Tranco-ranked first, then curated, then rest
        def priority(d):
            data = domains_data[d]
            tranco = int(data.get('tranco_rank', 0) or 0)
            source = data.get('source', '')
            if source == 'curated':
                return 0
            if tranco > 0:
                return 1
            if source == 'cro_media':
                return 2
            return 3

        domains.sort(key=priority)
        domains = domains[:max_domains]

    logger.info(f"Verifying {len(domains):,} domains with {workers} concurrent workers...")

    semaphore = asyncio.Semaphore(workers)
    connector = aiohttp.TCPConnector(
        limit=workers, ttl_dns_cache=600, ssl=False,
        enable_cleanup_closed=True, force_close=True
    )

    results = {}
    batch_size = 500
    total_active = 0
    total_products = 0

    async with aiohttp.ClientSession(connector=connector) as session:
        for batch_start in range(0, len(domains), batch_size):
            batch = domains[batch_start:batch_start + batch_size]

            tasks = [verify_shopify_store(session, d, semaphore) for d in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in batch_results:
                if isinstance(res, Exception):
                    continue
                if isinstance(res, dict):
                    domain = res['domain']
                    results[domain] = res
                    if res.get('status') == 'active':
                        total_active += 1
                    if res.get('has_products'):
                        total_products += 1

            batch_end = min(batch_start + batch_size, len(domains))
            logger.info(
                f"Progress: {batch_end:,}/{len(domains):,} | "
                f"Active: {total_active:,} | "
                f"With products: {total_products:,}"
            )
            await asyncio.sleep(0.5)  # Brief pause between batches

    # Run headless/ecommerce detection on ALL non-confirmed domains
    headless_candidates = [
        d for d in domains
        if d in results and results[d].get('status') in ('not_shopify', 'empty_store', 'inactive')
    ]

    if headless_candidates:
        logger.info(f"Running headless detection on {len(headless_candidates):,} high-rank candidates...")

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=workers, ssl=False)) as session:
            for batch_start in range(0, len(headless_candidates), batch_size):
                batch = headless_candidates[batch_start:batch_start + batch_size]
                tasks = [verify_headless_store(session, d, semaphore) for d in batch]
                headless_results = await asyncio.gather(*tasks, return_exceptions=True)

                for res in headless_results:
                    if isinstance(res, dict):
                        domain = res['domain']
                        if domain not in results:
                            continue
                        ecom_signals = res.get('ecom_signal_count', 0)
                        detected_platform = res.get('detected_platform', 'unknown')
                        is_headless = res.get('is_headless', False)
                        is_ecommerce = is_headless or ecom_signals >= 2 or detected_platform != 'unknown'

                        if is_ecommerce:
                            results[domain]['is_headless'] = is_headless
                            results[domain]['status'] = 'active_headless' if is_headless else 'active_ecommerce'
                            results[domain]['platform_confirmed'] = True
                            results[domain]['detected_payments'] = res.get('detected_payments', [])
                            results[domain]['country'] = res.get('country', '')
                            results[domain]['ecom_signal_count'] = ecom_signals
                            if detected_platform != 'unknown':
                                results[domain]['detected_platform'] = detected_platform
                            total_active += 1

    # For ALL domains (regardless of /products.json), do DOM enrichment
    dom_candidates = [
        d for d in domains
        if d in results and results[d].get('status') in ('active', 'active_headless', 'not_shopify')
    ]

    if dom_candidates:
        logger.info(f"Running DOM enrichment on {len(dom_candidates):,} active domains...")

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=workers, ssl=False)) as session:
            for batch_start in range(0, len(dom_candidates), batch_size):
                batch = dom_candidates[batch_start:batch_start + batch_size]
                tasks = [verify_headless_store(session, d, semaphore) for d in batch]
                dom_results = await asyncio.gather(*tasks, return_exceptions=True)

                for res in dom_results:
                    if isinstance(res, dict):
                        domain = res['domain']
                        if domain in results:
                            results[domain]['detected_payments'] = res.get('detected_payments', [])
                            results[domain]['country'] = res.get('country', results[domain].get('country', ''))
                            results[domain]['ecom_signal_count'] = res.get('ecom_signal_count', 0)
                            if res.get('detected_platform', 'unknown') != 'unknown':
                                results[domain]['detected_platform'] = res['detected_platform']

    # Export verification results
    verified_path = os.path.join(OUTPUT_DIR, 'verified_results.csv')
    fieldnames = ['url', 'domain', 'platform', 'niche', 'country', 'source',
                  'tranco_rank', 'majestic_rank', 'status', 'http_status',
                  'has_products', 'product_count', 'product_types', 'tags',
                  'platform_confirmed', 'is_headless', 'detected_payments',
                  'ecom_signal_count', 'min_price', 'max_price']

    with open(verified_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for domain in sorted(results.keys()):
            row = {**domains_data.get(domain, {}), **results[domain]}
            # Serialize lists
            row['product_types'] = '|'.join(row.get('product_types', [])[:5])
            row['tags'] = '|'.join(row.get('tags', [])[:10])
            row['detected_payments'] = '|'.join(row.get('detected_payments', []))
            writer.writerow(row)

    logger.info(f"\nVerification complete:")
    logger.info(f"  Total checked: {len(results):,}")
    logger.info(f"  Active: {total_active:,} ({total_active/max(len(results),1)*100:.1f}%)")
    logger.info(f"  With products: {total_products:,}")
    logger.info(f"  Output: {verified_path}")

    return results


# ============================================================
# PHASE 3: NICHE CLASSIFICATION
# ============================================================

def classify_niche(product_types, tags, domain):
    """Classify store niche from product metadata."""
    text = ' '.join(product_types + tags + [domain]).lower()

    scores = {}
    for niche, keywords in NICHE_MAP.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[niche] = score

    if scores:
        return max(scores, key=scores.get)
    return 'general'


# ============================================================
# PHASE 4: QUALITY SCORE
# ============================================================

def compute_quality_score(domain_data, tranco_max=1000000):
    """Compute composite Quality Score."""
    tranco_rank = int(domain_data.get('tranco_rank', 0) or 0)
    majestic_rank = int(domain_data.get('majestic_rank', 0) or 0)
    product_count = int(domain_data.get('product_count', 0) or 0)
    ecom_signals = int(domain_data.get('ecom_signal_count', 0) or 0)
    niche = domain_data.get('niche', 'general')
    payments = domain_data.get('detected_payments', '')
    if isinstance(payments, str):
        payment_count = len([p for p in payments.split('|') if p])
    else:
        payment_count = len(payments)

    # Traffic score (w1=0.35): inverted normalized Tranco rank
    if tranco_rank > 0:
        traffic_score = max(0, (1 - tranco_rank / tranco_max)) * 100
    elif majestic_rank > 0:
        traffic_score = max(0, (1 - majestic_rank / tranco_max)) * 80  # Majestic weighted less
    else:
        traffic_score = 0

    # Trust/authority score (w2=0.30): combination of ranking presence
    trust_score = 0
    if tranco_rank > 0:
        trust_score += 50
    if majestic_rank > 0:
        trust_score += 30
    if payment_count > 0:
        trust_score += 20

    # Inventory + signals score (w3=0.35)
    inventory_score = min(product_count / 5 * 100, 100)  # 5+ products = max score
    signal_score = min(ecom_signals / 4 * 100, 100)      # 4+ signals = max
    content_score = (inventory_score * 0.6 + signal_score * 0.4)

    # CVR niche multiplier
    cvr = CVR_MULTIPLIERS.get(niche, 0.8)

    # Final QS
    qs = (0.35 * traffic_score + 0.30 * trust_score + 0.35 * content_score) * cvr

    return round(min(qs, 100), 1)


def phase_score():
    """Phase 4: Compute Quality Scores for all verified domains."""
    logger.info("=" * 60)
    logger.info("PHASE 4: QUALITY SCORE COMPUTATION")
    logger.info("=" * 60)

    verified_path = os.path.join(OUTPUT_DIR, 'verified_results.csv')
    if not os.path.exists(verified_path):
        logger.error("No verified results found. Run phase verify first.")
        return

    rows = []
    with open(verified_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['quality_score'] = compute_quality_score(row)

            # Reclassify niche if product data available
            product_types = row.get('product_types', '').split('|')
            tags = row.get('tags', '').split('|')
            if any(product_types) or any(tags):
                row['niche'] = classify_niche(product_types, tags, row['domain'])

            rows.append(row)

    # Sort by quality score
    rows.sort(key=lambda x: float(x.get('quality_score', 0)), reverse=True)

    scored_path = os.path.join(OUTPUT_DIR, 'scored_results.csv')
    fieldnames = list(rows[0].keys()) if rows else []

    with open(scored_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Stats
    active = [r for r in rows if r.get('status') in ('active', 'active_headless', 'active_ecommerce')]
    with_products = [r for r in rows if r.get('has_products') == 'True']
    qs_above_40 = [r for r in active if float(r.get('quality_score', 0)) >= 40]

    logger.info(f"Scored {len(rows):,} domains → {scored_path}")
    logger.info(f"  Active: {len(active):,}")
    logger.info(f"  With products: {len(with_products):,}")
    logger.info(f"  QS ≥ 40: {len(qs_above_40):,}")

    return rows


# ============================================================
# PHASE 5: FILTER & EXPORT
# ============================================================

def phase_export():
    """Phase 5: Filter and export the golden list."""
    logger.info("=" * 60)
    logger.info("PHASE 5: FILTER & EXPORT GOLDEN LIST")
    logger.info("=" * 60)

    scored_path = os.path.join(OUTPUT_DIR, 'scored_results.csv')
    if not os.path.exists(scored_path):
        logger.error("No scored results found. Run phase score first.")
        return

    all_rows = []
    golden = []

    with open(scored_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_rows.append(row)

            status = row.get('status', '')
            qs = float(row.get('quality_score', 0))
            has_products = row.get('has_products', '') == 'True'
            ecom_signals = int(row.get('ecom_signal_count', 0) or 0)
            payments = row.get('detected_payments', '')

            is_active = status in ('active', 'active_headless', 'active_ecommerce')
            has_commerce = has_products or ecom_signals >= 2
            has_payment = bool(payments)

            if is_active and has_commerce and qs >= 20:
                golden.append(row)
            elif is_active and qs >= 10:
                # Include lower-scoring active sites too
                golden.append(row)

    # Sort by QS descending
    golden.sort(key=lambda x: float(x.get('quality_score', 0)), reverse=True)

    # Export CSV
    csv_path = os.path.join(OUTPUT_DIR, 'ecommerce_quality_final.csv')
    export_fields = ['url', 'domain', 'platform', 'niche', 'country', 'quality_score',
                     'tranco_rank', 'majestic_rank', 'product_count', 'detected_payments',
                     'ecom_signal_count', 'status', 'source', 'product_types', 'tags',
                     'min_price', 'max_price']

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=export_fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(golden)

    # Export JSON
    json_path = os.path.join(OUTPUT_DIR, 'ecommerce_quality_final.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump([{k: row.get(k, '') for k in export_fields} for row in golden],
                  f, indent=2, ensure_ascii=False)

    logger.info(f"\n{'='*60}")
    logger.info(f"GOLDEN LIST EXPORT COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"  Total verified: {len(all_rows):,}")
    logger.info(f"  Golden (QS≥40 + active + commerce): {len(golden):,}")
    logger.info(f"  CSV: {csv_path}")
    logger.info(f"  JSON: {json_path}")

    # Phase 6: Stats
    phase_report(golden, all_rows)

    return golden


# ============================================================
# PHASE 6: FINAL REPORT
# ============================================================

def phase_report(golden, all_rows):
    """Phase 6: Generate statistics report."""
    logger.info(f"\n{'='*60}")
    logger.info(f"FINAL STATISTICS REPORT")
    logger.info(f"{'='*60}")

    if not golden:
        logger.info("No golden stores to report on.")
        return

    # Platform breakdown
    platforms = defaultdict(int)
    niches = defaultdict(int)
    countries = defaultdict(int)
    payments = defaultdict(int)
    qs_buckets = defaultdict(int)

    for row in golden:
        platforms[row.get('platform', 'unknown')] += 1
        niches[row.get('niche', 'general')] += 1
        country = row.get('country', '') or 'Unknown'
        countries[country] += 1

        for p in row.get('detected_payments', '').split('|'):
            if p:
                payments[p] += 1

        qs = float(row.get('quality_score', 0))
        if qs >= 70:
            qs_buckets['Elite (≥70)'] += 1
        elif qs >= 55:
            qs_buckets['High (55-69)'] += 1
        else:
            qs_buckets['Quality (40-54)'] += 1

    logger.info(f"\n  Total Golden Stores: {len(golden):,}")

    logger.info(f"\n  By Platform:")
    for p, c in sorted(platforms.items(), key=lambda x: -x[1])[:15]:
        logger.info(f"    {p:25s}: {c:>6,} ({c/len(golden)*100:.1f}%)")

    logger.info(f"\n  By Niche:")
    for n, c in sorted(niches.items(), key=lambda x: -x[1])[:20]:
        logger.info(f"    {n:25s}: {c:>6,} ({c/len(golden)*100:.1f}%)")

    logger.info(f"\n  By Country (top 15):")
    for co, c in sorted(countries.items(), key=lambda x: -x[1])[:15]:
        logger.info(f"    {co:25s}: {c:>6,} ({c/len(golden)*100:.1f}%)")

    logger.info(f"\n  Payment Gateways:")
    for pg, c in sorted(payments.items(), key=lambda x: -x[1]):
        logger.info(f"    {pg:25s}: {c:>6,}")

    logger.info(f"\n  Quality Score Distribution:")
    for bucket, c in sorted(qs_buckets.items()):
        logger.info(f"    {bucket:25s}: {c:>6,}")

    # Top 20 stores
    logger.info(f"\n  Top 20 Stores by Quality Score:")
    for i, row in enumerate(golden[:20], 1):
        logger.info(f"    {i:3d}. {row['domain']:40s} QS={row['quality_score']:>5s}  "
                     f"Niche={row.get('niche',''):15s} Products={row.get('product_count','0')}")


# ============================================================
# MAIN
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='E-Commerce Intelligence Pipeline')
    parser.add_argument('--phase', choices=['ingest', 'verify', 'score', 'export', 'all'],
                        default='all', help='Pipeline phase to run')
    parser.add_argument('--max-domains', type=int, default=None,
                        help='Limit domains to verify (for testing)')
    parser.add_argument('--workers', type=int, default=80,
                        help='Concurrent verification workers')
    args = parser.parse_args()

    if args.phase in ('ingest', 'all'):
        phase_ingest()

    if args.phase in ('verify', 'all'):
        asyncio.run(phase_verify(max_domains=args.max_domains, workers=args.workers))

    if args.phase in ('score', 'all'):
        phase_score()

    if args.phase in ('export', 'all'):
        phase_export()


if __name__ == '__main__':
    main()
