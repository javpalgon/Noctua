# Noctua: Plataforma B2B Avanzada de IA con GraphRAG (TFG)

Bienvenido a **Noctua**, un Trabajo de Fin de Grado (TFG) diseñado para revolucionar el ecosistema de los asistentes conversacionales en entornos corporativos (B2B). 

## ¿Qué es Noctua?
Noctua es una plataforma SaaS que permite a cualquier empresa integrar un asistente de IA experto en su negocio en menos de 2 minutos. A diferencia de los chatbots tradicionales, Noctua **no requiere entrenamiento manual, configuraciones complejas ni reglas predefinidas**.

Noctua nace con una filosofia clara:
- **Autoaprendizaje sin friccion**: el conocimiento se genera desde la web del cliente.
- **Aislamiento por cliente**: cada negocio tiene su propio grafo y memoria.
- **Respuesta controlada**: se evita conocimiento externo para reducir riesgos.

## ¿Cómo funciona el motor de Inteligencia Artificial (GraphRAG)?
Para evitar las **alucinaciones** (que el LLM invente respuestas), Noctua utiliza un sistema híbrido que llamamos **GraphRAG (Retrieval-Augmented Generation apoyado en Grafos de Conocimiento)**:
1. **Rastreo Automático (Crawling)**: El sistema raspa la web que le indigues usando `crawl4ai`.
2. **Construcción del Grafo**: A través de modelos OpenSource (Llama3/Zephyr vía Ollama local), extrae entidades y relaciones para formar un "Grafo de Conocimiento".
3. **Almacenamiento**: Estos grafos se almacenan en una base de datos orientada a grafos (**Neo4j Aura Cloud**).
4. **Respuestas Precisas**: Cuando un cliente pregunta en el widget, Noctua primero busca el contexto exacto cruzando los nodos en Neo4j y luego formula una respuesta determinista a través de LangChain y Groq.

Flujo resumido (de principio a fin):
1. Usuario crea un chatbot desde el portal y proporciona URL.
2. El backend valida la URL y lanza el rastreo en segundo plano.
3. Se limpia el contenido y se extraen entidades y relaciones.
4. Se guarda el grafo por `client_id`.
5. El widget inicia una sesion y pregunta con contexto.

Elementos clave del motor:
- **Chunking inteligente**: fragmentos con solapamiento para mantener contexto.
- **Filtrado de ruido**: se descartan URLs, scripts, rutas y ruido tecnico.
- **Prompts estrictos**: reglas para filtrar alucinaciones y sesgos de marca.

## Tecnología y Arquitectura
- **Backend (API Core)**: Python con FastAPI de altísimo rendimiento.
- **Base de Datos Relacional**: PostgreSQL (para almacenar datos de los clientes y sus Client IDs).
- **Base de Datos de Contexto (Conocimiento AI)**: Neo4j Aura, la base de datos de grafos líder del sector.
- **Memoria de Chat**: Redis. Garantiza la persistencia ultra rápida de las sesiones de los usuarios a gran escala.
- **Orquestación de IA**: LangChain.
- **Frontend / Portal Web**: Vanilla HTML, CSS y React (sin build tools), desplegando una interfaz Glassmorphism estilo Vercel.
- **Widget Embebido**: JavaScript puro, optimizado en base a `sessionStorage` para mantener la conversación cliente a cliente.

Servicios y componentes internos:
- `schedule_knowledge.py`: rastreo web + limpieza de texto + generacion del grafo.
- `knowledge_graph_builder.py`: extraccion de entidades y relaciones, guardado Neo4j.
- `graph_qa.py`: consultas en Neo4j y redaccion de respuestas.
- `chat_session_store_redis.py`: memoria de sesion efimera para el widget.

## Seguridad y Limitación de Contexto (B2B)
El prompt central de Noctua siempre obliga al asistente a **jamás mencionar servicios externos, empresas de la competencia o enlaces fuera del dominio del cliente**. El objetivo de Noctua es retener al cliente dentro de la corporación.

Controles adicionales:
- Filtro por `client_id` en todas las consultas de Neo4j.
- Reescritura de respuestas con lenguaje directo para el cliente.
- Evita asumir sector o categoria si no aparece en el contenido real.

## Despliegue Rápido
Para integrarlo, sólo necesitas copiar y pegar el script `<script src="http://.../noctua-widget.js"></script>` en la etiqueta `<body>` del HTML de la empresa. Noctua hace el resto.

## Casos de uso B2B
- **SaaS**: resolver dudas sobre planes, integraciones y onboarding.
- **Ecommerce B2B**: responder sobre catalogos, plazos y politicas.
- **Formacion**: explicar temarios, calendarios y requisitos.
- **Servicios Profesionales**: filtrar preguntas frecuentes y derivar leads.

## Feature destacada: Actualizar Grafo
Cuando el cliente actualiza su web, el grafo puede quedar obsoleto. Noctua incluye un flujo para **actualizar el grafo**:
- Se vuelve a rastrear la URL del cliente.
- Se genera el grafo con el contenido actualizado.
- Se reemplaza el grafo anterior por el nuevo (mismo `client_id`).

Esto permite probar facilmente si el chatbot refleja contenido nuevo sin crear un bot distinto.

## Endpoints principales (referencia)
- `POST /auth/register` -> crea usuario
- `POST /auth/login` -> login
- `GET /me/chatbots` -> lista bots del usuario
- `POST /clientes` -> crea bot y dispara rastreo
- `POST /clientes/{id}/refresh` -> actualiza grafo del bot
- `POST /chat/session/start` -> inicia sesion de chat
- `POST /chat` -> envia pregunta

## Prompt de demo (ejemplos)
Preguntas que el widget puede responder si el grafo esta actualizado:
- "Que es Noctua y para que sirve?"
- "Como se construye el grafo de conocimiento?"
- "Que tecnologias usa el backend?"
- "Como evita las alucinaciones?"
- "Como funciona la actualizacion del grafo?"

## Roadmap
- Version 2.1: indicadores de estado de rastreo en dashboard.
- Version 2.2: control de profundidad de rastreo por cliente.
- Version 2.3: panel de edicion de prompts por marca.
- Version 3.0: multi-idioma y deteccion automatica de idioma.

## FAQ
**El chatbot aprende de fuentes externas?**
No. Solo responde con el contexto obtenido del rastreo.

**Puedo forzar una actualizacion del conocimiento?**
Si. Usa el boton "Actualizar grafo" en el dashboard.

**Que ocurre si no hay contenido suficiente?**
El asistente devuelve una respuesta breve y puede pedir una aclaracion.

**Se puede incrustar en cualquier web?**
Si. Solo necesitas el script del widget y el `client_id`.
