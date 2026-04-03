#!/usr/bin/env python3
"""
Merge all verified e-commerce sources into a single golden list.
Sources:
  1. verified_full.csv (run_verify.py output - main scan)
  2. verified_ecom_remaining.csv (fast_ecom_scan.py - keyword-filtered remaining)
  3. verified_crux_ecom.csv (fast_ecom_scan.py - CRUX dataset)
  4. storeleads_verified.csv (pre-verified StoreLead Shopify stores)
  5. cro_media_shopify.csv (CRO.media scraper)
"""
import csv
import os
import sys
import argparse
from collections import Counter

def load_main_verify(path):
    """Load e-commerce domains from run_verify.py output."""
    domains = {}
    if not os.path.exists(path):
        return domains
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get('domain', '').lower().strip()
            if not domain:
                continue
            has_products = row.get('has_products') == 'True'
            product_count = int(row.get('product_count', 0) or 0)
            ecom_signals = int(row.get('ecom_signal_count', 0) or 0)
            
            # E-commerce criteria: has products OR high ecom signals
            if has_products or product_count > 0 or ecom_signals >= 2:
                domains[domain] = {
                    'domain': domain,
                    'url': row.get('url', f'https://{domain}'),
                    'platform': row.get('platform', 'unknown'),
                    'has_products': has_products,
                    'product_count': product_count,
                    'ecom_signals': ecom_signals,
                    'detected_payments': row.get('detected_payments', ''),
                    'tags': row.get('tags', ''),
                    'min_price': row.get('min_price', ''),
                    'max_price': row.get('max_price', ''),
                    'source': row.get('source', 'main_verify'),
                    'tranco_rank': row.get('tranco_rank', ''),
                    'majestic_rank': row.get('majestic_rank', ''),
                    'monthly_visits': '',
                }
    return domains

def load_fast_scan(path, source_name):
    """Load e-commerce domains from fast_ecom_scan.py output."""
    domains = {}
    if not os.path.exists(path):
        return domains
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get('domain', '').lower().strip()
            if not domain:
                continue
            if row.get('status') == 'active_ecommerce':
                domains[domain] = {
                    'domain': domain,
                    'url': f'https://{domain}',
                    'platform': row.get('platform', 'unknown'),
                    'has_products': row.get('has_products') == 'True',
                    'product_count': int(row.get('product_count', 0) or 0),
                    'ecom_signals': int(row.get('ecom_signals', 0) or 0),
                    'detected_payments': '',
                    'tags': '',
                    'min_price': '',
                    'max_price': '',
                    'source': source_name,
                    'tranco_rank': '',
                    'majestic_rank': '',
                    'monthly_visits': '',
                }
    return domains

def load_storeleads(path):
    """Load pre-verified StoreLead Shopify stores."""
    domains = {}
    if not os.path.exists(path):
        return domains
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get('domain', '').lower().strip()
            if not domain:
                continue
            domains[domain] = {
                'domain': domain,
                'url': f'https://{domain}',
                'platform': 'shopify',
                'has_products': True,
                'product_count': 0,
                'ecom_signals': 5,
                'detected_payments': '',
                'tags': '',
                'min_price': '',
                'max_price': '',
                'source': 'storeleads',
                'tranco_rank': '',
                'majestic_rank': '',
                'monthly_visits': row.get('monthly_visits', row.get('estimated_monthly_visits', '')),
            }
    return domains

def load_cro_media(path):
    """Load CRO.media Shopify stores."""
    domains = {}
    if not os.path.exists(path):
        return domains
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get('domain', '').lower().strip()
            if not domain:
                continue
            domains[domain] = {
                'domain': domain,
                'url': f'https://{domain}',
                'platform': 'shopify',
                'has_products': True,
                'product_count': 0,
                'ecom_signals': 3,
                'detected_payments': '',
                'tags': '',
                'min_price': '',
                'max_price': '',
                'source': 'cro_media',
                'tranco_rank': '',
                'majestic_rank': '',
                'monthly_visits': '',
            }
    return domains

