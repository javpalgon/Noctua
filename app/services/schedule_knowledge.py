import asyncio
from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig,
    BFSDeepCrawlStrategy,
    BrowserConfig,
    DomainFilter,
    FilterChain,
)
from app.schemas.client import ClientConfig
from app.services.knowledge_graph_builder import KnowledgeGraphBuilder
from pathlib import Path
from dotenv import load_dotenv
import os
import re
from urllib.parse import urlparse

load_dotenv()

# Configuración
LLAMUS_URL = os.getenv("LLAMUS_URL", "https://llamus.cs.us.es/ollama")
LLAMUS_API_KEY = os.getenv("LLAMUS_API_KEY")
LLAMUS_MODEL = os.getenv("LLAMUS_MODEL_EXTRACT", "llama3.2:3b")
KG_CHUNK_SIZE = int(os.getenv("KG_CHUNK_SIZE", "1500"))
KG_CHUNK_OVERLAP = int(os.getenv("KG_CHUNK_OVERLAP", "150"))
KG_MAX_CHUNKS = int(os.getenv("KG_MAX_CHUNKS", "20"))
OUTPUT_DIR = Path("./knowledge_graphs")
SAVE_TO_NEO4J = os.getenv("NEO4J_URI") is not None  # Auto-detectar si usar Neo4j

def limpiar_markdown(texto: str) -> str:
    """Limpia el markdown eliminando scripts, estilos y caracteres no deseados."""
    lineas_limpias=[]
    for linea in texto.split("\n"):

        linea_strip=linea.strip()
        # Saltar lineas vacías
        if not linea_strip:
            continue

        # #Saltar lineas con muchos links
        # num_links = len(re.findall(r'\[.*?\]\(.*?\)', linea_strip))
        # if num_links > 3:
        #     continue

        # Saltar líneas que parecen footers/legales
        palabras_footer = ["cookie", "privacy", "©", "copyright", "terms of", "política de"]
        if any(p in linea_strip.lower() for p in palabras_footer):
            continue

        #Saltar separadores markdown
        if linea_strip.startswith("---") or linea_strip.startswith("==="):
            continue

        # Saltar lineas de URL/rutas para evitar nodos de infraestructura
        if re.search(r"https?://|www\\.", linea_strip.lower()):
            continue
        if re.match(r"^[./\\\\].+", linea_strip):
            continue

        # Saltar bloques tecnicos frecuentes en documentacion
        if "<script" in linea_strip.lower() or "</script>" in linea_strip.lower():
            continue

        lineas_limpias.append(linea_strip)

    return "\n".join(lineas_limpias)

