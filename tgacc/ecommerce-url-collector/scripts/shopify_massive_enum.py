#!/usr/bin/env python3
"""
Massive myshopify.com subdomain enumeration using common English words.
Checks /products.json?limit=1 for each candidate.
"""
import asyncio, aiohttp, csv, os, time, random

COMMON_WORDS = [
    "about", "above", "across", "actually", "after", "again", "against", "all", "almost", "also",
    "always", "among", "another", "any", "back", "because", "become", "been", "before", "began",
    "begin", "being", "below", "between", "black", "blue", "both", "bring", "brown", "build",
    "business", "came", "can", "change", "children", "city", "close", "cold", "come", "company",
    "could", "country", "cut", "day", "design", "did", "different", "does", "done", "door",
    "down", "each", "early", "earth", "east", "end", "enough", "even", "every", "example",
    "eye", "face", "family", "far", "feel", "few", "find", "first", "follow", "food",
    "form", "found", "four", "free", "full", "game", "gave", "girl", "give", "going",
    "good", "got", "great", "green", "group", "grow", "had", "half", "hand", "hard",
    "has", "have", "head", "hear", "help", "her", "here", "high", "him", "his",
    "home", "hot", "house", "how", "hundred", "idea", "important", "into", "island", "its",
    "just", "keep", "kind", "know", "land", "large", "last", "late", "later", "learn",
    "leave", "left", "let", "life", "light", "like", "line", "list", "little", "live",
    "long", "look", "low", "made", "main", "make", "man", "many", "may", "men",
    "might", "mind", "miss", "money", "more", "most", "mother", "move", "much", "must",
    "name", "near", "need", "never", "new", "next", "night", "not", "nothing", "now",
    "number", "off", "often", "old", "once", "one", "only", "open", "order", "other",
    "our", "out", "over", "own", "page", "paper", "part", "people", "picture", "place",
    "plan", "plant", "play", "point", "press", "problem", "put", "quite", "ran", "read",
    "real", "red", "right", "river", "room", "run", "said", "same", "saw", "say",
    "school", "sea", "second", "see", "set", "she", "show", "side", "since", "small",
    "some", "something", "sometimes", "soon", "space", "stand", "start", "state", "still", "stop",
    "story", "such", "sure", "take", "talk", "tell", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "thing", "think", "this", "those", "three",
    "through", "time", "together", "too", "top", "toward", "tree", "true", "turn", "two",
    "under", "unit", "until", "upon", "use", "usual", "very", "want", "was", "water",
    "way", "well", "went", "were", "what", "when", "where", "which", "while", "white",
    "who", "whole", "why", "wide", "will", "with", "without", "woman", "word", "work",
    "world", "write", "year", "young", "able", "allow", "along", "already", "animal",
    "appear", "area", "arm", "ask", "base", "best", "better", "big", "body", "book",
    "boy", "car", "carry", "case", "center", "child", "class", "clear", "complete",
    "contain", "copy", "correct", "course", "dark", "develop", "direct", "draw", "drive",
    "dry", "during", "fast", "father", "figure", "fine", "fire", "floor", "force",
    "forward", "general", "gold", "gone", "ground", "happen", "hold", "hope", "hour",
    "interest", "job", "king", "lead", "letter", "love", "machine", "major", "mark",
    "matter", "mean", "measure", "meet", "minute", "moment", "morning", "natural",
    "note", "object", "office", "pair", "pass", "past", "person", "piece", "possible",
    "power", "present", "produce", "product", "program", "question", "quick", "rather",
    "reach", "ready", "reason", "record", "rest", "result", "return", "rise", "rule",
    "safe", "sail", "season", "shape", "share", "short", "simple", "sit", "sleep",
    "slow", "smile", "sort", "sound", "south", "speak", "special", "spring", "square",
    "stage", "step", "strong", "surface", "table", "thick", "thin", "third", "travel",
    "trouble", "type", "voice", "walk", "watch", "window", "wonder",
]

ECOM_WORDS = [
    "shop", "store", "buy", "sell", "deal", "sale", "market", "bazaar", "outlet", "hub",
    "beauty", "fashion", "style", "wear", "cloth", "dress", "shoe", "bag", "hat", "ring",
    "skin", "care", "glow", "pure", "natural", "organic", "vegan", "clean", "fresh", "aroma",
    "home", "decor", "living", "cozy", "nest", "haven", "modern", "rustic", "minimal", "boho",
    "coffee", "tea", "brew", "roast", "spice", "herb", "chocolate", "sweet", "candy", "sugar",
    "tech", "gadget", "gear", "smart", "phone", "case", "charge", "power", "solar", "pixel",
    "pet", "dog", "cat", "puppy", "kitty", "paw", "bark", "treat", "bone", "toy",
    "fit", "gym", "yoga", "sport", "active", "strong", "flex", "muscle", "surf", "cycle",
    "art", "craft", "print", "create", "custom", "unique", "studio", "gallery", "canvas",
    "gold", "silver", "jewel", "gem", "crystal", "pearl", "stone", "diamond", "luxe",
    "baby", "kid", "mom", "dad", "mama", "papa", "family", "mini", "tiny", "little",
    "book", "note", "pen", "journal", "diary", "ink", "paper",
    "plant", "flower", "garden", "seed", "leaf", "bloom", "blossom", "rose", "lily",
    "cook", "chef", "kitchen", "food", "meal", "recipe", "bake", "grill",
    "wine", "beer", "spirit", "drink", "sip", "pour", "bar",
    "gift", "wrap", "present", "surprise", "card", "box",
    "soap", "candle", "scent", "fragrance", "wax", "melt",
    "lamp", "bulb", "neon", "glow", "shine",
    "chair", "desk", "table", "shelf", "rack",
    "bed", "pillow", "blanket", "duvet", "quilt",
    "bottle", "jar", "cup", "mug", "tumbler",
    "belt", "buckle", "strap", "tie", "bow",
    "health", "wellness", "vita", "zen", "calm",
    "travel", "pack", "adventure", "explore", "wander",
    "moon", "star", "sun", "sky", "earth", "ocean", "wave",
    "wild", "free", "happy", "lucky", "magic", "wonder", "bliss",
    "black", "white", "pink", "purple", "coral", "teal", "ivory",
    "thread", "stitch", "knit", "weave", "loom", "fiber",
    "leather", "denim", "silk", "cotton", "linen", "wool", "velvet",
]

