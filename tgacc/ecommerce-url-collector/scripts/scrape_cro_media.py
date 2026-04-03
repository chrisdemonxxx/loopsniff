#!/usr/bin/env python3
"""
CRO.media Shopify Store Scraper
Scrapes verified Shopify store domains from cro.media/all-shopify-stores/
"""

import re
import csv
import os
import sys
import time
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}


def scrape_cro_page(page_num):
    """Scrape a single CRO.media page for Shopify store domains."""
    if page_num == 1:
        url = 'https://cro.media/all-shopify-stores/'
    else:
        url = f'https://cro.media/all-shopify-stores/page/{page_num}/'

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return [], False

        html = resp.text
        # Extract domains from links like: [domain.com](https://www.domain.com?ref=cro.media...)
        domains = re.findall(r'\[([a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\]\(https?://(?:www\.)?', html)

        # Also extract from #### [domain.com] headers
        domains += re.findall(r'####\s*\[([a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\]', html)

        # Extract themes
        themes = re.findall(r'Shopify Theme Used:\*\*\s*\[([^\]]+)\]', html)

        # Deduplicate
        unique = list(dict.fromkeys(d.lower().strip() for d in domains if '.' in d and len(d) > 3))

        has_more = len(unique) > 0
        return [(d, 'shopify') for d in unique], has_more

    except Exception as e:
        logger.warning(f"Page {page_num} error: {e}")
        return [], False


def scrape_cro_media(max_pages=600, workers=5):
    """Scrape CRO.media with pagination."""
    all_stores = {}
    page = 1
    empty_streak = 0

    logger.info("Starting CRO.media Shopify store scraping...")

    while page <= max_pages and empty_streak < 5:
        stores, has_more = scrape_cro_page(page)

        for domain, platform in stores:
            if domain not in all_stores:
                all_stores[domain] = {
                    'url': f'https://{domain}',
                    'domain': domain,
                    'platform': 'shopify',
                    'niche': '',
                    'country': '',
                    'source': 'cro_media',
                }

        if not stores:
            empty_streak += 1
        else:
            empty_streak = 0

        if page % 25 == 0:
            logger.info(f"Page {page}: {len(all_stores):,} total stores collected")

        page += 1
        time.sleep(random.uniform(0.5, 1.5))

    # Export
    output_path = os.path.join(OUTPUT_DIR, 'cro_media_shopify.csv')
    fieldnames = ['url', 'domain', 'platform', 'niche', 'country', 'source']

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in sorted(all_stores.values(), key=lambda x: x['domain']):
            writer.writerow(d)

    logger.info(f"CRO.media scraping complete: {len(all_stores):,} Shopify stores → {output_path}")
    return all_stores


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-pages', type=int, default=600)
    args = parser.parse_args()
    scrape_cro_media(max_pages=args.max_pages)
