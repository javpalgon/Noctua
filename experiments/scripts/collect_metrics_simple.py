#!/usr/bin/env python3
"""
Simple collector: query Neo4j for |V|, |E| and semantic density D by client_id.
Writes CSV to experiments/results/simple_results_with_density.csv
"""
import os
import csv
import argparse
from urllib.parse import urlparse
import requests
import urllib3
from bs4 import BeautifulSoup
from neo4j import GraphDatabase

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'results')
os.makedirs(OUTPUT_DIR, exist_ok=True)
CSV_PATH = os.path.join(OUTPUT_DIR, 'simple_results_with_density.csv')

NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '')
ALLOW_INSECURE_TLS_FALLBACK = os.getenv('ALLOW_INSECURE_TLS_FALLBACK', 'true').lower() in {'1', 'true', 'yes', 'on'}
MAX_URLS_PER_CLIENT = int(os.getenv('METRICS_MAX_URLS_PER_CLIENT', '20'))
HEADERS = {'User-Agent': 'Noctua-Metrics-Agent/1.0'}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if not NEO4J_URI:
    print('NEO4J_URI not set. Please set NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD environment variables.')
    raise SystemExit(1)


def host_from_url(u):
    try:
        host = urlparse(u).netloc
        if host.startswith('www.'):
            host = host[4:]
        return host.lower()
    except Exception:
        return u


def count_nodes_edges(session, client_id):
    q_nodes = "MATCH (c:Concept {client_id: $cid}) RETURN count(c) AS nodes"
    q_edges = "MATCH (a:Concept {client_id: $cid})-[r:RELATED_TO]->(b:Concept {client_id: $cid}) RETURN count(r) AS edges"
    nodes = session.run(q_nodes, cid=client_id).single().get('nodes', 0)
    edges = session.run(q_edges, cid=client_id).single().get('edges', 0)
    return int(nodes), int(edges)


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    for s in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
        s.decompose()
    text = soup.get_text(separator='\n')
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return '\n'.join(lines)


def _get_with_tls_fallback(url: str, timeout: int = 10):
    try:
        return requests.get(url, headers=HEADERS, timeout=timeout)
    except requests.exceptions.SSLError:
        if ALLOW_INSECURE_TLS_FALLBACK:
            return requests.get(url, headers=HEADERS, timeout=timeout, verify=False)
        raise


def fetch_size_kb(urls, timeout=10, max_per_client=20):
    total_chars = 0
    checked = 0
    ok = 0
    for u in urls:
        if checked >= max_per_client:
            break
        checked += 1
        try:
            r = _get_with_tls_fallback(u, timeout=timeout)
            if r.status_code == 200 and r.text:
                total_chars += len(extract_text(r.text))
                ok += 1
        except Exception as e:
            print(f"  Warning: failed to fetch {u}: {e}")
            continue
    return (total_chars / 1024.0 if total_chars else 0.0), checked, ok


def sample_host_for_client(session, client_id):
    q = """
    MATCH (s:Source {client_id: $cid})
    RETURN s.url AS url
    LIMIT 1
    """
    rec = session.run(q, cid=client_id).single()
    if not rec or not rec.get('url'):
        return ''
    return host_from_url(rec['url'])


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
            domain = sample_host_for_client(session, cid)
            domain_label = named_map.get(cid) or domain or 'manual'
            urls = session.run(
                "MATCH (s:Source {client_id: $cid}) RETURN collect(distinct s.url)[0..50] AS urls",
                cid=cid,
            ).single().get('urls', []) or []
            S_kb, checked, ok = fetch_size_kb(urls, max_per_client=MAX_URLS_PER_CLIENT)
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