ALL_WORDS = list(set(COMMON_WORDS + ECOM_WORDS))


def generate_massive_candidates():
    candidates = set()

    for w in ALL_WORDS:
        candidates.add(w)

    prefixes = ['the', 'my', 'get', 'go', 'try', 'buy', 'shop', 'love', 'i', 'we',
                'hey', 'its', 'be', 'mr', 'dr', 'all', 'so', 'no', 'do', 'hi']
    for p in prefixes:
        for w in ALL_WORDS:
            candidates.add(f'{p}{w}')

    suffixes = ['co', 'hq', 'shop', 'store', 'hub', 'lab', 'ly', 'ify', 'io',
                'club', 'world', 'zone', 'life', 's', 'ed', 'er', 'ing']
    for w in ALL_WORDS:
        for s in suffixes:
            candidates.add(f'{w}{s}')

    combo1 = ALL_WORDS[:200]
    combo2 = ECOM_WORDS[:60]
    for w1 in combo1:
        for w2 in combo2:
            if w1 != w2:
                candidates.add(f'{w1}{w2}')
                candidates.add(f'{w1}-{w2}')

    for w in ALL_WORDS[:100]:
        for n in ['1', '2', '3', '5', '7', '9', '10', '11', '21', '23', '99', '101', '365']:
            candidates.add(f'{w}{n}')

    return list(candidates)


async def check_subdomain(session, subdomain, sem, results, stats):
    url = f'https://{subdomain}.myshopify.com/products.json?limit=1'
    async with sem:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=6),
                                   allow_redirects=True, ssl=False) as resp:
                stats['checked'] += 1
                if resp.status == 200:
                    try:
                        data = await resp.json(content_type=None)
                        if 'products' in data:
                            from urllib.parse import urlparse
                            final_url = str(resp.url)
                            parsed = urlparse(final_url)
                            domain = parsed.hostname or f'{subdomain}.myshopify.com'
                            products = data.get('products', [])
                            results.append({
                                'domain': domain,
                                'myshopify': f'{subdomain}.myshopify.com',
                                'platform': 'shopify',
                                'has_products': len(products) > 0,
                                'product_count': len(products),
                            })
                            stats['found'] += 1
                    except Exception:
                        pass
                elif resp.status == 401:
                    results.append({
                        'domain': f'{subdomain}.myshopify.com',
                        'myshopify': f'{subdomain}.myshopify.com',
                        'platform': 'shopify',
                        'has_products': False,
                        'product_count': 0,
                    })
                    stats['found'] += 1
        except Exception:
            stats['errors'] += 1

        if stats['checked'] % 2000 == 0:
            elapsed = time.time() - stats['start']
            rate = stats['checked'] / elapsed if elapsed > 0 else 0
            hit = stats['found'] / stats['checked'] * 100 if stats['checked'] > 0 else 0
            print(f"[{stats['checked']:,}/{stats['total']:,}] found={stats['found']:,} "
                  f"({hit:.1f}%) rate={rate:.0f}/s err={stats['errors']:,}", flush=True)


async def main():
    candidates = generate_massive_candidates()

    known = set()
    for f in ['output/gist_shopify.csv', 'output/subfinder_shopify.csv',
              'output/huggingface_verified.csv', 'output/storeleads_verified.csv',
              'output/shopify_subdomain_discovered.csv']:
        if os.path.exists(f):
            with open(f) as fh:
                for row in csv.DictReader(fh):
                    d = row.get('domain', '').lower()
                    if '.myshopify.com' in d:
                        known.add(d.replace('.myshopify.com', ''))
                    known.add(d)

    candidates = [c for c in candidates if c not in known]
    random.shuffle(candidates)
    print(f"Total candidates: {len(candidates):,}", flush=True)

    sem = asyncio.Semaphore(40)
    stats = {'checked': 0, 'found': 0, 'errors': 0,
             'total': len(candidates), 'start': time.time()}
    results = []

    connector = aiohttp.TCPConnector(limit=80, ttl_dns_cache=600,
                                     enable_cleanup_closed=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        batch_size = 5000
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i + batch_size]
            tasks = [check_subdomain(session, sub, sem, results, stats) for sub in batch]
            await asyncio.gather(*tasks)

            if results:
                outfile = 'output/shopify_massive_enum.csv'
                with open(outfile, 'w', newline='') as f:
                    w = csv.DictWriter(f, fieldnames=['domain', 'myshopify', 'platform',
                                                       'has_products', 'product_count'])
                    w.writeheader()
                    w.writerows(results)

    elapsed = time.time() - stats['start']
    print(f"\nDone! {stats['checked']:,} checked in {elapsed:.0f}s, "
          f"{stats['found']:,} stores found", flush=True)

    if results:
        outfile = 'output/shopify_massive_enum.csv'
        with open(outfile, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['domain', 'myshopify', 'platform',
                                               'has_products', 'product_count'])
            w.writeheader()
            w.writerows(results)
        print(f"Saved {len(results)} stores to {outfile}", flush=True)

asyncio.run(main())
