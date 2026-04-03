#!/usr/bin/env python3
"""
E-Commerce URL Verifier - Checks URLs are active and detects platforms.
Run on a sample or full list to validate and enrich the database.

Usage:
    python verify_urls.py --sample 500 --workers 30
    python verify_urls.py --all --workers 50
"""

import csv
import json
import os
import sys
import time
import random
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

PLATFORM_SIGNATURES = {
    'shopify': [
        'cdn.shopify.com', 'myshopify.com', 'Shopify.theme',
        'shopify-section', 'shopify-payment', 'Shopify.shop'
    ],
    'woocommerce': [
        'wp-content/plugins/woocommerce', 'woocommerce-page',
        'wc-add-to-cart', 'wc-block-grid', 'woocommerce-product'
    ],
    'magento': [
        'Magento_Ui', 'mage/cookies', 'data-mage-init',
        'Magento_Customer', '/static/version'
    ],
    'prestashop': [
        'PrestaShop', 'prestashop', 'id_product=',
        '/modules/ps_', 'prestashop-page'
    ],
    'opencart': [
        'index.php?route=', 'Powered by OpenCart',
        'catalog/view/theme'
    ],
    'bigcommerce': [
        'BigCommerce', 'data-content-region',
        'bigcommerce.com'
    ],
    'squarespace': [
        'squarespace.com', 'static.squarespace',
        'sqsp.com', 'squarespace-cdn'
    ],
    'wix': [
        'wixsite.com', 'parastorage.com',
        '_wix_browser_sess', 'wix-code-sdk'
    ],
}


def verify_url(url, timeout=8):
    """Verify a single URL and detect platform."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        }
        resp = requests.get(url, timeout=timeout, allow_redirects=True, headers=headers)
        status = resp.status_code

        if status >= 400:
            return {'status': 'inactive', 'http_status': status, 'platform': 'unknown'}

        # Detect platform from response
        html = resp.text[:30000].lower() if resp.text else ''
        detected_platform = 'unknown'

        for platform, sigs in PLATFORM_SIGNATURES.items():
            for sig in sigs:
                if sig.lower() in html:
                    detected_platform = platform
                    break
            if detected_platform != 'unknown':
                break

        # Check for any e-commerce indicators
        ecom_indicators = ['add-to-cart', 'add_to_cart', 'checkout', 'shopping-cart',
                           'buy-now', 'add to cart', 'purchase', 'price', 'cart']
        is_ecommerce = any(ind in html for ind in ecom_indicators)

        return {
            'status': 'active',
            'http_status': status,
            'platform': detected_platform,
            'is_ecommerce': is_ecommerce,
        }

    except requests.exceptions.Timeout:
        return {'status': 'timeout', 'http_status': 0, 'platform': 'unknown'}
    except requests.exceptions.ConnectionError:
        return {'status': 'connection_error', 'http_status': 0, 'platform': 'unknown'}
    except Exception as e:
        return {'status': 'error', 'http_status': 0, 'platform': 'unknown', 'error': str(e)}


def verify_database(input_file, sample_size=None, workers=30):
    """Verify URLs from the database."""
    logger.info(f"Loading {input_file}...")

    rows = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    logger.info(f"Loaded {len(rows):,} URLs")

    if sample_size and sample_size < len(rows):
        rows = random.sample(rows, sample_size)
        logger.info(f"Sampled {sample_size:,} URLs for verification")

    results = {}
    active = 0
    inactive = 0
    ecommerce_confirmed = 0
    platform_detected = 0

    def process_row(row):
        url = row['url']
        result = verify_url(url)
        return row, result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_row, row): row for row in rows}
        completed = 0

        for future in as_completed(futures):
            completed += 1
            row, result = future.result()
            domain = row['domain']

            row['verified_status'] = result['status']
            row['http_status'] = result['http_status']

            if result['platform'] != 'unknown':
                row['platform'] = result['platform']
                platform_detected += 1

            if result.get('is_ecommerce'):
                row['verified_ecommerce'] = 'yes'
                ecommerce_confirmed += 1

            if result['status'] == 'active':
                active += 1
            else:
                inactive += 1

            results[domain] = row

            if completed % 50 == 0:
                logger.info(f"Progress: {completed}/{len(rows)} | Active: {active} | E-commerce: {ecommerce_confirmed} | Platform detected: {platform_detected}")

    # Export verified results
    verified_file = input_file.replace('.csv', '_verified.csv')
    fieldnames = ['url', 'domain', 'platform', 'niche', 'country', 'source',
                  'verified_status', 'http_status', 'verified_ecommerce']

    with open(verified_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for domain, row in sorted(results.items()):
            writer.writerow(row)

    logger.info(f"\nVerification Results:")
    logger.info(f"  Total checked: {len(rows):,}")
    logger.info(f"  Active: {active:,} ({active/len(rows)*100:.1f}%)")
    logger.info(f"  Inactive: {inactive:,} ({inactive/len(rows)*100:.1f}%)")
    logger.info(f"  E-commerce confirmed: {ecommerce_confirmed:,} ({ecommerce_confirmed/len(rows)*100:.1f}%)")
    logger.info(f"  Platform detected: {platform_detected:,} ({platform_detected/len(rows)*100:.1f}%)")
    logger.info(f"  Output: {verified_file}")

    return verified_file


def main():
    import argparse
    parser = argparse.ArgumentParser(description='E-Commerce URL Verifier')
    parser.add_argument('--input', default=os.path.join(OUTPUT_DIR, 'ecommerce_100k_urls.csv'))
    parser.add_argument('--sample', type=int, default=200, help='Sample size (0 for all)')
    parser.add_argument('--workers', type=int, default=30, help='Concurrent workers')
    args = parser.parse_args()

    sample = args.sample if args.sample > 0 else None
    verify_database(args.input, sample_size=sample, workers=args.workers)


if __name__ == '__main__':
    main()
