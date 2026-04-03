#!/usr/bin/env python3
"""
Discover Shopify stores via myshopify.com subdomain enumeration.
Every Shopify store has a *.myshopify.com subdomain.
We check if the subdomain exists and resolves to get custom domain.
"""
import asyncio, aiohttp, csv, sys, os, time, random, string

# Common English words and patterns for store names
WORD_LISTS = [
    # Fashion/clothing
    'fashion', 'style', 'wear', 'clothing', 'apparel', 'outfit', 'threads', 'denim',
    'silk', 'cotton', 'linen', 'cashmere', 'wool', 'velvet', 'satin', 'chic',
    'vogue', 'glamour', 'trendy', 'luxury', 'haute', 'couture', 'boutique',
    'wardrobe', 'closet', 'dressy', 'casual', 'urban', 'streetwear', 'vintage',
    # Beauty/skincare
    'beauty', 'skin', 'glow', 'radiant', 'flawless', 'natural', 'organic', 'pure',
    'bloom', 'blossom', 'petal', 'rose', 'lavender', 'honey', 'coconut', 'aloe',
    'serum', 'cream', 'lotion', 'mask', 'scrub', 'butter', 'oil', 'essence',
    # Home/living
    'home', 'house', 'nest', 'haven', 'cozy', 'comfort', 'living', 'decor',
    'kitchen', 'bath', 'garden', 'outdoor', 'indoor', 'modern', 'rustic', 'boho',
    'minimal', 'nordic', 'scandinavian', 'cottage', 'farmhouse', 'industrial',
    # Food/drink
    'coffee', 'tea', 'brew', 'roast', 'beans', 'spice', 'herb', 'salt', 'pepper',
    'chocolate', 'candy', 'sweet', 'sugar', 'honey', 'maple', 'berry', 'fruit',
    'juice', 'smoothie', 'protein', 'vitamin', 'supplement', 'health', 'wellness',
    # Tech/gadgets
    'tech', 'digital', 'smart', 'cyber', 'pixel', 'byte', 'data', 'cloud',
    'gadget', 'gear', 'device', 'phone', 'case', 'charge', 'power', 'solar',
    # Pets
    'pet', 'dog', 'cat', 'puppy', 'kitty', 'paw', 'bark', 'meow', 'furry',
    'tail', 'treat', 'bone', 'leash', 'collar', 'toy', 'bed', 'bowl',
    # Sports/fitness
    'fit', 'gym', 'yoga', 'run', 'sport', 'active', 'strong', 'flex', 'muscle',
    'cardio', 'lift', 'cross', 'train', 'race', 'cycle', 'swim', 'surf',
    # General commerce
    'shop', 'store', 'buy', 'deal', 'sale', 'mart', 'market', 'bazaar',
    'emporium', 'depot', 'outlet', 'hub', 'spot', 'zone', 'world', 'land',
    'central', 'direct', 'express', 'prime', 'elite', 'pro', 'premium', 'gold',
    'silver', 'diamond', 'platinum', 'royal', 'crown', 'king', 'queen',
    # Colors
    'black', 'white', 'red', 'blue', 'green', 'pink', 'purple', 'orange',
    'yellow', 'gold', 'silver', 'grey', 'brown', 'navy', 'coral', 'teal',
    # Nature
    'sun', 'moon', 'star', 'sky', 'earth', 'ocean', 'sea', 'river', 'lake',
    'mountain', 'forest', 'tree', 'leaf', 'flower', 'stone', 'rock', 'crystal',
    # Misc popular
    'the', 'my', 'our', 'your', 'best', 'top', 'new', 'fresh', 'clean',
    'good', 'great', 'super', 'mega', 'ultra', 'max', 'mini', 'tiny', 'little',
    'big', 'grand', 'wild', 'free', 'happy', 'lucky', 'magic', 'wonder',
]

