# ESTE MODULO CONSTRUYE UN GRAFO DE CONOCIMIENTO A PARTIR DE TEXTO DE LA WEB

# MÓDULO EXTRAÍDO DEL REPOSITORIO Knowledge_graph_builder

import os
import json
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path
import networkx as nx
from pyvis.network import Network
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()  # Carga variables desde .env

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
    
    def generate(self, model: str, prompt: str, system: str = None) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "system": system, "stream": False}
        payload = {k: v for k, v in payload.items() if v is not None}
        response = requests.post(url, json=payload, timeout=600)
        response.raise_for_status()
        return response.json().get("response", "")


class KnowledgeGraphBuilder:
    
    EXTRACTION_PROMPT = """You are a knowledge graph extractor. Your ONLY task is to extract entities and their relationships from the given text.

CRITICAL RULES FOR METRICS, TABLES, AND NUMBERS:
- If you detect structured data, tables, lists, rankings, or items with associated numbers (e.g., prices, scores, positions, quantities, dates), you MUST extract the numbers as individual nodes and link them to the main entity.
- If the text has an overarching theme or context (e.g., a specific industry, sport, location, or company), extract that context as a node and link the main entities to it.

EXAMPLES OF HOW TO HANDLE METRICS/TABLES:
Text: "ID: 15 | John Doe | Dept: Sales | 2500 USD"
Correct Output:
[
  {"node_1": "John Doe", "node_2": "15", "edge": "has ID"},
  {"node_1": "John Doe", "node_2": "Sales", "edge": "belongs to department"},
  {"node_1": "John Doe", "node_2": "2500 USD", "edge": "has metric value"}
]

GENERAL RULES:
- Extract REAL concepts, entities, people, places, metrics, or organizations.
- Each relationship must connect two different concepts.
- The "edge" field must be a short, clear verb or descriptive phrase.
- Output ONLY a valid JSON array of objects with keys "node_1", "node_2", and "edge". Do not add markdown, explanations, or text outside the JSON.
"""

    def __init__(
        self,
        model: str = "zephyr:latest",
        ollama_url: str = "http://localhost:11434",
        chunk_size: int = 1500,
        max_chunks: Optional[int] = None,
    ):
        self.model = model
        self.chunk_size = chunk_size
        self.max_chunks = max_chunks
        self.client = OllamaClient(ollama_url)

    @staticmethod
    def _normalize_text(value: Any) -> str:
        """Normaliza valores de salida del LLM a texto seguro para el grafo."""
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        return value.lower().strip()
    
    def _split_text(self, text: str) -> List[str]:
        chunks, start = [], 0
        text = text.strip()
        while start < len(text):
            chunks.append(text[start:start + self.chunk_size])
            start += self.chunk_size - 150  # solapamiento de 150 caracteres para contexto
        if not chunks:
            return [text]
        if self.max_chunks is not None and self.max_chunks > 0:
            return chunks[: self.max_chunks]
        return chunks
    
    def _extract_from_chunk(self, chunk: str) -> List[Dict]:
        prompt = f"Extract the knowledge graph from this text:\n\n{chunk}\n\nJSON output:"
        try:
            response = self.client.generate(self.model, prompt, self.EXTRACTION_PROMPT).strip()
            if not response:
                print("  ⚠️ Respuesta vacía del modelo")
                return []
            
            # Limpiar bloques de código markdown
            if "```" in response:
                parts = response.split("```")
                if len(parts) >= 2:
                    response = parts[1].replace("json", "", 1).strip()
            
            # Buscar el array JSON
            start, end = response.find('['), response.rfind(']') + 1
            if start == -1 or end <= start:
                print(f"  ⚠️ No se encontró JSON válido en la respuesta: {response[:200]}")
                return []
            
            response = response[start:end]
            result = json.loads(response)
            
            # Validar estructura
            valid = []
            for item in result:
                if isinstance(item, dict) and "node_1" in item and "node_2" in item:
                    valid.append(item)
            
            if not valid:
                print(f"  ⚠️ JSON parseado pero sin relaciones válidas")
            return valid
            
        except json.JSONDecodeError as e:
            print(f"  ❌ Error parseando JSON del modelo: {e}")
            print(f"     Respuesta recibida: {response[:300]}")
            return []
        except requests.exceptions.Timeout:
            print(f"  ❌ Timeout al llamar a Ollama")
            return []
        except requests.exceptions.ConnectionError:
            print(f"  ❌ No se pudo conectar con Ollama. ¿Está corriendo en {self.client.base_url}?")
            return []
        except Exception as e:
            print(f"  ❌ Error inesperado extrayendo del chunk: {type(e).__name__}: {e}")
            return []
    
    def build_from_text(self, text: str, verbose: bool = True) -> Dict[str, Any]:
        chunks = self._split_text(text)
        if verbose:
            print(f"📄 Procesando {len(chunks)} fragmentos...")
        
        all_relations = []
        # Línea para probar con 5 chunks
        # chunks = chunks[:5] if len(chunks) > 5 else chunks

        for i, chunk in enumerate(chunks):
            print(f"Extrayendo el fragmento {i+1}/{len(chunks)}...")
            preview = chunk[:600].replace("\n", " ")
            print(f"Chunk extraído (preview): {preview}")
            for rel in self._extract_from_chunk(chunk):
                rel["node_1"] = self._normalize_text(rel.get("node_1", ""))
                rel["node_2"] = self._normalize_text(rel.get("node_2", ""))
                rel["edge"] = self._normalize_text(rel.get("edge", "related")) or "related"
                if rel["node_1"] and rel["node_2"] and rel["node_1"] != rel["node_2"]:
                    all_relations.append(rel)
        
        if not all_relations:
            return {"nodes": [], "edges": [], "networkx": None}
        
        # Agrupar relaciones
        edge_groups = {}
        for rel in all_relations:
            key = tuple(sorted([rel["node_1"], rel["node_2"]])) # Evita duplicados invertidos
            if key not in edge_groups:
                edge_groups[key] = []
            edge_groups[key].append(self._normalize_text(rel.get("edge", "related")) or "related")
        
        edges = [{"node_1": k[0], "node_2": k[1], "edge": "; ".join(set(v))} for k, v in edge_groups.items()]
        nodes = list(set(e["node_1"] for e in edges) | set(e["node_2"] for e in edges))
        
        G = None
        G = nx.Graph()
        G.add_nodes_from(nodes)
        for e in edges:
            G.add_edge(e["node_1"], e["node_2"], label=e["edge"])
        
        if verbose:
            print(f"✅ Grafo: {len(nodes)} nodos, {len(edges)} relaciones")
        
        return {"nodes": nodes, "edges": edges, "networkx": G}
    
    def visualize(self, graph: Dict, output_path: str = "graph.html", open_browser: bool = True) -> Optional[str]:
        G = graph["networkx"]
        colors = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4", "#46f0f0", "#f032e6"]
        
        for i, node in enumerate(G.nodes()):
            G.nodes[node]["color"] = colors[i % len(colors)]
            G.nodes[node]["size"] = G.degree(node) * 5 + 15
            G.nodes[node]["title"] = node
        
        net = Network(height="800px", width="100%", bgcolor="#222222", font_color="#ffffff", notebook=False, cdn_resources="remote")
        net.from_nx(G)
        net.force_atlas_2based(central_gravity=0.01, gravity=-50)
        
        output_path = str(Path(output_path).resolve())
        net.save_graph(output_path)
        print(f"📊 Guardado: {output_path}")
        
        if open_browser:
            import webbrowser
            webbrowser.open(f"file://{output_path}")
        return output_path
    
    def to_json(self, graph: Dict) -> str:
        return json.dumps({"nodes": graph["nodes"], "edges": graph["edges"]}, indent=2, ensure_ascii=False)

    # ═══════════════════════════════════════════════════════════
    # CONEXIÓN NEO4J AURA (cloud)
    # ═══════════════════════════════════════════════════════════

    def _get_neo4j_driver(self):
        """Crea y devuelve un driver de Neo4j usando las variables de entorno."""
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD")

        return GraphDatabase.driver(uri, auth=(user, password))

    def verify_neo4j_connection(self) -> bool:
        """Verifica que la conexión a Neo4j Aura funcione."""
        driver = self._get_neo4j_driver()
        try:
            driver.verify_connectivity()
            print("✅ Conexión a Neo4j Aura establecida correctamente")
            return True
        except Exception as e:
            print(f"❌ Error conectando a Neo4j: {e}")
            return False
        finally:
            driver.close()
    # Esta función es relevante? 

    def save_to_neo4j(self, graph: Dict, client_id: str = "default") -> bool:
        """
        Guarda el grafo de conocimiento en Neo4j Aura.
        Cada nodo se crea como (:Concept) y cada arista como [:RELATED_TO].
        Se etiqueta todo con client_id para aislar datos por cliente.
        """
        if not graph.get("nodes"):
            print("⚠️  Grafo vacío, nada que guardar en Neo4j")
            return False

        driver = self._get_neo4j_driver()
        try:
            with driver.session() as session:
                # 1. Borrar grafo anterior de este cliente
                session.run(
                    "MATCH (c:Concept {client_id: $cid}) DETACH DELETE c",
                    cid=client_id,
                )

                # 2. Crear nodos
                for node_name in graph["nodes"]:
                    session.run(
                        """
                        CREATE (c:Concept {
                            name: $name,
                            client_id: $cid
                        })
                        """,
                        name=node_name,
                        cid=client_id,
                    )

                # 3. Crear relaciones
                for edge in graph["edges"]:
                    session.run(
                        """
                        MATCH (a:Concept {name: $n1, client_id: $cid})
                        MATCH (b:Concept {name: $n2, client_id: $cid})
                        CREATE (a)-[:RELATED_TO {label: $label}]->(b)
                        """,
                        n1=edge["node_1"],
                        n2=edge["node_2"],
                        label=edge.get("edge", "related"),
                        cid=client_id,
                    )

            nodes_count = len(graph["nodes"])
            edges_count = len(graph["edges"])
            print(f"✅ Guardado en Neo4j Aura: {nodes_count} nodos, {edges_count} relaciones (client: {client_id})")
            return True

        except Exception as e:
            print(f"❌ Error guardando en Neo4j: {e}")
            return False
        finally:
            driver.close()

    def load_from_neo4j(self, client_id: str = "default") -> Dict[str, Any]:
        """
        Carga el grafo de un cliente desde Neo4j y lo devuelve
        en el mismo formato que build_from_text().
        """
        driver = self._get_neo4j_driver()
        try:
            with driver.session() as session:
                # Obtener nodos
                result = session.run(
                    "MATCH (c:Concept {client_id: $cid}) RETURN c.name AS name",
                    cid=client_id,
                )
                nodes = [record["name"] for record in result]

                # Obtener relaciones
                result = session.run(
                    """
                    MATCH (a:Concept {client_id: $cid})-[r:RELATED_TO]->(b:Concept {client_id: $cid})
                    RETURN a.name AS node_1, b.name AS node_2, r.label AS edge
                    """,
                    cid=client_id,
                )
                edges = [{"node_1": r["node_1"], "node_2": r["node_2"], "edge": r["edge"]} for r in result]

            # Reconstruir grafo NetworkX
            G = nx.Graph()
            G.add_nodes_from(nodes)
            for e in edges:
                G.add_edge(e["node_1"], e["node_2"], label=e["edge"])

            print(f"📥 Cargado desde Neo4j: {len(nodes)} nodos, {len(edges)} relaciones (client: {client_id})")
            return {"nodes": nodes, "edges": edges, "networkx": G}

        except Exception as e:
            print(f"❌ Error cargando desde Neo4j: {e}")
            return {"nodes": [], "edges": [], "networkx": None}
        finally:
            driver.close()

    def delete_from_neo4j(self, client_id: str = "default") -> bool:
        """Elimina todos los nodos y relaciones de un cliente en Neo4j."""
        driver = self._get_neo4j_driver()
        try:
            with driver.session() as session:
                result = session.run(
                    "MATCH (c:Concept {client_id: $cid}) DETACH DELETE c RETURN count(c) AS deleted",
                    cid=client_id,
                )
                deleted = result.single()["deleted"]
                print(f"🗑️  Eliminados {deleted} nodos del cliente '{client_id}' en Neo4j")
                return True
        except Exception as e:
            print(f"❌ Error eliminando de Neo4j: {e}")
            return False
        finally:
            driver.close()

    def search_in_neo4j(self, search_terms: List[str], client_id: str = "default", max_depth: int = 2) -> Dict[str, Any]:
        """
        Busca conceptos relacionados con los términos dados.
        Navega hasta max_depth saltos de profundidad.
        Útil para dar contexto al LLM antes de responder.
        """
        driver = self._get_neo4j_driver()
        try:
            with driver.session() as session:
                # Buscar conceptos que contengan alguno de los términos
                result = session.run(
                    """
                    MATCH path = (start:Concept {client_id: $cid})-[*1..""" + str(max_depth) + """]->(end:Concept {client_id: $cid})
                    WHERE ANY(term IN $terms WHERE start.name CONTAINS term)
                    RETURN nodes(path) AS nodes, relationships(path) AS rels
                    LIMIT 50
                    """,
                    cid=client_id,
                    terms=[self._normalize_text(t) for t in search_terms if self._normalize_text(t)],
                )

                nodes_set = set()
                edges_list = []
                for record in result:
                    for node in record["nodes"]:
                        nodes_set.add(node["name"])
                    for rel in record["rels"]:
                        edges_list.append({
                            "node_1": rel.start_node["name"],
                            "node_2": rel.end_node["name"],
                            "edge": rel.get("label", "related"),
                        })

                nodes = list(nodes_set)
                print(f"🔍 Búsqueda Neo4j: {len(nodes)} conceptos encontrados para {search_terms}")
                return {"nodes": nodes, "edges": edges_list}

        except Exception as e:
            print(f"❌ Error buscando en Neo4j: {e}")
            return {"nodes": [], "edges": []}
        finally:
            driver.close()
