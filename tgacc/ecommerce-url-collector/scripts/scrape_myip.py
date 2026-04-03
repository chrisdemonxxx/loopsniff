#!/usr/bin/env python3
"""
MyIP.ms Shopify Hosting Domain Scraper
Extracts domains hosted on Shopify Inc infrastructure from myip.ms
"""

import re
import csv
import os
import time
import logging
import random

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Shopify Inc hosting pages on myip.ms
MYIP_URLS = [
    'https://myip.ms/browse/sites/1/own/376714',           # Shopify Inc primary
    'https://myip.ms/browse/sites/1/ownerID/376714/ownerID_A/1',  # Shopify Inc extended
]


def scrape_myip_page(url):
    """Scrape a single myip.ms page for domains."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')

        domains = []
        # Find domain links in the hosting table
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)

            # myip.ms links to site info pages with domain names
            if '/view/sites/' in href or '/info/whois/' in href:
                # Extract domain from link text
                if '.' in text and len(text) > 3 and ' ' not in text:
                    domain = text.lower().strip().rstrip('/')
                    if re.match(r'^[a-z0-9][a-z0-9.-]+\.[a-z]{2,}$', domain):
                        domains.append(domain)

        # Also extract from raw text patterns
        text_domains = re.findall(
            r'(?<![/\w])([a-zA-Z0-9][a-zA-Z0-9-]+\.[a-zA-Z]{2,})(?![/\w])',
            resp.text
        )
        for d in text_domains:
            d = d.lower().strip()
            if d.endswith(('.com', '.co.uk', '.net', '.org', '.io', '.store', '.shop', '.ca', '.de', '.fr')):
                if d not in ('myip.ms', 'shopify.com', 'cloudflare.com', 'google.com'):
                    domains.append(d)

        return list(set(domains))

    except Exception as e:
        logger.warning(f"myip.ms scrape error: {e}")
        return []


def scrape_myip_paginated(base_url, max_pages=100):
    """Scrape multiple pages from myip.ms."""
    all_domains = set()

    for page in range(1, max_pages + 1):
        if page == 1:
            url = base_url
        else:
            url = f"{base_url}/page/{page}"

        domains = scrape_myip_page(url)
        if not domains:
            logger.info(f"No domains on page {page}, stopping")
            break

        before = len(all_domains)
        all_domains.update(domains)
        new = len(all_domains) - before

        if page % 10 == 0:
            logger.info(f"Page {page}: +{new} new, {len(all_domains):,} total")

        time.sleep(random.uniform(1.0, 3.0))

    return all_domains


def scrape_myip():
    """Main myip.ms scraping function."""
    logger.info("Starting MyIP.ms Shopify domain scraping...")

    all_domains = set()
    for url in MYIP_URLS:
        logger.info(f"Scraping: {url}")
        domains = scrape_myip_paginated(url, max_pages=50)
        all_domains.update(domains)
        logger.info(f"Collected {len(all_domains):,} unique domains so far")

    # Export
    output_path = os.path.join(OUTPUT_DIR, 'myip_shopify.csv')
    fieldnames = ['url', 'domain', 'platform', 'niche', 'country', 'source']

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for domain in sorted(all_domains):
            writer.writerow({
                'url': f'https://{domain}',
                'domain': domain,
                'platform': 'shopify',
                'niche': '',
                'country': '',
                'source': 'myip_ms',
            })

    logger.info(f"MyIP.ms scraping complete: {len(all_domains):,} Shopify domains → {output_path}")
    return all_domains


if __name__ == '__main__':
    scrape_myip()
