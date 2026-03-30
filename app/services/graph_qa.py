from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
# Para crear prompts personalizados
from langchain_core.prompts import PromptTemplate
import os
from dotenv import load_dotenv

load_dotenv()

class GraphQAService:
    def __init__(self):
        # Configuración de la conexión a Neo4j
        self.neo4j_url = os.getenv("NEO4J_URI")
        self.neo4j_user = os.getenv("NEO4J_USER")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD")

        # Configurar el LLM de Ollama
        # self.ollama_url = os.getenv("OLLAMA_URL")
        # self.ollama_model = os.getenv("OLLAMA_MODEL")

        self.groq_api_key = os.getenv("GROQ_API_KEY")

        # Programador de Cypher
        self.llm = ChatGroq(
            api_key=self.groq_api_key,
            model="llama-3.3-70b-versatile",
            temperature=0
        )

        # El redactor de respuestas humanas
        self.qa_llm = ChatGroq(
            api_key=self.groq_api_key,
            model="llama-3.3-70b-versatile",
            temperature=0.7
        )
        try: 
            # Conexión al grafo
            self.graph = Neo4jGraph(
                url = self.neo4j_url,
                username = self.neo4j_user, 
                password = self.neo4j_password
            )
            # Refrescar el esquema al inicar para que el LLM sepa qué nodos existen
            self.graph.refresh_schema()
        except Exception as e:
            print(f"Error al conectar a Neo4j: {e}")
            self.graph = None

    def _get_cypher_prompt(self, client_id: str) -> PromptTemplate:
        """
        Genera el prompt de sistema para que el LLM sepa traducir a Cypher.
        Aquí es donde filtramos por client_id por seguridad.
        """
        template = f"""
        Eres un experto desarrollador de Neo4j y el motor de un sistema GraphRAG universal. 

        REGLAS ESTRUCTURALES DE ORO:
        1. Trabajas SIEMPRE con nodos de etiqueta `:Concept`.
        2. SEGURIDAD: Inicia filtrando por el `client_id` exacto: MATCH (n:Concept {{{{client_id: '{client_id}'}}}})
        
        REGLAS DE BÚSQUEDA (¡CRÍTICO!):
        3. Busca la entidad principal con regex flexible: WHERE principal.name =~ '(?i).*palabra_clave.*'
        4. USA OPTIONAL MATCH para las relaciones. Si el nodo tiene el ranking como propiedad interna pero no tiene relaciones, no queremos perder esa información.
        5. EXTRAE TODO EL CONTEXTO: Necesito las propiedades internas del nodo (por si ahí están el ranking o los puntos), el tipo de relación, las propiedades de la relación y el nodo conectado.

        EJEMPLO DE CONSULTA QUE DEBES GENERAR:
        ---
        MATCH (principal:Concept {{{{client_id: '{client_id}'}}}})
        WHERE principal.name =~ '(?i).*javier.*'
        OPTIONAL MATCH (principal)-[r]-(asociado:Concept)
        RETURN 
            principal.name AS entidad, 
            properties(principal) AS propiedades_entidad,
            type(r) AS tipo_relacion,
            properties(r) AS propiedades_relacion,
            asociado.name AS conectado_a
        LIMIT 25
        ---
        
        Esquema de la base de datos:
        {{schema}}

        Pregunta del usuario: {{question}}
        Consulta Cypher pura (sin notas ni markdown ni explicaciones):
        """

        return PromptTemplate(input_variables=["schema", "question"], template=template)
    
    def process_question(self, question: str, client_id: str):
        """
        Orquesta toda la magia:
        Pregunta -> LLM (Cypher) -> Neo4j (Datos) -> LLM (Respuesta final)
        Procesa la pregunta y devuelve la respuesta utilizando el grafo.
        """
        if not self.graph: 
            return {"error": "No hay conexión con la base de datos de grafos"}
        
        try:
            # Crear la cadena RAG
            chain = GraphCypherQAChain.from_llm(
                cypher_llm=self.llm, # Genera la query Cypher
                qa_llm=self.qa_llm,     # Genera la respuesta final (hablada)
                graph= self.graph,
                cypher_prompt=self._get_cypher_prompt(client_id),
                allow_dangerous_requests=True,
                verbose=True
            )

            #Ejecutar consulta
            return chain.invoke({"query": question})
        
        except Exception as e:
            return {"error": str(e)}
        
qa_service = GraphQAService()