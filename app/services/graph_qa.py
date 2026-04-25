from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_groq import ChatGroq
# Para crear prompts personalizados
from langchain_core.prompts import PromptTemplate
import os
import re
from dotenv import load_dotenv
import unicodedata
import json

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
            temperature=0.3
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

    def _get_cypher_prompt(self, client_id: str, company_name: str) -> PromptTemplate:
        """
        Genera el prompt de sistema para que el LLM sepa traducir a Cypher.
        Aquí es donde filtramos por client_id por seguridad.
        """
        template = f"""
        Eres un experto en Neo4j. Tu unica salida debe ser una consulta Cypher valida.

        REGLAS ESTRUCTURALES (OBLIGATORIAS):
        1. Usa siempre nodos :Concept.
        2. Filtra siempre por client_id exacto usando propiedad: n.client_id = '{client_id}'.
        3. Devuelve siempre estas columnas:
            - principal.name AS entidad
            - properties(principal) AS propiedades_entidad
            - type(r) AS tipo_relacion
            - properties(r) AS propiedades_relacion
            - asociado.name AS conectado_a
        4. Usa OPTIONAL MATCH para no perder contexto parcial.

        REGLAS DE RECUPERACION:
        5. Si la pregunta es general (ej. "que es", "de que va", "resumen", "proyecto", "tecnologia"), haz una consulta panoramica del cliente sin asumir sector.
        6. Si la pregunta contiene terminos concretos, usa WHERE flexible con OR sobre principal.name para esos terminos.
        7. Si existe un nombre de empresa en la pregunta (por ejemplo "{company_name}"), prioriza tambien coincidencias por ese nombre.
        8. No uses APOC ni funciones no estandar.

        REGLAS ANTI-ERRORES (MUY IMPORTANTE):
        9. Evita comparaciones exactas sensibles a mayusculas/minusculas (NO uses principal.name = 'Noctua').
        10. Para texto usa toLower(... ) CONTAINS toLower('termino').
        11. No pongas un WHERE que filtre asociado justo despues de OPTIONAL MATCH si puede dejar filas nulas inutiles.
        12. Cuando filtres por texto, aplica el WHERE sobre principal tras el MATCH principal.
        13. No uses tokens de 1-2 caracteres para buscar por CONTAINS (ej. "ia"). Usa frases completas o terminos de 3+ caracteres.

        Esquema de la base de datos:
        {{schema}}

        Pregunta del usuario: {{question}}
        Consulta Cypher pura (sin markdown ni explicaciones):
        """

        return PromptTemplate(input_variables=["schema", "question"], template=template)
    
    def _get_qa_prompt(self, company_name: str) -> PromptTemplate:
        """
        Genera el prompt de respuesta inyectando el contexto de la empresa del cliente.
        """
        template = f"""
    Eres un asistente de atencion al cliente en espanol.
    ACTUALMENTE TRABAJAS PARA: {company_name}.

    REGLA PRINCIPAL (OBLIGATORIA):
    - Responde EXCLUSIVAMENTE con la informacion del "Contexto extraido".
    - No uses conocimiento general del mundo, aunque creas conocer la marca por fuera del contexto.
    - No asumas el sector por el nombre comercial.

    REGLAS DE FIABILIDAD:
    1. Si el contexto es vacio o insuficiente, dilo de forma breve y transparente.
    2. Si falta contexto, haz una sola pregunta de clarificacion util para recuperar mejor informacion.
    3. No inventes datos, productos, servicios, precios, cifras ni caracteristicas.
    4. No menciones competidores ni servicios externos.
    5. No asumas sector (ej. retail, salud, legal, hardware, educacion) salvo que aparezca literal en el contexto.

    ESTILO:
    1. Respuesta clara, breve y profesional.
    2. Sin jerga tecnica de bases de datos.
    3. Cuando haya datos en contexto, citalos de forma concreta en lenguaje natural.
     4. Habla en voz directa para usuario final, no en modo "analista".
     5. PROHIBIDO usar frases metadiscursivas como:
         - "segun la informacion disponible"
         - "se menciona"
         - "en el contexto proporcionado"
         - "de acuerdo con la informacion"
         - "con la informacion proporcionada"
     6. Si faltan datos, dilo natural y breve. Ejemplo: "Ahora mismo no tengo ese dato concreto."

    Contexto extraido:
    {{context}}

    Pregunta del usuario:
    {{question}}

    Respuesta natural en espanol:
        """

        return PromptTemplate(input_variables=["context", "question"], template=template)

    @staticmethod
    def _contains_meta_language(answer_text: str) -> bool:
        normalized = quitar_tildes(answer_text or "").lower()
        markers = (
            "segun la informacion disponible",
            "se menciona",
            "en el contexto proporcionado",
            "de acuerdo con la informacion",
            "con la informacion proporcionada",
            "segun el contexto",
        )
        return any(marker in normalized for marker in markers)

    def _rewrite_direct_style(self, answer_text: str, company_name: str) -> str:
        """Reescribe respuestas con tono metadiscursivo a tono directo de atencion al cliente."""
        rewrite_prompt = f"""
        Reescribe el siguiente texto para un usuario final de {company_name}.

        REGLAS:
        - Mantener los mismos hechos.
        - No inventar nada nuevo.
        - Tono directo, natural y profesional.
        - No usar frases como "se menciona", "segun la informacion disponible", "en el contexto proporcionado".
        - Si faltan datos, usar una frase breve y natural.

        Texto original:
        {answer_text}

        Texto reescrito:
        """
        rewritten = self.qa_llm.invoke(rewrite_prompt)
        return getattr(rewritten, "content", str(rewritten))

    @staticmethod
    def _company_terms(company_name: str) -> list[str]:
        normalized = quitar_tildes(company_name or "").lower().strip()
        if not normalized:
            return []
        tokens = re.findall(r"[a-z0-9]+", normalized)
        terms = [normalized]
        for token in tokens:
            if len(token) >= 3 and token not in terms:
                terms.append(token)
        return terms[:8]

    @staticmethod
    def _question_terms(question: str) -> list[str]:
        q_raw = (question or "").lower()
        q_norm = quitar_tildes(question or "").lower()
        tokens_raw = re.findall(r"[a-z0-9áéíóúñü]+", q_raw)
        tokens_norm = re.findall(r"[a-z0-9]+", q_norm)
        stopwords = {
            "hola", "que", "de", "del", "la", "el", "los", "las", "un", "una",
            "por", "para", "con", "sin", "sobre", "este", "esta", "esto", "es", "va",
            "quiero", "saber", "comenta", "comentame", "proyecto",
        }
        terms = []
        for token in tokens_raw + tokens_norm:
            if len(token) < 3:
                continue
            if token in stopwords:
                continue
            if token not in terms:
                terms.append(token)
        return terms[:8]

    @staticmethod
    def _is_general_question(question: str) -> bool:
        q = quitar_tildes(question or "").lower()
        general_patterns = [
            r"\bque es\b",
            r"\bde que va\b",
            r"\bde que trata\b",
            r"\bresumen\b",
            r"\bexplicame\b",
            r"\bpresentate\b",
            r"\bproyecto\b",
            r"\bque hace\b",
        ]
        return any(re.search(p, q) for p in general_patterns)

    def _answer_from_context(self, question: str, company_name: str, context_rows: list[dict]) -> str:
        qa_prompt = self._get_qa_prompt(company_name)
        prompt_input = qa_prompt.format(
            context=json.dumps(context_rows, ensure_ascii=False),
            question=question,
        )
        answer = self.qa_llm.invoke(prompt_input)
        answer_text = getattr(answer, "content", str(answer))

        if self._contains_meta_language(answer_text):
            try:
                answer_text = self._rewrite_direct_style(answer_text, company_name)
            except Exception:
                pass

        return answer_text

    def _get_seed_context(
        self,
        client_id: str,
        company_name: str,
        question: str | None = None,
        limit: int = 40,
        use_company_fallback: bool = True,
    ):
        """Contexto de respaldo generico para preguntas amplias o con poco resultado."""
        if not self.graph:
            return []

        company_terms = self._company_terms(company_name)
        question_terms = self._question_terms(question or "")

        combined_terms = []
        for term in question_terms + company_terms:
            if term not in combined_terms:
                combined_terms.append(term)
        combined_terms = combined_terms[:12]

        query_by_terms = """
        MATCH (principal:Concept {client_id: $cid})
        OPTIONAL MATCH (principal)-[r:RELATED_TO]-(asociado:Concept {client_id: $cid})
        WITH principal, r, asociado
        WHERE ANY(term IN $terms
              WHERE toLower(principal.name) CONTAINS term
                 OR toLower(coalesce(asociado.name, '')) CONTAINS term)
        RETURN
            principal.name AS entidad,
            properties(principal) AS propiedades_entidad,
            type(r) AS tipo_relacion,
            properties(r) AS propiedades_relacion,
            asociado.name AS conectado_a
        LIMIT $row_limit
        """

        query_panorama = """
        MATCH (principal:Concept {client_id: $cid})
        OPTIONAL MATCH (principal)-[:RELATED_TO]-(:Concept {client_id: $cid})
        WITH principal, count(*) AS grado
        ORDER BY grado DESC, principal.name ASC
        LIMIT $limit
        OPTIONAL MATCH (principal)-[r:RELATED_TO]-(asociado:Concept {client_id: $cid})
        RETURN
            principal.name AS entidad,
            properties(principal) AS propiedades_entidad,
            type(r) AS tipo_relacion,
            properties(r) AS propiedades_relacion,
            asociado.name AS conectado_a
        LIMIT $row_limit
        """

        try:
            if question_terms:
                by_question = self.graph.query(
                    query_by_terms,
                    params={"cid": client_id, "terms": question_terms, "row_limit": limit * 3},
                )
                if by_question:
                    return by_question

            if not use_company_fallback:
                return []

            if company_terms:
                by_company = self.graph.query(
                    query_by_terms,
                    params={"cid": client_id, "terms": company_terms, "row_limit": limit * 3},
                )
                if by_company:
                    return by_company

            if combined_terms:
                by_combined = self.graph.query(
                    query_by_terms,
                    params={"cid": client_id, "terms": combined_terms, "row_limit": limit * 3},
                )
                if by_combined:
                    return by_combined

            return self.graph.query(
                query_panorama,
                params={"cid": client_id, "limit": limit, "row_limit": limit * 3},
            )
        except Exception:
            return []
    
    def process_question(self, question: str, client_id: str, company_name: str):
        """
        Orquesta toda la magia:
        Pregunta -> LLM (Cypher) -> Neo4j (Datos) -> LLM (Respuesta final)
        Procesa la pregunta y devuelve la respuesta utilizando el grafo.
        """

        question_original = question
        question_limpia = quitar_tildes(question)
        if not self.graph: 
            return {"error": "No hay conexión con la base de datos de grafos"}

        # Para preguntas generales, usamos primero un contexto semilla estable.
        # Evita depender de una query Cypher generada que pueda venir demasiado vaga.
        if self._is_general_question(question_original):
            seed_context = self._get_seed_context(client_id, company_name, question=question_original)
            if seed_context:
                return {
                    "query": question_original,
                    "result": self._answer_from_context(question_original, company_name, seed_context)
                }

        # Para preguntas especificas, probamos primero contexto focalizado
        # por terminos de la pregunta sin contaminar con contexto general.
        focused_context = self._get_seed_context(
            client_id,
            company_name,
            question=question_original,
            limit=20,
            use_company_fallback=False,
        )
        if focused_context:
            return {
                "query": question_original,
                "result": self._answer_from_context(question_original, company_name, focused_context)
            }
        
        try:
            # Crear la cadena RAG
            chain = GraphCypherQAChain.from_llm(
                cypher_llm=self.llm, # Genera la query Cypher
                qa_llm=self.qa_llm,     # Genera la respuesta final (hablada)
                graph= self.graph,
                cypher_prompt=self._get_cypher_prompt(client_id, company_name),
                qa_prompt=self._get_qa_prompt(company_name),
                allow_dangerous_requests=True,
                verbose=True
            )

            # Ejecutar consulta principal
            result = chain.invoke({"query": question_limpia})

            # Fallback cuando el resultado es vacio o poco informativo
            answer_text = str(result.get("result", "")).strip().lower()
            normalized_answer = quitar_tildes(answer_text)
            low_info_markers = (
                "no veo informacion",
                "no tengo informacion",
                "contexto insuficiente",
                "no aparece en el contexto",
                "no tengo suficiente informacion",
                "no tengo mas informacion",
                "no hay mas informacion",
                "no hay mas detalles",
                "no puedo determinar",
                "podrias proporcionar mas contexto",
                "podrias proporcionar mas detalles",
                "necesito mas contexto",
                "parece estar relacionado",
            )
            needs_fallback = (not answer_text) or any(m in normalized_answer for m in low_info_markers)

            if needs_fallback:
                seed_context = self._get_seed_context(client_id, company_name, question=question_limpia)
                if seed_context:
                    result["result"] = self._answer_from_context(
                        question_original,
                        company_name,
                        seed_context,
                    )

            return result
        
        except Exception as e:
            return {"error": str(e)}
        
qa_service = GraphQAService()