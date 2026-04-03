#!/usr/bin/env python3
"""
E-Commerce URL Builder - Builds 100K+ e-commerce URL list
from Majestic Million + curated seeds + heuristic filtering.
"""

import csv
import json
import os
import sys
import re
import random
import logging
from datetime import datetime
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# E-COMMERCE DOMAIN HEURISTICS
# ============================================================

# Words commonly found in e-commerce domain names
ECOMMERCE_KEYWORDS = [
    'shop', 'store', 'buy', 'deal', 'sale', 'outlet', 'mart', 'market',
    'bazaar', 'bazar', 'mall', 'wholesale', 'retail', 'merch', 'goods',
    'supply', 'supplies', 'depot', 'warehouse', 'direct', 'express',
    'fashion', 'style', 'wear', 'cloth', 'apparel', 'dress', 'shoe',
    'beauty', 'cosmetic', 'skin', 'hair', 'makeup', 'fragrance',
    'jewel', 'gem', 'diamond', 'gold', 'silver', 'watch',
    'tech', 'electronic', 'gadget', 'phone', 'computer', 'laptop',
    'food', 'grocer', 'organic', 'gourmet', 'kitchen', 'cook',
    'pet', 'dog', 'cat', 'fish', 'bird',
    'baby', 'kid', 'toy', 'game',
    'sport', 'fitness', 'gym', 'outdoor', 'camp', 'hike',
    'auto', 'car', 'motor', 'tire', 'part',
    'book', 'music', 'art', 'craft', 'gift',
    'health', 'vitamin', 'supplement', 'pharma', 'medical',
    'home', 'furniture', 'decor', 'garden', 'tool', 'hardware',
    'wine', 'beer', 'spirit', 'liquor', 'coffee', 'tea',
    'flower', 'plant', 'seed',
    'print', 'custom', 'design', 'photo',
    'travel', 'luggage', 'bag',
    'eyewear', 'glasses', 'lens', 'optical',
    'lingerie', 'underwear', 'intimates',
    'cbd', 'vape', 'hemp',
    'fabric', 'textile', 'yarn', 'sewing',
    'candle', 'soap', 'bath',
    'sneaker', 'trainer', 'boot',
    'handbag', 'purse', 'wallet',
    'mattress', 'bed', 'pillow', 'blanket',
    'rug', 'carpet', 'curtain',
    'lamp', 'light', 'bulb',
    'paint', 'wallpaper', 'tile',
    'plumb', 'electric', 'hvac',
    'aquarium', 'terrarium', 'vivarium',
    'equestrian', 'horse', 'saddle',
    'fishing', 'hunting', 'archery',
    'skiing', 'snowboard', 'surf',
    'golf', 'tennis', 'soccer', 'baseball', 'basketball',
    'music', 'instrument', 'guitar', 'piano', 'drum',
    'camera', 'lens', 'tripod',
    'drone', 'rc', 'hobby',
    'sticker', 'poster', 'sign',
    'party', 'balloon', 'costume',
    'wedding', 'bridal', 'engagement',
    'nutrition', 'protein', 'whey',
]

# Domains that are definitely NOT e-commerce
NON_ECOMMERCE_PATTERNS = [
    'google', 'facebook', 'youtube', 'twitter', 'instagram', 'linkedin',
    'reddit', 'wikipedia', 'github', 'stackoverflow', 'quora', 'medium',
    'tumblr', 'pinterest', 'tiktok', 'snapchat', 'whatsapp', 'telegram',
    'discord', 'slack', 'zoom', 'teams', 'skype',
    'apple.com', 'microsoft.com', 'amazon.com', 'aws.', 'azure.',
    'cloudflare', 'akamai', 'fastly', 'cloudfront',
    'gov', 'edu', 'mil', 'org',
    'bbc.', 'cnn.', 'nytimes', 'reuters', 'apnews',
    'bank', 'chase', 'wellsfargo', 'citibank', 'hsbc',
    'paypal', 'stripe', 'square',
    'uber', 'lyft', 'airbnb', 'booking',
    'netflix', 'hulu', 'disney', 'hbo', 'spotify',
    'dropbox', 'box.com', 'onedrive',
    'wordpress.org', 'drupal.org', 'joomla.org',
    'w3.org', 'ietf.org', 'ieee.org',
    'gravatar', 'akismet', 'jetpack',
    'analytics', 'adsense', 'adwords',
    'cdn.', 'static.', 'assets.', 'img.', 'images.',
    'api.', 'app.', 'admin.', 'login.',
    'mail.', 'email.', 'smtp.', 'imap.',
    'ftp.', 'ssh.', 'vpn.', 'proxy.',
    'localhost', '127.0.0.1', '0.0.0.0',
    'test.', 'dev.', 'staging.', 'demo.',
    '.gov', '.edu', '.mil',
]

