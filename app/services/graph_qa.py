from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
# Para crear prompts personalizados
from langchain_core.prompts import PromptTemplate
import os
from dotenv import load_dotenv
import unicodedata

load_dotenv()

def quitar_tildes(texto: str) -> str:
    """Elimina tildes y acentos para mejorar la coincidencia en el LLM"""
    texto_normalizado = unicodedata.normalize('NFD', texto)
    texto_sin_tildes = ''.join(
        c for c in texto_normalizado if unicodedata.category(c) != 'Mn'
    )
    return texto_sin_tildes

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
        3. BÚSQUEDA FLEXIBLE Y APODOS (MUY IMPORTANTE): Si el usuario usa apodos ("Paquito", "Ari", "Ale", "Momo"), nombres incompletos o abreviaturas, DEBES usar tu conocimiento general para expandir la búsqueda en la cláusula WHERE usando OR
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
    
    def _get_qa_prompt(self, company_name: str) -> PromptTemplate:
        """
        Genera el prompt de respuesta inyectando el contexto de la empresa del cliente.
        """
        template = f"""
    Eres un asistente de atención al cliente en español.
    ACTUALMENTE TRABAJAS PARA: {company_name}. Debes sonar como un empleado real de la marca.

        OBJETIVO:
    - Prioriza responder con la información del "Contexto extraído".
    - Sonar cercano, profesional y orientado a ayudar como lo haría un vendedor experto de {company_name}.

        REGLAS DE FIABILIDAD (ANTIALUCINACIONES):
        1. DATOS DEL CLIENTE: No inventes datos específicos de {company_name}. Si algo no aparece en el contexto, dilo con claridad.
        2. PRECISIÓN: Cuando haya datos en el contexto, usa valores exactos (nombres, números, relaciones) sin alterarlos.
        3. CONTEXTO INSUFICIENTE: Si el contexto está vacío ([]) o no alcanza para responder con certeza sobre datos del cliente:
              - Primero indícalo de forma natural y breve (ej: "Ahora mismo no veo ese dato concreto en la información disponible.").
              - Después, en lugar de dar recomendaciones genéricas externas, haz una pregunta de clarificación útil para poder recomendar mejor dentro de {company_name}.
                 Ejemplos de clarificación: uso principal (running/gym/casual), presupuesto aproximado, preferencias de comodidad/estilo, superficie de uso.
              - Si decides dar orientación general, debe ser breve, práctica y siempre enfocada al catálogo de {company_name} (sin mencionar otras tiendas ni comercios externos).
              - Nunca presentes orientación general como si fuera dato confirmado del cliente.
        4. RESOLUCIÓN DE ENTIDADES: Si el usuario usa apodos o nombres abreviados y el contexto apunta claramente a una persona concreta, responde con seguridad usando el nombre completo.
          5. PROHIBIDO INVENTAR PRODUCTOS: No inventes nombres de modelos, precios, stock o características concretas que no estén en el contexto.

        REGLAS DE ESTILO:
        1. No uses jerga técnica de bases de datos (nodo, grafo, relación, label, propiedad, etc.).
        2. Tono humano, directo y profesional. Evita respuestas mecánicas o plantillas rígidas.
    3. Si falta contexto, evita frases frías tipo "no tengo información" como única respuesta; combina transparencia + siguiente paso útil.
    4. No recomiendes "mirar en minoristas", "otras tiendas" ni canales fuera de {company_name}.

        Contexto extraído:
        {{context}}

        Pregunta del usuario:
        {{question}}

        Respuesta natural en español:
        """

        return PromptTemplate(input_variables=["context", "question"], template=template)
    
    def process_question(self, question: str, client_id: str, company_name: str):
        """
        Orquesta toda la magia:
        Pregunta -> LLM (Cypher) -> Neo4j (Datos) -> LLM (Respuesta final)
        Procesa la pregunta y devuelve la respuesta utilizando el grafo.
        """

        question_limpia = quitar_tildes(question)
        if not self.graph: 
            return {"error": "No hay conexión con la base de datos de grafos"}
        
        try:
            # Crear la cadena RAG
            chain = GraphCypherQAChain.from_llm(
                cypher_llm=self.llm, # Genera la query Cypher
                qa_llm=self.qa_llm,     # Genera la respuesta final (hablada)
                graph= self.graph,
                cypher_prompt=self._get_cypher_prompt(client_id),
                qa_prompt=self._get_qa_prompt(company_name),
                allow_dangerous_requests=True,
                verbose=True
            )

            #Ejecutar consulta
            return chain.invoke({"query": question_limpia})
        
        except Exception as e:
            return {"error": str(e)}
        
qa_service = GraphQAService()