def compute_quality_score(entry):
    """Compute a quality score (0-100) for ranking."""
    score = 0
    
    # Platform detection (known platform = higher quality)
    platform = entry.get('platform', '').lower()
    if platform in ('shopify', 'woocommerce', 'magento', 'bigcommerce'):
        score += 25
    elif platform not in ('', 'unknown'):
        score += 15
    
    # Products detected
    if entry.get('has_products'):
        score += 20
    pc = entry.get('product_count', 0)
    if isinstance(pc, str):
        pc = int(pc) if pc.isdigit() else 0
    if pc > 0:
        score += min(15, pc * 3)
    
    # E-commerce signals
    ecom = entry.get('ecom_signals', 0)
    if isinstance(ecom, str):
        ecom = int(ecom) if ecom.isdigit() else 0
    score += min(15, ecom * 3)
    
    # Payment detection
    payments = entry.get('detected_payments', '')
    if payments:
        score += 10
    
    # Traffic data (from storeleads)
    visits = entry.get('monthly_visits', '')
    if visits:
        try:
            v = int(float(visits))
            if v > 1000000: score += 15
            elif v > 100000: score += 12
            elif v > 50000: score += 10
            elif v > 10000: score += 7
            elif v > 1000: score += 3
        except: pass
    
    # Ranking data
    for rank_field in ('tranco_rank', 'majestic_rank'):
        rank = entry.get(rank_field, '')
        if rank:
            try:
                r = int(rank)
                if r > 0:
                    if r < 10000: score += 10
                    elif r < 100000: score += 5
                    elif r < 500000: score += 2
            except: pass
    
    # Source reliability bonus
    source = entry.get('source', '')
    if source == 'storeleads': score += 5
    elif source == 'cro_media': score += 3
    elif 'curated' in source or 'seed' in source: score += 5
    
    return min(100, score)


