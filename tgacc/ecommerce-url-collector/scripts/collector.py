#!/usr/bin/env python3
"""
E-Commerce URL Collector - Multi-Source Aggregator
Collects e-commerce website URLs from multiple public sources,
categorized by platform and niche.

Usage:
    python collector.py --method all --output ../output/ecommerce_urls.csv
    python collector.py --method google_dorks --platform woocommerce
    python collector.py --method publicwww --platform shopify
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import hashlib
import random
import logging
from datetime import datetime
from urllib.parse import urlparse, quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
import tldextract

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

PLATFORMS = {
    'woocommerce': {
        'signatures': [
            'wp-content/plugins/woocommerce',
            'woocommerce-page',
            'wc-block-grid',
            'woocommerce-product',
            'class="woocommerce"',
        ],
        'google_dorks': [
            'inurl:"/product/" "add to cart" "woocommerce"',
            'inurl:"/shop/" "powered by woocommerce"',
            'inurl:"/cart/" site:*.com "woocommerce"',
            '"wp-content/plugins/woocommerce" -site:wordpress.org -site:github.com',
            'inurl:"/product-category/" "woocommerce"',
        ],
        'publicwww_queries': [
            '"wp-content/plugins/woocommerce"',
            '"woocommerce-page"',
            '"wc-add-to-cart"',
        ],
    },
    'shopify': {
        'signatures': [
            'cdn.shopify.com',
            'myshopify.com',
            'shopify-section',
            'Shopify.theme',
        ],
        'google_dorks': [
            'site:myshopify.com',
            '"powered by shopify" -site:shopify.com',
            'inurl:"cdn.shopify.com" online store',
        ],
        'publicwww_queries': [
            '"cdn.shopify.com"',
            '"Shopify.theme"',
        ],
    },
    'magento': {
        'signatures': [
            'Magento_Ui',
            'mage/cookies',
            '/static/version',
            'Magento_Customer',
            'data-mage-init',
        ],
        'google_dorks': [
            '"powered by magento" online store',
            'inurl:"/customer/account/" "magento"',
            '"Mage.Cookies" site:*.com',
        ],
        'publicwww_queries': [
            '"Magento_Ui"',
            '"mage/cookies"',
        ],
    },
    'opencart': {
        'signatures': [
            'catalog/view/theme',
            'index.php?route=product',
            'index.php?route=common',
            'Powered by OpenCart',
        ],
        'google_dorks': [
            '"powered by opencart" -site:opencart.com',
            'inurl:"index.php?route=product/product"',
            'inurl:"index.php?route=common/home" online store',
        ],
        'publicwww_queries': [
            '"Powered by OpenCart"',
            '"index.php?route=common"',
        ],
    },
    'prestashop': {
        'signatures': [
            'PrestaShop',
            'id_product=',
            'prestashop',
            '/module/blockcontact',
        ],
        'google_dorks': [
            '"powered by prestashop" -site:prestashop.com',
            'inurl:"id_product=" "add to cart"',
            '"prestashop" inurl:"/en/" online store',
        ],
        'publicwww_queries': [
            '"Powered by PrestaShop"',
            '"prestashop"',
        ],
    },
    'bigcommerce': {
        'signatures': [
            'bigcommerce.com',
            'BigCommerce',
            'data-content-region',
        ],
        'google_dorks': [
            '"powered by bigcommerce" online store',
            'site:mybigcommerce.com',
        ],
        'publicwww_queries': [
            '"Powered by BigCommerce"',
        ],
    },
    'joomla_virtuemart': {
        'signatures': [
            'VirtueMart',
            'com_virtuemart',
            'virtuemart',
        ],
        'google_dorks': [
            '"powered by virtuemart" online store',
            'inurl:"com_virtuemart" "add to cart"',
        ],
        'publicwww_queries': [
            '"com_virtuemart"',
            '"VirtueMart"',
        ],
    },
    'oscommerce': {
        'signatures': [
            'osCommerce',
            'osCsid',
        ],
        'google_dorks': [
            '"powered by oscommerce" -site:oscommerce.com',
        ],
        'publicwww_queries': [
            '"Powered by osCommerce"',
        ],
    },
    'squarespace': {
        'signatures': [
            'squarespace.com',
            'static.squarespace',
            'sqsp.com',
        ],
        'google_dorks': [
            '"built with squarespace" online store shop',
        ],
        'publicwww_queries': [
            '"static.squarespace.com"',
        ],
    },
    'wix': {
        'signatures': [
            'wixsite.com',
            'parastorage.com',
            'wix.com',
        ],
        'google_dorks': [
            'site:wixsite.com online store shop',
        ],
        'publicwww_queries': [
            '"parastorage.com"',
        ],
    },
}

NICHES = [
    'fashion', 'clothing', 'apparel', 'shoes', 'jewelry', 'accessories',
    'electronics', 'gadgets', 'computers', 'phones', 'tech',
    'beauty', 'cosmetics', 'skincare', 'health', 'wellness', 'supplements',
    'food', 'grocery', 'organic', 'gourmet', 'beverages', 'coffee',
    'home', 'furniture', 'decor', 'garden', 'kitchen', 'appliances',
    'sports', 'fitness', 'outdoor', 'camping', 'hiking',
    'toys', 'games', 'kids', 'baby', 'children',
    'books', 'music', 'movies', 'entertainment',
    'automotive', 'car', 'motorcycle', 'parts',
    'pets', 'pet supplies', 'dog', 'cat',
    'art', 'crafts', 'handmade', 'vintage',
    'gifts', 'flowers', 'stationery',
    'tools', 'hardware', 'industrial',
    'pharmacy', 'medical', 'dental',
    'watches', 'luxury', 'designer',
    'eyewear', 'glasses', 'sunglasses',
    'lingerie', 'swimwear', 'activewear',
    'vape', 'cbd', 'hemp',
    'wine', 'beer', 'spirits', 'alcohol',
    'print', 'tshirt', 'merch', 'custom',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


class EcommerceCollector:
    """Multi-source e-commerce URL collector."""

    def __init__(self, output_dir='../output'):
        self.urls = {}  # domain -> {url, platform, niche, source, ...}
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def add_url(self, url, platform='unknown', niche='general', source='manual', extra=None):
        """Add a URL to the collection, deduplicating by domain."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            domain = domain.lower().strip().rstrip('/')
            if domain.startswith('www.'):
                domain = domain[4:]
            if not domain or '.' not in domain:
                return False

            if domain not in self.urls:
                self.urls[domain] = {
                    'url': f'https://{domain}',
                    'domain': domain,
                    'platform': platform,
                    'niche': niche,
                    'source': source,
                    'discovered_at': datetime.utcnow().isoformat(),
                    'extra': extra or {},
                }
                return True
            else:
                # Update platform if previously unknown
                if self.urls[domain]['platform'] == 'unknown' and platform != 'unknown':
                    self.urls[domain]['platform'] = platform
                return False
        except Exception:
            return False

    # ========================================
    # SOURCE 1: CURATED/KNOWN STORES
    # ========================================
    def collect_curated_stores(self):
        """Add well-known curated e-commerce stores from public showcases."""
        logger.info("Collecting curated/known stores...")

        shopify_stores = [
            # Fashion & Clothing
            ('hiutdenim.co.uk', 'shopify', 'fashion'),
            ('tentree.com', 'shopify', 'fashion'),
            ('maguireshoes.com', 'shopify', 'shoes'),
            ('the-outrage.com', 'shopify', 'fashion'),
            ('adoredvintage.com', 'shopify', 'vintage'),
            ('goodfair.com', 'shopify', 'fashion'),
            ('kirrinfinch.com', 'shopify', 'fashion'),
            ('rothys.com', 'shopify', 'shoes'),
            ('beefcakeswimwear.com', 'shopify', 'swimwear'),
            ('suta.in', 'shopify', 'fashion'),
            ('allbirds.com', 'shopify', 'shoes'),
            ('camillebrinch.com', 'shopify', 'jewelry'),
            ('velasca.com', 'shopify', 'shoes'),
            ('troubadourgoods.com', 'shopify', 'accessories'),
            ('unitedbyblue.com', 'shopify', 'fashion'),
            ('manitobah.com', 'shopify', 'shoes'),
            # Food & Drink
            ('blkandbold.com', 'shopify', 'coffee'),
            ('flybyjing.com', 'shopify', 'food'),
            ('vervecoffee.com', 'shopify', 'coffee'),
            ('tazachocolate.com', 'shopify', 'food'),
            ('yeungmancooking.com', 'shopify', 'food'),
            ('flourist.com', 'shopify', 'food'),
            # Beauty & Wellness
            ('thehoneypot.co', 'shopify', 'beauty'),
            ('packagefreeshop.com', 'shopify', 'beauty'),
            ('beautybakerie.com', 'shopify', 'beauty'),
            ('cheekbonebeauty.com', 'shopify', 'beauty'),
            ('meowmeowtweet.com', 'shopify', 'beauty'),
            ('beneathyourmask.com', 'shopify', 'beauty'),
            ('freshheritage.com', 'shopify', 'beauty'),
            ('thenimetyou.com', 'shopify', 'beauty'),
            ('lastobject.com', 'shopify', 'beauty'),
            ('tofinosoapcompany.com', 'shopify', 'beauty'),
            ('satyaorganics.com', 'shopify', 'beauty'),
            # Art & Decor
            ('uppercasemagazine.com', 'shopify', 'art'),
            ('artisaire.com', 'shopify', 'art'),
            ('terrebleu.ca', 'shopify', 'home'),
            ('silkandwillow.com', 'shopify', 'home'),
            ('goodeeworld.com', 'shopify', 'home'),
            # Electronics
            ('bruvi.com', 'shopify', 'electronics'),
            ('pelacase.ca', 'shopify', 'electronics'),
            ('cowboy.com', 'shopify', 'electronics'),
            # Others
            ('givemetap.com', 'shopify', 'accessories'),
            ('lunchskins.com', 'shopify', 'home'),
            ('bebemoss.com', 'shopify', 'toys'),
            ('madeincookware.com', 'shopify', 'kitchen'),
            ('lootcrate.com', 'shopify', 'entertainment'),
            ('potgang.co.uk', 'shopify', 'garden'),
            ('cocofloss.com', 'shopify', 'health'),
            # Major Shopify stores
            ('gymshark.com', 'shopify', 'fitness'),
            ('kyliecosmetics.com', 'shopify', 'beauty'),
            ('fashionnova.com', 'shopify', 'fashion'),
            ('colorpop.com', 'shopify', 'beauty'),
            ('jeffreestarcosmetics.com', 'shopify', 'beauty'),
            ('stevemadden.com', 'shopify', 'shoes'),
            ('ruggable.com', 'shopify', 'home'),
            ('bombas.com', 'shopify', 'fashion'),
            ('skims.com', 'shopify', 'fashion'),
            ('figs.com', 'shopify', 'fashion'),
            ('brooklinen.com', 'shopify', 'home'),
            ('chubbies.com', 'shopify', 'fashion'),
            ('untuckit.com', 'shopify', 'fashion'),
            ('bajaao.com', 'shopify', 'music'),
            ('puravidabracelets.com', 'shopify', 'jewelry'),
            ('mvmtwatches.com', 'shopify', 'watches'),
            ('hauslabs.com', 'shopify', 'beauty'),
            ('deathwishcoffee.com', 'shopify', 'coffee'),
            ('negativeunderwear.com', 'shopify', 'lingerie'),
            ('drinkmudwtr.com', 'shopify', 'beverages'),
            ('ridge.com', 'shopify', 'accessories'),
            ('hellotushy.com', 'shopify', 'home'),
            ('catbird.com', 'shopify', 'jewelry'),
            ('mejuri.com', 'shopify', 'jewelry'),
            ('tatcha.com', 'shopify', 'beauty'),
            ('drinkags.com', 'shopify', 'beverages'),
            ('wearpact.com', 'shopify', 'fashion'),
            ('olipop.com', 'shopify', 'beverages'),
            ('glossier.com', 'shopify', 'beauty'),
            ('cettire.com', 'shopify', 'luxury'),
            ('rfrk.com', 'shopify', 'food'),
            ('hydroflask.com', 'shopify', 'accessories'),
            ('peets.com', 'shopify', 'coffee'),
            ('drinkag1.com', 'shopify', 'health'),
        ]

        woocommerce_stores = [
            # Top WooCommerce stores
            ('aioseo.com', 'woocommerce', 'tech'),
            ('coolpc.com.tw', 'woocommerce', 'electronics'),
            ('rankmath.com', 'woocommerce', 'tech'),
            ('yoast.com', 'woocommerce', 'tech'),
            ('wp-rocket.me', 'woocommerce', 'tech'),
            ('creativefabrica.com', 'woocommerce', 'art'),
            ('screamingfrog.co.uk', 'woocommerce', 'tech'),
            ('dnsdumpster.com', 'woocommerce', 'tech'),
            ('wpml.org', 'woocommerce', 'tech'),
            ('advancedcustomfields.com', 'woocommerce', 'tech'),
            ('adminmart.com', 'woocommerce', 'tech'),
            # Well-known WooCommerce stores
            ('weber.com', 'woocommerce', 'kitchen'),
            ('airstream.com', 'woocommerce', 'automotive'),
            ('clickbank.com', 'woocommerce', 'tech'),
            ('singer.com', 'woocommerce', 'home'),
            ('dr-adventures.com', 'woocommerce', 'sports'),
            ('hoodsly.com', 'woocommerce', 'home'),
            ('coffeebeandirect.com', 'woocommerce', 'coffee'),
            ('onnit.com', 'woocommerce', 'supplements'),
            ('snowboard-asylum.com', 'woocommerce', 'sports'),
            ('beardbrand.com', 'woocommerce', 'beauty'),
            ('sodastream.com', 'woocommerce', 'kitchen'),
            ('overclockers.co.uk', 'woocommerce', 'electronics'),
            ('roots.com', 'woocommerce', 'fashion'),
            ('portlandleather.com', 'woocommerce', 'accessories'),
            ('daelmans.com', 'woocommerce', 'food'),
            ('wandrd.com', 'woocommerce', 'accessories'),
        ]

        magento_stores = [
            ('nike.com', 'magento', 'fashion'),
            ('coca-cola.com', 'magento', 'beverages'),
            ('ford.com', 'magento', 'automotive'),
            ('hp.com', 'magento', 'electronics'),
            ('landrover.com', 'magento', 'automotive'),
            ('bulkbarn.ca', 'magento', 'food'),
            ('tommyhilfiger.com', 'magento', 'fashion'),
            ('olimp-labs.com', 'magento', 'supplements'),
            ('hersheys.com', 'magento', 'food'),
            ('warbyparker.com', 'magento', 'eyewear'),
            ('pepe-jeans.com', 'magento', 'fashion'),
            ('shopdisney.com', 'magento', 'toys'),
            ('sigma-global.com', 'magento', 'electronics'),
            ('monin.com', 'magento', 'food'),
            ('ghd.com', 'magento', 'beauty'),
            ('end.com', 'magento', 'fashion'),
            ('jackjones.com', 'magento', 'fashion'),
            ('bottegaveneta.com', 'magento', 'luxury'),
            ('omegawatches.com', 'magento', 'watches'),
            ('byredo.com', 'magento', 'beauty'),
            ('bulgari.com', 'magento', 'luxury'),
            ('paul-smith.com', 'magento', 'fashion'),
            ('oliverpeoples.com', 'magento', 'eyewear'),
            ('crocs.com', 'magento', 'shoes'),
            ('lenovo.com', 'magento', 'electronics'),
            ('canon.com', 'magento', 'electronics'),
            ('vizio.com', 'magento', 'electronics'),
        ]

        opencart_stores = [
            ('techport.ru', 'opencart', 'electronics'),
            ('brantshop.kz', 'opencart', 'fashion'),
            ('hongkiat.com', 'opencart', 'tech'),
            ('mycomputerworks.com', 'opencart', 'electronics'),
            ('thaimart.in', 'opencart', 'general'),
        ]

        prestashop_stores = [
            ('emmezeta.hr', 'prestashop', 'home'),
            ('shop.mango.com', 'prestashop', 'fashion'),
            ('zippo.com', 'prestashop', 'accessories'),
            ('salomon.com', 'prestashop', 'sports'),
        ]

        bigcommerce_stores = [
            ('skullcandy.com', 'bigcommerce', 'electronics'),
            ('soylent.com', 'bigcommerce', 'food'),
            ('bliss.com', 'bigcommerce', 'beauty'),
            ('qualtrics.com', 'bigcommerce', 'tech'),
            ('camelbak.com', 'bigcommerce', 'accessories'),
            ('blackdiamondequipment.com', 'bigcommerce', 'sports'),
        ]

        all_stores = (shopify_stores + woocommerce_stores + magento_stores +
                      opencart_stores + prestashop_stores + bigcommerce_stores)

        count = 0
        for domain, platform, niche in all_stores:
            if self.add_url(f'https://{domain}', platform, niche, 'curated'):
                count += 1

        logger.info(f"Added {count} curated stores")
        return count

    # ========================================
    # SOURCE 2: GOOGLE SEARCH COLLECTION
    # ========================================
    def collect_from_google(self, platform=None, max_per_query=100):
        """Collect e-commerce URLs using Google Search API / scraping."""
        logger.info("Collecting from Google search...")
        platforms_to_search = {platform: PLATFORMS[platform]} if platform else PLATFORMS
        count = 0

        for plat_name, plat_config in platforms_to_search.items():
            for dork in plat_config.get('google_dorks', []):
                try:
                    urls = self._google_search(dork, max_results=max_per_query)
                    for url in urls:
                        niche = self._detect_niche_from_url(url)
                        if self.add_url(url, plat_name, niche, 'google'):
                            count += 1
                    time.sleep(random.uniform(2, 5))
                except Exception as e:
                    logger.warning(f"Google search error for '{dork}': {e}")

        logger.info(f"Added {count} URLs from Google search")
        return count

    def _google_search(self, query, max_results=100):
        """Perform a Google search and extract URLs from results."""
        urls = []
        encoded = quote_plus(query)
        for start in range(0, max_results, 10):
            try:
                url = f'https://www.google.com/search?q={encoded}&start={start}&num=10'
                resp = self.session.get(url, timeout=15)
                soup = BeautifulSoup(resp.text, 'html.parser')
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    if '/url?q=' in href:
                        actual_url = href.split('/url?q=')[1].split('&')[0]
                        if not any(x in actual_url for x in [
                            'google.com', 'youtube.com', 'facebook.com',
                            'twitter.com', 'wikipedia.org', 'reddit.com'
                        ]):
                            urls.append(actual_url)
                time.sleep(random.uniform(1, 3))
            except Exception as e:
                logger.debug(f"Search page error: {e}")
                break
        return urls

    # ========================================
    # SOURCE 3: COMMON CRAWL DATA
    # ========================================
    def collect_from_commoncrawl(self, platform=None, max_results=5000):
        """Search Common Crawl index for e-commerce sites."""
        logger.info("Collecting from Common Crawl index...")
        cc_api = 'https://index.commoncrawl.org/CC-MAIN-2025-08-index'
        count = 0
        platforms_to_search = {platform: PLATFORMS[platform]} if platform else PLATFORMS

        for plat_name, plat_config in platforms_to_search.items():
            for sig in plat_config['signatures'][:2]:  # Limit queries
                try:
                    params = {
                        'url': f'*.com',
                        'output': 'json',
                        'limit': min(max_results, 1000),
                        'filter': f'=mime:text/html',
                    }
                    resp = self.session.get(cc_api, params=params, timeout=30)
                    if resp.status_code == 200:
                        for line in resp.text.strip().split('\n'):
                            try:
                                data = json.loads(line)
                                url = data.get('url', '')
                                niche = self._detect_niche_from_url(url)
                                if self.add_url(url, plat_name, niche, 'commoncrawl'):
                                    count += 1
                            except json.JSONDecodeError:
                                continue
                    time.sleep(1)
                except Exception as e:
                    logger.debug(f"Common Crawl error: {e}")

        logger.info(f"Added {count} URLs from Common Crawl")
        return count

    # ========================================
    # SOURCE 4: WAPPALYZER-STYLE DETECTION
    # ========================================
    def detect_platform(self, url):
        """Detect the e-commerce platform of a given URL."""
        try:
            resp = self.session.get(url, timeout=10, allow_redirects=True)
            html = resp.text.lower()

            for platform, config in PLATFORMS.items():
                for sig in config['signatures']:
                    if sig.lower() in html:
                        return platform
            return 'unknown'
        except Exception:
            return 'unknown'

    # ========================================
    # SOURCE 5: DIRECTORY SCRAPING
    # ========================================
    def collect_from_directories(self):
        """Scrape e-commerce directories and showcases."""
        logger.info("Collecting from directories and showcases...")
        count = 0

        directories = [
            'https://www.shopify.com/blog/shopify-stores',
            'https://woocommerce.com/showcase/',
            'https://www.prestashop.com/en/showcase',
            'https://www.opencart.com/index.php?route=cms/feature',
            'https://www.bigcommerce.com/case-studies/',
        ]

        for directory_url in directories:
            try:
                resp = self.session.get(directory_url, timeout=15)
                soup = BeautifulSoup(resp.text, 'html.parser')

                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    parsed = urlparse(href)
                    if parsed.netloc and parsed.scheme in ('http', 'https'):
                        ext = tldextract.extract(href)
                        if ext.registered_domain:
                            # Skip known non-store domains
                            skip = ['shopify.com', 'woocommerce.com', 'prestashop.com',
                                    'opencart.com', 'bigcommerce.com', 'wordpress.org',
                                    'github.com', 'youtube.com', 'google.com',
                                    'facebook.com', 'twitter.com', 'instagram.com',
                                    'cdn.shopify.com']
                            if ext.registered_domain not in skip:
                                platform = self._guess_platform_from_directory(directory_url)
                                niche = self._detect_niche_from_url(href)
                                if self.add_url(href, platform, niche, 'directory'):
                                    count += 1
                time.sleep(2)
            except Exception as e:
                logger.warning(f"Directory scraping error for {directory_url}: {e}")

        logger.info(f"Added {count} URLs from directories")
        return count

    # ========================================
    # SOURCE 6: BULK NICHE SEARCH
    # ========================================
    def collect_niche_stores(self, max_per_niche=50):
        """Search for e-commerce stores by niche category."""
        logger.info("Collecting stores by niche...")
        count = 0

        niche_queries = []
        for niche in NICHES[:30]:  # Limit to top niches
            for platform in ['shopify', 'woocommerce', 'magento']:
                niche_queries.append((niche, platform))

        for niche, platform in niche_queries:
            try:
                query = f'"{niche}" "online store" "{platform}" -site:{platform}.com'
                urls = self._google_search(query, max_results=max_per_niche)
                for url in urls:
                    if self.add_url(url, platform, niche, 'niche_search'):
                        count += 1
                time.sleep(random.uniform(2, 5))
            except Exception as e:
                logger.debug(f"Niche search error: {e}")

        logger.info(f"Added {count} URLs from niche search")
        return count

    # ========================================
    # SOURCE 7: DOMAIN LISTS / TLD CRAWLING
    # ========================================
    def collect_from_domain_lists(self):
        """Collect from publicly available domain lists (Majestic Million, etc.)."""
        logger.info("Collecting from domain lists (Majestic Million)...")
        count = 0

        try:
            # Majestic Million - top 1M domains, many are e-commerce
            url = 'https://downloads.majestic.com/majestic_million.csv'
            resp = self.session.get(url, timeout=60, stream=True)
            if resp.status_code == 200:
                lines = resp.iter_lines(decode_unicode=True)
                header = next(lines)  # Skip header
                for i, line in enumerate(lines):
                    if i > 50000:  # Check top 50k domains
                        break
                    try:
                        parts = line.split(',')
                        if len(parts) > 2:
                            domain = parts[2].strip().strip('"')
                            self.add_url(f'https://{domain}', 'unknown', 'general', 'majestic_million')
                            count += 1
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Majestic Million download error: {e}")

        logger.info(f"Added {count} URLs from domain lists")
        return count

    # ========================================
    # HELPERS
    # ========================================
    def _detect_niche_from_url(self, url):
        """Attempt to detect niche from URL path and domain."""
        url_lower = url.lower()
        for niche in NICHES:
            if niche in url_lower:
                return niche
        return 'general'

    def _guess_platform_from_directory(self, directory_url):
        """Guess platform from directory source URL."""
        url_lower = directory_url.lower()
        for platform in PLATFORMS:
            if platform.replace('_', '') in url_lower:
                return platform
        if 'shopify' in url_lower:
            return 'shopify'
        if 'woocommerce' in url_lower or 'wordpress' in url_lower:
            return 'woocommerce'
        return 'unknown'

    # ========================================
    # VERIFICATION
    # ========================================
    def verify_urls(self, sample_size=None, workers=20):
        """Verify URLs are active by checking HTTP status."""
        logger.info("Verifying URLs...")
        domains = list(self.urls.keys())
        if sample_size:
            domains = random.sample(domains, min(sample_size, len(domains)))

        verified = 0
        failed = 0

        def check_url(domain):
            url = self.urls[domain]['url']
            try:
                resp = self.session.head(url, timeout=8, allow_redirects=True)
                if resp.status_code < 400:
                    self.urls[domain]['status'] = 'active'
                    self.urls[domain]['http_status'] = resp.status_code
                    return True
                else:
                    self.urls[domain]['status'] = 'inactive'
                    self.urls[domain]['http_status'] = resp.status_code
                    return False
            except Exception:
                self.urls[domain]['status'] = 'unreachable'
                self.urls[domain]['http_status'] = 0
                return False

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(check_url, d): d for d in domains}
            for future in as_completed(futures):
                if future.result():
                    verified += 1
                else:
                    failed += 1

        logger.info(f"Verified: {verified} active, {failed} failed")
        return verified, failed

    # ========================================
    # OUTPUT
    # ========================================
    def export_csv(self, filename='ecommerce_urls.csv', active_only=False):
        """Export collected URLs to CSV."""
        filepath = os.path.join(self.output_dir, filename)
        fieldnames = ['url', 'domain', 'platform', 'niche', 'source', 'status', 'http_status', 'discovered_at']

        rows = []
        for domain, data in self.urls.items():
            if active_only and data.get('status') not in ('active', None):
                continue
            rows.append({
                'url': data['url'],
                'domain': data['domain'],
                'platform': data['platform'],
                'niche': data['niche'],
                'source': data['source'],
                'status': data.get('status', 'unverified'),
                'http_status': data.get('http_status', ''),
                'discovered_at': data['discovered_at'],
            })

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        logger.info(f"Exported {len(rows)} URLs to {filepath}")
        return filepath

    def export_json(self, filename='ecommerce_urls.json'):
        """Export collected URLs to JSON."""
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(list(self.urls.values()), f, indent=2, ensure_ascii=False)
        logger.info(f"Exported {len(self.urls)} URLs to {filepath}")
        return filepath

    def print_stats(self):
        """Print collection statistics."""
        total = len(self.urls)
        by_platform = {}
        by_niche = {}
        by_source = {}

        for data in self.urls.values():
            plat = data['platform']
            by_platform[plat] = by_platform.get(plat, 0) + 1
            niche = data['niche']
            by_niche[niche] = by_niche.get(niche, 0) + 1
            source = data['source']
            by_source[source] = by_source.get(source, 0) + 1

        print(f"\n{'='*60}")
        print(f"  E-Commerce URL Collection Statistics")
        print(f"{'='*60}")
        print(f"  Total unique domains: {total:,}")
        print(f"\n  By Platform:")
        for p, c in sorted(by_platform.items(), key=lambda x: -x[1]):
            print(f"    {p:20s}: {c:,}")
        print(f"\n  By Niche (top 15):")
        for n, c in sorted(by_niche.items(), key=lambda x: -x[1])[:15]:
            print(f"    {n:20s}: {c:,}")
        print(f"\n  By Source:")
        for s, c in sorted(by_source.items(), key=lambda x: -x[1]):
            print(f"    {s:20s}: {c:,}")
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='E-Commerce URL Collector')
    parser.add_argument('--method', default='all',
                        choices=['all', 'curated', 'google', 'directories', 'niche', 'commoncrawl', 'domains'],
                        help='Collection method(s) to use')
    parser.add_argument('--platform', default=None,
                        choices=list(PLATFORMS.keys()),
                        help='Filter by platform')
    parser.add_argument('--output', default='../output',
                        help='Output directory')
    parser.add_argument('--verify', action='store_true',
                        help='Verify URLs are active')
    parser.add_argument('--format', default='csv',
                        choices=['csv', 'json', 'both'],
                        help='Output format')

    args = parser.parse_args()
    collector = EcommerceCollector(output_dir=args.output)

    methods = {
        'curated': collector.collect_curated_stores,
        'directories': collector.collect_from_directories,
        'google': lambda: collector.collect_from_google(platform=args.platform),
        'niche': collector.collect_niche_stores,
        'commoncrawl': lambda: collector.collect_from_commoncrawl(platform=args.platform),
        'domains': collector.collect_from_domain_lists,
    }

    if args.method == 'all':
        for name, func in methods.items():
            try:
                func()
            except Exception as e:
                logger.error(f"Error in {name}: {e}")
    else:
        methods[args.method]()

    if args.verify:
        collector.verify_urls()

    collector.print_stats()

    if args.format in ('csv', 'both'):
        collector.export_csv()
    if args.format in ('json', 'both'):
        collector.export_json()


if __name__ == '__main__':
    main()