def _normalize_host(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().strip()
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host

async def rastreo_web(cliente: ClientConfig, save_to_neo4j: bool = True, single_url: bool = False):
    """
    Rastrea la web del cliente y genera un grafo de conocimiento.
    
    Args:
        cliente: Configuración del cliente
        save_to_neo4j: Si True, guarda en Neo4j además de en local
    """
    
    print(f"\n{'='*50}")
    print(f"[RASTREO] Iniciando rastreo web para {cliente.company_name}")
    print(f"[RASTREO] URL: {cliente.url_portal}")
    modo_rastreo = "solo URL" if single_url else "rastreo profundo"
    print(f"[RASTREO] Modo: {modo_rastreo}")
    print(f"{'='*50}\n")

    expected_host = _normalize_host(str(cliente.url_portal))

    max_depth = 0 if single_url else 2
    filter_chain = FilterChain(
        [DomainFilter(allowed_domains=expected_host)]
        if expected_host
        else []
    )
    crawl_strategy = BFSDeepCrawlStrategy(
        max_depth=max_depth,
        filter_chain=filter_chain,
    )
    configuration = CrawlerRunConfig(
        exclude_external_links=True, 
        exclude_all_images=True, 
        deep_crawl_strategy=crawl_strategy,
        excluded_tags=["footer", "aside", "header", "script", "style"],
        word_count_threshold=15,
        verbose=True
    )

    browser_config = BrowserConfig(ignore_https_errors=True)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun(url=str(cliente.url_portal), config=configuration)

        try:
            kg = KnowledgeGraphBuilder(
                model=LLAMUS_MODEL,
                ollama_url=LLAMUS_URL,
                api_key=LLAMUS_API_KEY,
                chunk_size=KG_CHUNK_SIZE,
                chunk_overlap=KG_CHUNK_OVERLAP,
                max_chunks=KG_MAX_CHUNKS,
            )
            paginas_exitosas = 0
            paginas_excluidas_host = 0
            total_chars = 0
            combined_nodes = set()
            edge_labels: dict[tuple[str, str], set[str]] = {}
            node_sources: dict[str, set[str]] = {}

            for pagina in results:
                if pagina.success:
                    page_host = _normalize_host(str(pagina.url))
                    if expected_host and page_host and page_host != expected_host:
                        paginas_excluidas_host += 1
                        continue

                    paginas_exitosas += 1
                    total_chars += len(pagina.markdown or "")

                    markdown_limpio = limpiar_markdown(pagina.markdown or "")
                    if not markdown_limpio.strip():
                        continue

                    page_graph = kg.build_from_text(
                        markdown_limpio,
                        verbose=True,
                        source_url=str(pagina.url),
                    )

                    combined_nodes.update(page_graph.get("nodes", []))

                    for edge in page_graph.get("edges", []):
                        key = tuple(sorted([edge["node_1"], edge["node_2"]]))
                        labels = edge_labels.setdefault(key, set())
                        for label in str(edge.get("edge", "")).split(";"):
                            label = label.strip()
                            if label:
                                labels.add(label)

                    for node, urls in (page_graph.get("node_sources", {}) or {}).items():
                        if not urls:
                            continue
                        node_sources.setdefault(node, set()).update([u for u in urls if u])
                else:
                    print(f"[RASTREO] ❌ Error al rastrear {pagina.url}: {pagina.error_message}")

            print(f"\n[RASTREO] ✅ Rastreadas {paginas_exitosas} páginas")
            if paginas_excluidas_host:
                print(f"[RASTREO] ⏭️  Excluidas por host: {paginas_excluidas_host}")
            print(f"[RASTREO] 📄 Total de caracteres: {total_chars}")

            if not combined_nodes:
                print("[RASTREO] ❌ No se obtuvo contenido para procesar")
                return None

            # Construir el grafo de conocimiento
            print(f"\n{'='*50}")
            print(f"[KNOWLEDGE GRAPH] Generando grafo de conocimiento...")
            print(f"{'='*50}\n")
            edges = [
                {
                    "node_1": key[0],
                    "node_2": key[1],
                    "edge": "; ".join(sorted(labels)),
                }
                for key, labels in edge_labels.items()
            ]

            graph = {
                "nodes": sorted(combined_nodes),
                "edges": edges,
                "node_sources": {
                    node: sorted(urls) for node, urls in node_sources.items() if urls
                },
                "networkx": None,
            }

            if not graph["nodes"]:
                print("[KNOWLEDGE GRAPH] ⚠️ No se extrajeron conceptos del texto")
                return None
            
            # Guardar en Neo4j si está configurado y tenemos client_id
            if save_to_neo4j and SAVE_TO_NEO4J and cliente.client_id:
                print(f"\n[NEO4J] Guardando grafo en Neo4j...")
                kg.save_to_neo4j(
                    client_id=cliente.client_id,
                    graph=graph
                )
            elif save_to_neo4j and not cliente.client_id:
                print(f"[NEO4J] ⚠️ No se guardó en Neo4j: falta client_id")
        
            print(f"\n{'='*50}")
            print(f"[RESUMEN] Grafo de conocimiento generado:")
            print(f"          - Conceptos (nodos): {len(graph['nodes'])}")
            print(f"          - Relaciones (aristas): {len(graph['edges'])}")
            print(f"          - Neo4j: {'✅ Guardado' if (save_to_neo4j and SAVE_TO_NEO4J and cliente.client_id) else '❌ No guardado'}")
            print(f"{'='*50}\n")
            
            return graph
            
        except ConnectionError as e:
            print(f"[KNOWLEDGE GRAPH] ❌ Error de conexión con Ollama: {e}")
            return None
        except Exception as e:
            print(f"[KNOWLEDGE GRAPH] ❌ Error al generar grafo: {e}")
            return None

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 INICIANDO GENERACIÓN DE GRAFO DE CONOCIMIENTO")
    print("="*60 + "\n")
    
    # Ejemplo: cliente sin guardar en Neo4j (sin client_id)
    # Para guardar en Neo4j, el cliente debe existir en PostgreSQL primero
    cliente_ejemplo = ClientConfig(
        company_name="MoonTerraza",
        url_portal="http://0.0.0.0:8001/",
        client_id=None,  # Sin ID = no se guarda en Neo4j
        api_key=None
    )
    
    graph = asyncio.run(rastreo_web(cliente_ejemplo))
    
    if graph:
        print("\n" + "="*60)
        print("✅ GRAFO DE CONOCIMIENTO GENERADO EXITOSAMENTE")
        print("="*60 + "\n")
    else:
        print("\n" + "="*60)
        print("❌ ERROR AL GENERAR EL GRAFO DE CONOCIMIENTO")
        print("="*60 + "\n")