def main():
    parser = argparse.ArgumentParser(description='Merge all e-commerce sources')
    parser.add_argument('--output', default='output/ecommerce_golden_100k.csv')
    parser.add_argument('--limit', type=int, default=100000, help='Max URLs to export')
    parser.add_argument('--min-score', type=int, default=0, help='Min quality score')
    parser.add_argument('--stats-only', action='store_true', help='Only show stats')
    args = parser.parse_args()
    
    print("=== Loading sources ===")
    
    # Load all sources
    src1 = load_main_verify('output/verified_full.csv')
    print(f"  Main verify (top): {len(src1):,} e-commerce domains")
    
    src1b = load_main_verify('output/verified_bottom.csv')
    print(f"  Main verify (bottom): {len(src1b):,} e-commerce domains")
    
    src2 = load_fast_scan('output/verified_ecom_remaining.csv', 'fast_ecom_remaining')
    print(f"  Fast ecom remaining: {len(src2):,} e-commerce domains")
    
    src3 = load_fast_scan('output/verified_crux_ecom.csv', 'crux_ecom')
    print(f"  CRUX scan: {len(src3):,} e-commerce domains")
    
    src4 = load_storeleads('output/storeleads_verified.csv')
    print(f"  StoreLead: {len(src4):,} e-commerce domains")
    
    src5 = load_cro_media('output/cro_media_shopify.csv')
    print(f"  CRO.media: {len(src5):,} e-commerce domains")
    
    # Borderline domains (active with ≥1 ecom signal from main verify)
    src6 = load_main_verify('output/borderline_ecom.csv')
    print(f"  Borderline ecom: {len(src6):,} e-commerce domains")
    
    # Reverse IP Shopify stores (pre-verified via Shopify IP range)
    src7 = {}
    for rip_path in ['output/reverse_ip_shopify.csv', 'output/reverse_ip_shopify_expanded.csv']:
        if os.path.exists(rip_path):
            with open(rip_path) as f:
                for row in csv.DictReader(f):
                    d = row.get('domain', '').lower().strip()
                    if d and d not in src7:
                        src7[d] = {
                            'domain': d, 'url': f'https://{d}',
                            'platform': 'shopify', 'has_products': True,
                            'product_count': 0, 'ecom_signals': 3,
                            'detected_payments': '', 'tags': '',
                            'min_price': '', 'max_price': '',
                            'source': 'reverse_ip_shopify',
                            'tranco_rank': '', 'majestic_rank': '',
                            'monthly_visits': '',
                        }
    print(f"  Reverse IP Shopify: {len(src7):,} e-commerce domains")
    
    # HuggingFace verified Shopify stores
    src8 = load_fast_scan('output/huggingface_verified.csv', 'huggingface')
    if not src8:
        src8 = {}
        hf_path = 'output/huggingface_verified.csv'
        if os.path.exists(hf_path):
            with open(hf_path) as f:
                for row in csv.DictReader(f):
                    d = row.get('domain', '').lower().strip()
                    if d:
                        src8[d] = {
                            'domain': d, 'url': f'https://{d}',
                            'platform': 'shopify', 'has_products': True,
                            'product_count': 0, 'ecom_signals': 3,
                            'detected_payments': '', 'tags': '',
                            'min_price': '', 'max_price': '',
                            'source': 'huggingface',
                            'tranco_rank': '', 'majestic_rank': '',
                            'monthly_visits': '',
                        }
    print(f"  HuggingFace Shopify: {len(src8):,} e-commerce domains")
    
    # crt.sh scan results
    src9 = load_fast_scan('output/verified_crtsh.csv', 'crtsh')
    print(f"  crt.sh scan: {len(src9):,} e-commerce domains")
    
    # CRUX ultra scan results
    src10 = load_fast_scan('output/verified_crux_ultra.csv', 'crux_ultra')
    print(f"  CRUX ultra scan: {len(src10):,} e-commerce domains")
    
    # GitHub Gist Shopify stores
    src11 = load_fast_scan('output/gist_shopify.csv', 'github_gist')
    if not src11:
        src11 = {}
        gist_path = 'output/gist_shopify.csv'
        if os.path.exists(gist_path):
            with open(gist_path) as f:
                for row in csv.DictReader(f):
                    d = row.get('domain', '').lower().strip()
                    if d:
                        src11[d] = {
                            'domain': d, 'url': f'https://{d}',
                            'platform': 'shopify', 'has_products': True,
                            'product_count': 0, 'ecom_signals': 3,
                            'detected_payments': '', 'tags': '',
                            'min_price': '', 'max_price': '',
                            'source': 'github_gist',
                            'tranco_rank': '', 'majestic_rank': '',
                            'monthly_visits': '',
                        }
    print(f"  GitHub Gist Shopify: {len(src11):,} e-commerce domains")
    
    # Subfinder myshopify.com subdomains
    src12 = {}
    sf_path = 'output/subfinder_shopify.csv'
    if os.path.exists(sf_path):
        with open(sf_path) as f:
            for row in csv.DictReader(f):
                d = row.get('domain', '').lower().strip()
                if d:
                    src12[d] = {
                        'domain': d, 'url': f'https://{d}',
                        'platform': 'shopify', 'has_products': True,
                        'product_count': 0, 'ecom_signals': 2,
                        'detected_payments': '', 'tags': '',
                        'min_price': '', 'max_price': '',
                        'source': 'subfinder',
                        'tranco_rank': '', 'majestic_rank': '',
                        'monthly_visits': '',
                    }
    print(f"  Subfinder Shopify: {len(src12):,} e-commerce domains")
    
    # Platform-detected extras (domains with recognized ecom platform but below signal threshold)
    src13 = {}
    pe_path = 'output/platform_detected_extras.csv'
    if os.path.exists(pe_path):
        with open(pe_path) as f:
            for row in csv.DictReader(f):
                d = row.get('domain', '').lower().strip()
                if d:
                    src13[d] = {
                        'domain': d, 'url': row.get('url', f'https://{d}'),
                        'platform': row.get('platform', 'unknown'),
                        'has_products': row.get('has_products', 'False') == 'True',
                        'product_count': int(row.get('product_count', 0) or 0),
                        'ecom_signals': max(int(row.get('ecom_signals', 0) or 0), 1),
                        'detected_payments': row.get('detected_payments', ''),
                        'tags': row.get('tags', ''),
                        'min_price': row.get('min_price', ''),
                        'max_price': row.get('max_price', ''),
                        'source': 'platform_detected',
                        'tranco_rank': '', 'majestic_rank': '',
                        'monthly_visits': '',
                    }
    print(f"  Platform-detected extras: {len(src13):,} e-commerce domains")
    
    # CRUX ultra2 scan results
    src14 = load_fast_scan('output/verified_crux_ultra2.csv', 'crux_ultra2')
    print(f"  CRUX ultra2 scan: {len(src14):,} e-commerce domains")
    
    # Source 15: Wayback CDX confirmed ecommerce platform stores
    src15 = {}
    if os.path.exists('output/wayback_confirmed_ecom.csv'):
        with open('output/wayback_confirmed_ecom.csv') as f:
            for row in csv.DictReader(f):
                d = row.get('domain', '').lower().strip()
                if d and d not in src15:
                    src15[d] = {
                        'domain': d, 'url': f'https://{d}',
                        'platform': row.get('platform', 'unknown'),
                        'has_products': True, 'product_count': 0,
                        'ecom_signals': 1, 'detected_payments': '',
                        'tags': '', 'min_price': '', 'max_price': '',
                        'source': 'wayback_platform', 'tranco_rank': '',
                        'majestic_rank': '', 'monthly_visits': '',
                    }
    print(f"  Wayback platform stores: {len(src15):,} e-commerce domains")
    
    # Source 16: Wayback CDX myshopify domains
    src16 = {}
    if os.path.exists('output/wayback_myshopify.csv'):
        with open('output/wayback_myshopify.csv') as f:
            for row in csv.DictReader(f):
                d = row.get('domain', '').lower().strip()
                if d and d not in src16:
                    src16[d] = {
                        'domain': d, 'url': f'https://{d}',
                        'platform': 'shopify', 'has_products': True,
                        'product_count': 0, 'ecom_signals': 1,
                        'detected_payments': '', 'tags': '',
                        'min_price': '', 'max_price': '',
                        'source': 'wayback_shopify', 'tranco_rank': '',
                        'majestic_rank': '', 'monthly_visits': '',
                    }
    print(f"  Wayback myshopify: {len(src16):,} e-commerce domains")
    
    # Source 17: Priority scan results
    src17 = load_fast_scan('output/verified_priority.csv', 'priority_scan')
    print(f"  Priority scan: {len(src17):,} e-commerce domains")
    
    # Source 18: ListSignal stores
    src18 = {}
    if os.path.exists('output/listsignal_stores.csv'):
        with open('output/listsignal_stores.csv') as f:
            for row in csv.DictReader(f):
                d = row.get('domain', '').lower().strip()
                if d and d not in src18:
                    src18[d] = {
                        'domain': d, 'url': f'https://{d}',
                        'platform': 'unknown', 'has_products': False,
                        'product_count': 0, 'ecom_signals': 1,
                        'detected_payments': '', 'tags': '',
                        'min_price': '', 'max_price': '',
                        'source': 'listsignal', 'tranco_rank': '',
                        'majestic_rank': '', 'monthly_visits': '',
                    }
    print(f"  ListSignal: {len(src18):,} e-commerce domains")
    
    # Merge with priority (storeleads first for richer data, then main verify, etc.)
    merged = {}
    for src in [src5, src7, src3, src2, src6, src1b, src1, src4, src8, src9, src10, src11, src12, src13, src14, src15, src16, src17, src18]:  # Later sources override earlier
        for domain, data in src.items():
            if domain not in merged:
                merged[domain] = data
            else:
                # Keep richer data (more fields filled)
                existing = merged[domain]
                # Prefer entry with more ecom signals / products
                if (data.get('product_count', 0) or 0) > (existing.get('product_count', 0) or 0):
                    data['monthly_visits'] = existing.get('monthly_visits', '') or data.get('monthly_visits', '')
                    merged[domain] = data
                elif data.get('monthly_visits') and not existing.get('monthly_visits'):
                    existing['monthly_visits'] = data['monthly_visits']
    
    print(f"\n=== Merged: {len(merged):,} unique e-commerce domains ===")
    
    # Compute quality scores
    for domain, data in merged.items():
        data['quality_score'] = compute_quality_score(data)
    
    # Sort by quality score descending
    sorted_domains = sorted(merged.values(), key=lambda x: x['quality_score'], reverse=True)
    
    # Filter by min score
    if args.min_score > 0:
        sorted_domains = [d for d in sorted_domains if d['quality_score'] >= args.min_score]
        print(f"After min_score={args.min_score} filter: {len(sorted_domains):,}")
    
    # Stats
    platforms = Counter()
    sources = Counter()
    score_buckets = Counter()
    for d in sorted_domains:
        platforms[d.get('platform', 'unknown')] += 1
        sources[d.get('source', 'unknown')] += 1
        qs = d['quality_score']
        if qs >= 80: score_buckets['80-100'] += 1
        elif qs >= 60: score_buckets['60-79'] += 1
        elif qs >= 40: score_buckets['40-59'] += 1
        elif qs >= 20: score_buckets['20-39'] += 1
        else: score_buckets['0-19'] += 1
    
    print("\n--- Platforms ---")
    for p, c in platforms.most_common(15):
        print(f"  {p}: {c:,}")
    
    print("\n--- Sources ---")
    for s, c in sources.most_common():
        print(f"  {s}: {c:,}")
    
    print("\n--- Quality Score Distribution ---")
    for bucket in ['80-100', '60-79', '40-59', '20-39', '0-19']:
        print(f"  {bucket}: {score_buckets.get(bucket, 0):,}")
    
    if args.stats_only:
        return
    
    # Export
    export = sorted_domains[:args.limit]
    
    fieldnames = ['domain', 'url', 'platform', 'quality_score', 'has_products',
                  'product_count', 'ecom_signals', 'detected_payments',
                  'monthly_visits', 'source', 'tranco_rank', 'majestic_rank']
    
    with open(args.output, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for entry in export:
            writer.writerow(entry)
    
    print(f"\n=== Exported {len(export):,} domains to {args.output} ===")
    print(f"Top 5 by quality score:")
    for d in export[:5]:
        print(f"  {d['domain']} (QS={d['quality_score']}, platform={d['platform']}, visits={d.get('monthly_visits','')})")

if __name__ == '__main__':
    main()
