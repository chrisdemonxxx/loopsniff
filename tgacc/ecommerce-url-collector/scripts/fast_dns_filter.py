#!/usr/bin/env python3
"""Fast DNS pre-filter: resolve domains in bulk to eliminate dead ones.
Uses asyncio DNS resolution with high concurrency (200+ workers).
Can process 100-500 domains/second - 10x faster than HTTP checks."""

import asyncio
import csv
import sys
import time
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# Suppress asyncio noise
logging.getLogger('asyncio').setLevel(logging.CRITICAL)

async def resolve_domain(domain, semaphore):
    """Try to resolve a domain via DNS. Returns (domain, alive)."""
    async with semaphore:
        try:
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.getaddrinfo(domain, 443, family=0, type=0),
                timeout=3
            )
            return (domain, True)
        except:
            return (domain, False)

async def process_chunk(domains, semaphore):
    """Process a chunk of domains concurrently."""
    tasks = [resolve_domain(d, semaphore) for d in domains]
    return await asyncio.gather(*tasks)

def main():
    parser = argparse.ArgumentParser(description='Fast DNS pre-filter')
    parser.add_argument('--input', default='output/mega_merged.csv')
    parser.add_argument('--output', default='output/dns_alive.csv')
    parser.add_argument('--workers', type=int, default=200)
    parser.add_argument('--chunk-size', type=int, default=2000)
    parser.add_argument('--skip-existing', action='store_true', help='Skip domains already in mega_merged')
    parser.add_argument('--extra-input', help='Additional input file (Tranco/Majestic remaining)')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()

    # Load domains already in mega_merged (to find remaining ones)
    mega_domains = set()
    if args.skip_existing:
        with open('output/mega_merged.csv') as f:
            reader = csv.DictReader(f)
            for row in reader:
                mega_domains.add(row.get('domain', '').lower().strip())
        log.info(f"Loaded {len(mega_domains):,} existing domains to skip")

    # Load domains to check
    domains_to_check = []
    
    if args.extra_input:
        # Load from Tranco or Majestic
        if 'tranco' in args.extra_input.lower() or 'top-1m' in args.extra_input.lower():
            with open(args.extra_input) as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        domain = parts[1].lower().strip()
                        if domain and domain not in mega_domains:
                            domains_to_check.append(domain)
        elif 'majestic' in args.extra_input.lower():
            with open(args.extra_input) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    domain = row.get('Domain', '').lower().strip()
                    if domain and domain not in mega_domains:
                        domains_to_check.append(domain)
        log.info(f"Loaded {len(domains_to_check):,} domains from {args.extra_input}")
    else:
        # Load from mega_merged
        with open(args.input) as f:
            reader = csv.DictReader(f)
            for row in reader:
                domain = row.get('domain', '').lower().strip()
                if domain:
                    domains_to_check.append(domain)
        log.info(f"Loaded {len(domains_to_check):,} domains from {args.input}")

    # Resume support
    already_done = set()
    if args.resume and os.path.exists(args.output):
        with open(args.output) as f:
            reader = csv.DictReader(f)
            for row in reader:
                already_done.add(row.get('domain', '').lower())
        domains_to_check = [d for d in domains_to_check if d not in already_done]
        log.info(f"Resuming: skipping {len(already_done):,} already checked")

    log.info(f"To check: {len(domains_to_check):,} domains with {args.workers} workers")

    # Process in chunks
    alive_count = 0
    dead_count = 0
    total_processed = 0
    start_time = time.time()
    
    write_header = not args.resume or not os.path.exists(args.output)
    outfile = open(args.output, 'a' if args.resume else 'w', newline='')
    writer = csv.writer(outfile)
    if write_header:
        writer.writerow(['domain', 'dns_alive'])

    for chunk_start in range(0, len(domains_to_check), args.chunk_size):
        chunk = domains_to_check[chunk_start:chunk_start + args.chunk_size]
        chunk_num = chunk_start // args.chunk_size + 1
        total_chunks = (len(domains_to_check) + args.chunk_size - 1) // args.chunk_size

        semaphore = asyncio.Semaphore(args.workers)
        results = asyncio.run(process_chunk(chunk, semaphore))

        for domain, alive in results:
            if alive:
                alive_count += 1
                writer.writerow([domain, '1'])
            else:
                dead_count += 1

        total_processed += len(chunk)
        elapsed = time.time() - start_time
        rate = total_processed / elapsed if elapsed > 0 else 0
        eta_h = (len(domains_to_check) - total_processed) / rate / 3600 if rate > 0 else 0

        if chunk_num % 5 == 0 or chunk_num <= 3:
            log.info(
                f"Chunk {chunk_num}/{total_chunks} | "
                f"Processed: {total_processed:,} | "
                f"Alive: {alive_count:,} ({alive_count*100/total_processed:.1f}%) | "
                f"Dead: {dead_count:,} | "
                f"Rate: {rate:.0f}/s | "
                f"ETA: {eta_h:.1f}h"
            )
        outfile.flush()

    outfile.close()
    elapsed = time.time() - start_time
    log.info(f"DONE. {total_processed:,} checked in {elapsed:.0f}s ({total_processed/elapsed:.0f}/s)")
    log.info(f"Alive: {alive_count:,} ({alive_count*100/max(1,total_processed):.1f}%) | Dead: {dead_count:,}")

import os
if __name__ == '__main__':
    main()