# Known e-commerce TLDs
ECOMMERCE_TLDS = [
    '.com', '.co.uk', '.ca', '.com.au', '.co.nz', '.in', '.de',
    '.fr', '.it', '.es', '.nl', '.be', '.se', '.dk', '.no', '.fi',
    '.pl', '.cz', '.at', '.ch', '.ie', '.pt', '.gr', '.ru',
    '.com.br', '.mx', '.co', '.cl', '.ar', '.pe',
    '.jp', '.kr', '.sg', '.hk', '.tw', '.ph', '.my', '.th', '.id',
    '.za', '.ae', '.sa', '.il', '.tr',
    '.shop', '.store', '.online', '.boutique', '.market',
]

# Platform signature to niche mapping
NICHE_KEYWORDS = {
    'fashion': ['fashion', 'cloth', 'apparel', 'wear', 'dress', 'style', 'jeans', 'denim', 'shirt', 'pant', 'suit', 'coat', 'jacket', 'sweater', 'hoodie', 'tshirt'],
    'shoes': ['shoe', 'boot', 'sneaker', 'sandal', 'heel', 'loafer', 'slipper', 'footwear'],
    'electronics': ['electronic', 'tech', 'gadget', 'phone', 'computer', 'laptop', 'tablet', 'camera', 'audio', 'speaker', 'headphone', 'tv', 'monitor'],
    'beauty': ['beauty', 'cosmetic', 'makeup', 'skincare', 'skin', 'hair', 'fragrance', 'perfume', 'nail'],
    'food': ['food', 'grocer', 'gourmet', 'organic', 'snack', 'candy', 'chocolate', 'cheese', 'meat', 'seafood', 'bakery', 'spice'],
    'home': ['home', 'furniture', 'decor', 'interior', 'kitchen', 'bath', 'bed', 'mattress', 'pillow', 'rug', 'curtain', 'lamp'],
    'sports': ['sport', 'fitness', 'gym', 'outdoor', 'camp', 'hike', 'bike', 'cycle', 'run', 'swim', 'yoga', 'golf', 'tennis'],
    'jewelry': ['jewel', 'ring', 'necklace', 'bracelet', 'earring', 'gem', 'diamond', 'gold', 'silver'],
    'health': ['health', 'vitamin', 'supplement', 'pharma', 'medical', 'wellness', 'nutrition'],
    'pets': ['pet', 'dog', 'cat', 'fish', 'bird', 'animal', 'vet'],
    'kids': ['baby', 'kid', 'child', 'toy', 'game', 'nursery', 'infant', 'toddler'],
    'automotive': ['auto', 'car', 'motor', 'tire', 'vehicle', 'truck', 'motorcycle'],
    'books': ['book', 'read', 'novel', 'comic', 'manga', 'publish', 'library'],
    'wine': ['wine', 'beer', 'spirit', 'liquor', 'whisky', 'vodka', 'rum', 'cocktail'],
    'coffee': ['coffee', 'espresso', 'roast', 'brew', 'bean', 'cafe'],
    'garden': ['garden', 'plant', 'seed', 'flower', 'nursery', 'lawn', 'landscape'],
    'art': ['art', 'craft', 'paint', 'draw', 'sculpture', 'gallery', 'print', 'poster'],
    'luxury': ['luxury', 'designer', 'premium', 'haute', 'couture', 'exclusive'],
    'accessories': ['accessory', 'bag', 'wallet', 'belt', 'scarf', 'hat', 'glove', 'sunglasses'],
    'watches': ['watch', 'clock', 'timepiece', 'chrono'],
}


def is_likely_ecommerce(domain):
    """Heuristic check if a domain is likely an e-commerce site."""
    domain_lower = domain.lower()

    # Skip known non-ecommerce
    for pattern in NON_ECOMMERCE_PATTERNS:
        if pattern in domain_lower:
            return False

    # Check for e-commerce keywords in domain
    for keyword in ECOMMERCE_KEYWORDS:
        if keyword in domain_lower:
            return True

    # Check for e-commerce TLD
    for tld in ['.shop', '.store', '.online', '.boutique', '.market']:
        if domain_lower.endswith(tld):
            return True

    return False


def detect_niche(domain):
    """Detect niche from domain name."""
    domain_lower = domain.lower()
    for niche, keywords in NICHE_KEYWORDS.items():
        for kw in keywords:
            if kw in domain_lower:
                return niche
    return 'general'


def load_majestic_million(filepath, limit=1000000):
    """Load domains from Majestic Million CSV."""
    logger.info(f"Loading Majestic Million (limit={limit:,})...")
    domains = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= limit:
                    break
                domain = row.get('Domain', '').strip().lower()
                tld = row.get('TLD', '').strip().lower()
                rank = int(row.get('GlobalRank', 0))
                if domain and '.' in domain:
                    domains[domain] = {
                        'url': f'https://{domain}',
                        'domain': domain,
                        'tld': tld,
                        'rank': rank,
                    }
        logger.info(f"Loaded {len(domains):,} domains from Majestic Million")
    except Exception as e:
        logger.error(f"Error loading Majestic Million: {e}")
    return domains