# Generate candidate subdomains
def generate_candidates():
    candidates = set()
    
    # Single words
    for w in WORD_LISTS:
        candidates.add(w)
    
    # Common prefixes + words
    prefixes = ['the', 'my', 'get', 'go', 'try', 'buy', 'shop', 'love', 'i', 'we', 'hey', 'oh', 'its', 'be']
    for p in prefixes:
        for w in WORD_LISTS[:80]:
            candidates.add(f'{p}{w}')
            candidates.add(f'{p}-{w}')
    
    # Words + common suffixes
    suffixes = ['co', 'hq', 'shop', 'store', 'hub', 'lab', 'ly', 'ify', 'io', 'app', 'club', 'world', 'zone', 'life', 'nyc', 'la', 'uk', 'usa', 'global']
    for w in WORD_LISTS[:80]:
        for s in suffixes:
            candidates.add(f'{w}{s}')
            candidates.add(f'{w}-{s}')
    
    # Two-word combos (most common patterns)
    combo_words = WORD_LISTS[:60]
    for i, w1 in enumerate(combo_words):
        for w2 in combo_words[i+1:i+10]:
            candidates.add(f'{w1}{w2}')
            candidates.add(f'{w1}-{w2}')
    
    # Common store name patterns
    patterns = [
        'official', 'original', 'authentic', 'genuine', 'real',
        'daily', 'weekly', 'everyday', 'always', 'forever',
        'simple', 'basic', 'essentials', 'basics', 'staples',
    ]
    for p in patterns:
        for w in WORD_LISTS[:30]:
            candidates.add(f'{p}{w}')
            candidates.add(f'{w}{p}')
    
    return list(candidates)

async def check_subdomain(session, subdomain, sem, results, stats):
    url = f'https://{subdomain}.myshopify.com/products.json?limit=1'
    async with sem:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), allow_redirects=True, ssl=False) as resp:
                stats['checked'] += 1
                if resp.status == 200:
                    try:
                        data = await resp.json(content_type=None)
                        if 'products' in data:
                            # Valid Shopify store! Get custom domain from redirect
                            final_url = str(resp.url)
                            custom_domain = resp.headers.get('X-Shopify-Stage', '')
                            # The final URL after redirect might be the custom domain
                            from urllib.parse import urlparse
                            parsed = urlparse(final_url)
                            domain = parsed.hostname or f'{subdomain}.myshopify.com'
                            if domain.endswith('.myshopify.com'):
                                domain = f'{subdomain}.myshopify.com'
                            
                            products = data.get('products', [])
                            product_count = len(products)
                            
                            results.append({
                                'domain': domain,
                                'myshopify': f'{subdomain}.myshopify.com',
                                'platform': 'shopify',
                                'has_products': product_count > 0,
                                'product_count': product_count,
                            })
                            stats['found'] += 1
                            if stats['found'] % 10 == 0 or stats['found'] <= 5:
                                print(f"  ✓ Found #{stats['found']}: {domain} ({product_count} products)")
                    except:
                        pass
                elif resp.status == 401:
                    # Password protected store - still exists
                    results.append({
                        'domain': f'{subdomain}.myshopify.com',
                        'myshopify': f'{subdomain}.myshopify.com',
                        'platform': 'shopify',
                        'has_products': False,
                        'product_count': 0,
                    })
                    stats['found'] += 1
        except:
            stats['errors'] += 1
        
        if stats['checked'] % 500 == 0:
            elapsed = time.time() - stats['start']
            rate = stats['checked'] / elapsed
            print(f"  Progress: {stats['checked']:,}/{stats['total']:,} checked, {stats['found']} found, {stats['errors']} errors, {rate:.0f}/s")

async def main():
    candidates = generate_candidates()
    print(f"Generated {len(candidates):,} candidate subdomains")
    
    # Remove already known domains
    known = set()
    for f in ['output/gist_shopify.csv', 'output/subfinder_shopify.csv', 'output/huggingface_verified.csv']:
        if os.path.exists(f):
            with open(f) as fh:
                for row in csv.DictReader(fh):
                    d = row.get('domain', '').lower()
                    if '.myshopify.com' in d:
                        known.add(d.replace('.myshopify.com', ''))
    
    candidates = [c for c in candidates if c not in known]
    print(f"After removing known: {len(candidates):,} to check")
    
    random.shuffle(candidates)
    
    sem = asyncio.Semaphore(50)
    stats = {'checked': 0, 'found': 0, 'errors': 0, 'total': len(candidates), 'start': time.time()}
    results = []
    
    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300, enable_cleanup_closed=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_subdomain(session, sub, sem, results, stats) for sub in candidates]
        await asyncio.gather(*tasks)
    
    elapsed = time.time() - stats['start']
    print(f"\nDone! {stats['checked']:,} checked in {elapsed:.0f}s")
    print(f"Found {len(results)} Shopify stores")
    
    # Save results
    if results:
        outfile = 'output/shopify_subdomain_discovered.csv'
        with open(outfile, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['domain', 'myshopify', 'platform', 'has_products', 'product_count'])
            w.writeheader()
            w.writerows(results)
        print(f"Saved to {outfile}")

asyncio.run(main())
