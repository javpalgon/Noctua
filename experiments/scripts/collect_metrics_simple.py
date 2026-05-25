#!/usr/bin/env python3
"""
Simple collector: query Neo4j for |V|, |E| and semantic density D by client_id.
Writes CSV to experiments/results/simple_results_with_density.csv
"""
import os
import csv
import argparse
import asyncio
import sys
import urllib3
from neo4j import GraphDatabase
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.schedule_knowledge import limpiar_markdown

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'results')
os.makedirs(OUTPUT_DIR, exist_ok=True)
CSV_PATH = os.path.join(OUTPUT_DIR, 'simple_results_with_density.csv')

NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '')
ALLOW_INSECURE_TLS_FALLBACK = os.getenv('ALLOW_INSECURE_TLS_FALLBACK', 'true').lower() in {'1', 'true', 'yes', 'on'}
MAX_SOURCE_URLS = int(os.getenv('METRICS_MAX_SOURCE_URLS', '0'))
FETCH_WORKERS = max(1, int(os.getenv('METRICS_FETCH_WORKERS', '3')))
HEADERS = {'User-Agent': 'Noctua-Metrics-Agent/1.0'}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if not NEO4J_URI:
    print('NEO4J_URI not set. Please set NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD environment variables.')
    raise SystemExit(1)


def count_nodes_edges(session, client_id):
    q_nodes = "MATCH (c:Concept {client_id: $cid}) RETURN count(c) AS nodes"
    q_edges = "MATCH (a:Concept {client_id: $cid})-[r:RELATED_TO]->(b:Concept {client_id: $cid}) RETURN count(r) AS edges"
    nodes = session.run(q_nodes, cid=client_id).single().get('nodes', 0)
    edges = session.run(q_edges, cid=client_id).single().get('edges', 0)
    return int(nodes), int(edges)


async def _crawl_markdown(url: str, crawler: AsyncWebCrawler):
    config = CrawlerRunConfig(
        exclude_external_links=True,
        exclude_all_images=True,
        excluded_tags=["footer", "aside", "header", "script", "style"],
        word_count_threshold=15,
        verbose=False,
    )
    result = await crawler.arun(url=url, config=config)
    if not result or not result.success:
        return ""
    return getattr(result, "markdown", "") or ""


async def _crawl_worker(url_queue: asyncio.Queue):
    total_chars = 0
    checked = 0
    ok = 0
    browser_config = BrowserConfig(ignore_https_errors=ALLOW_INSECURE_TLS_FALLBACK)
    async with AsyncWebCrawler(config=browser_config) as crawler:
        while True:
            url = await url_queue.get()
            try:
                if url is None:
                    return total_chars, checked, ok
                checked += 1
                try:
                    markdown = await _crawl_markdown(url, crawler)
                    markdown_limpio = limpiar_markdown(markdown)
                    if markdown_limpio.strip():
                        total_chars += len(markdown_limpio)
                        ok += 1
                except Exception as e:
                    print(f"  Warning: failed to fetch {url}: {e}")
            finally:
                url_queue.task_done()


async def fetch_size_kb(urls):
    urls = list(urls)
    if not urls:
        return 0.0, 0, 0

    url_queue: asyncio.Queue = asyncio.Queue()
    for url in urls:
        url_queue.put_nowait(url)

    worker_count = min(FETCH_WORKERS, len(urls))
    for _ in range(worker_count):
        url_queue.put_nowait(None)

    workers = [asyncio.create_task(_crawl_worker(url_queue)) for _ in range(worker_count)]
    await url_queue.join()
    totals = await asyncio.gather(*workers)

    total_chars = sum(item[0] for item in totals)
    checked = sum(item[1] for item in totals)
    ok = sum(item[2] for item in totals)
    return (total_chars / 1024.0 if total_chars else 0.0), checked, ok


def fetch_source_urls(session, client_id):
    query = "MATCH (s:Source {client_id: $cid}) RETURN collect(distinct s.url) AS urls"
    urls = session.run(query, cid=client_id).single().get('urls', []) or []
    if MAX_SOURCE_URLS > 0:
        return urls[:MAX_SOURCE_URLS]
    return urls


def sample_host_for_client(session, client_id):
    q = """
    MATCH (s:Source {client_id: $cid})
    RETURN s.url AS url
    LIMIT 1
    """
    rec = session.run(q, cid=client_id).single()
    if not rec or not rec.get('url'):
        return ''
    return rec['url']


def parse_args():
    parser = argparse.ArgumentParser(description='Collect simple graph metrics from Neo4j')
    parser.add_argument(
        '--client-ids',
        required=True,
        help='Comma-separated client IDs.'
    )
    parser.add_argument(
        '--named-client',
        action='append',
        default=[],
        help='Optional mapping NAME=CLIENT_ID. Can be repeated.'
    )
    return parser.parse_args()


def main():
    args = parse_args()
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    named_map = {}
    for pair in args.named_client:
        if '=' not in pair:
            continue
        name, cid = pair.split('=', 1)
        name = name.strip()
        cid = cid.strip()
        if name and cid:
            named_map[cid] = name

    explicit_client_ids = [c.strip() for c in args.client_ids.split(',') if c.strip()]

    if not explicit_client_ids:
        print('No valid client IDs provided in --client-ids.')
        raise SystemExit(1)

    rows = []
    with driver.session() as session:
        for cid in explicit_client_ids:
            V, E = count_nodes_edges(session, cid)
            sample_url = sample_host_for_client(session, cid)
            domain_label = named_map.get(cid) or sample_url or 'manual'
            urls = fetch_source_urls(session, cid)
            S_kb, checked, ok = asyncio.run(fetch_size_kb(urls))
            D = (V + E) / S_kb if S_kb > 0 else None
            print(
                f'  client_id={cid} ({domain_label}) -> V={V}, E={E}, '
                f'S_kb={S_kb:.2f}, D={(D if D is not None else "NA")}, '
                f'urls_ok={ok}/{checked}'
            )
            rows.append({
                'domain': domain_label,
                'client_id': cid,
                'V': V,
                'E': E,
                'S_kb': round(S_kb, 2),
                'D': round(D, 6) if D is not None else None,
                'urls_total': len(urls),
                'urls_checked': checked,
                'urls_ok': ok,
            })

    keys = ['domain', 'client_id', 'V', 'E', 'S_kb', 'D', 'urls_total', 'urls_checked', 'urls_ok']
    with open(CSV_PATH, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=keys)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print('Wrote CSV to', CSV_PATH)
    driver.close()

if __name__ == '__main__':
    main()