def load_curated_seeds():
    """Load curated seed data from the seed_generator module."""
    # Import from seed_generator
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from seed_generator import SEED_STORES, NICHE_DOMAINS

    seeds = {}

    for domain, platform, niche, country in SEED_STORES:
        domain = domain.lower().strip()
        seeds[domain] = {
            'url': f'https://{domain}',
            'domain': domain,
            'platform': platform,
            'niche': niche,
            'country': country,
            'source': 'curated',
        }

    for niche, domain_list in NICHE_DOMAINS.items():
        for domain in domain_list:
            domain = domain.lower().strip()
            if '/' in domain:
                domain = domain.split('/')[0]
            if domain not in seeds:
                seeds[domain] = {
                    'url': f'https://{domain}',
                    'domain': domain,
                    'platform': 'unknown',
                    'niche': niche,
                    'country': 'US',
                    'source': 'niche_list',
                }

    logger.info(f"Loaded {len(seeds):,} curated seed domains")
    return seeds


def filter_ecommerce_from_majestic(majestic_domains, curated_seeds):
    """Filter Majestic Million for likely e-commerce domains."""
    logger.info("Filtering Majestic Million for e-commerce domains...")

    ecommerce = {}
    # Commercial TLDs likely to have e-commerce
    commercial_tlds = {
        'com', 'co.uk', 'de', 'fr', 'it', 'es', 'nl', 'be', 'se', 'dk',
        'no', 'fi', 'pl', 'cz', 'at', 'ch', 'ie', 'pt', 'ru',
        'com.br', 'mx', 'co', 'com.au', 'co.nz', 'in', 'ca',
        'jp', 'kr', 'sg', 'hk', 'tw', 'ph', 'my', 'th', 'id',
        'za', 'ae', 'sa', 'il', 'tr',
        'shop', 'store', 'online', 'boutique', 'market',
    }

    for domain, data in majestic_domains.items():
        # Skip if already in curated seeds
        if domain in curated_seeds:
            continue

        tld = data.get('tld', '')

        # Must be a commercial TLD
        if tld not in commercial_tlds:
            continue

        # Check if likely e-commerce
        if is_likely_ecommerce(domain):
            niche = detect_niche(domain)
            ecommerce[domain] = {
                'url': f'https://{domain}',
                'domain': domain,
                'platform': 'unknown',
                'niche': niche,
                'country': '',
                'source': 'majestic_filtered',
                'rank': data.get('rank', 0),
            }

    logger.info(f"Found {len(ecommerce):,} likely e-commerce domains from Majestic")
    return ecommerce


def generate_additional_domains():
    """Generate additional e-commerce domains using common patterns."""
    logger.info("Generating additional domains from patterns...")

    prefixes = ['the', 'my', 'best', 'top', 'great', 'super', 'mega', 'ultra', 'pro', 'prime', 'elite', 'royal', 'global', 'world', 'smart', 'easy', 'quick', 'fast', 'cool', 'blue', 'green', 'red', 'gold', 'silver', 'fresh', 'pure', 'natural', 'organic', 'eco', 'zen', 'luxe', 'vibe', 'urban', 'modern', 'classic', 'vintage', 'retro', 'indie', 'artisan', 'craft']

    suffixes = ['shop', 'store', 'mart', 'hub', 'spot', 'world', 'zone', 'land', 'place', 'corner', 'market', 'depot', 'outlet', 'direct', 'central', 'express', 'supply', 'source', 'bay', 'box', 'lab', 'locker', 'vault', 'rack', 'hive']

    niches_short = ['fashion', 'beauty', 'tech', 'pet', 'baby', 'sport', 'home', 'food', 'book', 'art', 'shoe', 'bag', 'watch', 'jewel', 'gift', 'toy', 'wine', 'coffee', 'fitness', 'health', 'auto', 'garden', 'tool', 'craft', 'music', 'game', 'outdoor', 'kitchen', 'candle', 'soap', 'fabric', 'yarn', 'bead']

    tlds = ['.com', '.co.uk', '.ca', '.com.au', '.de', '.fr', '.store', '.shop', '.online']

    domains = {}
    for niche in niches_short:
        for suffix in suffixes[:15]:
            domain = f'{niche}{suffix}.com'
            domains[domain] = {
                'url': f'https://{domain}',
                'domain': domain,
                'platform': 'unknown',
                'niche': niche,
                'country': '',
                'source': 'generated_pattern',
            }

        for prefix in prefixes[:10]:
            domain = f'{prefix}{niche}.com'
            domains[domain] = {
                'url': f'https://{domain}',
                'domain': domain,
                'platform': 'unknown',
                'niche': niche,
                'country': '',
                'source': 'generated_pattern',
            }

        for tld in tlds[1:5]:
            domain = f'{niche}store{tld}'
            domains[domain] = {
                'url': f'https://{domain}',
                'domain': domain,
                'platform': 'unknown',
                'niche': niche,
                'country': '',
                'source': 'generated_pattern',
            }

    # Regional variations
    countries = {
        'us': '.com', 'uk': '.co.uk', 'ca': '.ca', 'au': '.com.au',
        'de': '.de', 'fr': '.fr', 'it': '.it', 'es': '.es',
        'nl': '.nl', 'se': '.se', 'dk': '.dk', 'no': '.no',
    }

    for country, tld in countries.items():
        for niche in niches_short[:15]:
            domain = f'{niche}shop{tld}'
            domains[domain] = {
                'url': f'https://{domain}',
                'domain': domain,
                'platform': 'unknown',
                'niche': niche,
                'country': country.upper(),
                'source': 'generated_regional',
            }

    logger.info(f"Generated {len(domains):,} additional pattern domains")
    return domains


def build_final_database():
    """Build the final 100K URL database."""

    # Step 1: Load curated seeds
    curated = load_curated_seeds()

    # Step 2: Load and filter Majestic Million
    majestic_path = os.path.join(DATA_DIR, 'majestic_million.csv')
    majestic = {}
    if os.path.exists(majestic_path):
        majestic_raw = load_majestic_million(majestic_path)
        majestic = filter_ecommerce_from_majestic(majestic_raw, curated)

    # Step 3: Generate additional domains
    generated = generate_additional_domains()

    # Step 4: Merge all sources
    all_urls = {}

    # Curated seeds get priority
    all_urls.update(curated)

    # Then Majestic filtered
    for domain, data in majestic.items():
        if domain not in all_urls:
            all_urls[domain] = data

    # Then generated patterns
    for domain, data in generated.items():
        if domain not in all_urls:
            all_urls[domain] = data

    logger.info(f"Total merged domains: {len(all_urls):,}")

    # Step 5: Export
    export_database(all_urls, 'ecommerce_100k_urls.csv')

    return all_urls


def export_database(urls_dict, filename):
    """Export to CSV and JSON."""
    csv_path = os.path.join(OUTPUT_DIR, filename)
    json_path = csv_path.replace('.csv', '.json')

    fieldnames = ['url', 'domain', 'platform', 'niche', 'country', 'source']
    rows = []

    for domain, data in urls_dict.items():
        rows.append({
            'url': data.get('url', f'https://{domain}'),
            'domain': domain,
            'platform': data.get('platform', 'unknown'),
            'niche': data.get('niche', 'general'),
            'country': data.get('country', ''),
            'source': data.get('source', 'unknown'),
        })

    # Sort by source priority and niche
    source_priority = {'curated': 0, 'niche_list': 1, 'majestic_filtered': 2, 'generated_pattern': 3, 'generated_regional': 4}
    rows.sort(key=lambda x: (source_priority.get(x['source'], 9), x['niche'], x['domain']))

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    logger.info(f"Exported {len(rows):,} URLs to {csv_path}")
    logger.info(f"Exported {len(rows):,} URLs to {json_path}")

    # Statistics
    by_platform = defaultdict(int)
    by_niche = defaultdict(int)
    by_source = defaultdict(int)

    for row in rows:
        by_platform[row['platform']] += 1
        by_niche[row['niche']] += 1
        by_source[row['source']] += 1

    print(f"\n{'='*65}")
    print(f"  E-COMMERCE URL DATABASE - FINAL STATISTICS")
    print(f"{'='*65}")
    print(f"  Total unique domains: {len(rows):,}")
    print(f"  Output CSV: {csv_path}")
    print(f"  Output JSON: {json_path}")
    print(f"\n  By Platform:")
    for p, c in sorted(by_platform.items(), key=lambda x: -x[1]):
        pct = c / len(rows) * 100
        print(f"    {p:25s}: {c:>6,} ({pct:.1f}%)")
    print(f"\n  By Niche (top 25):")
    for n, c in sorted(by_niche.items(), key=lambda x: -x[1])[:25]:
        pct = c / len(rows) * 100
        print(f"    {n:25s}: {c:>6,} ({pct:.1f}%)")
    print(f"\n  By Source:")
    for s, c in sorted(by_source.items(), key=lambda x: -x[1]):
        pct = c / len(rows) * 100
        print(f"    {s:25s}: {c:>6,} ({pct:.1f}%)")
    print(f"{'='*65}\n")


if __name__ == '__main__':
    build_final_database()
