# Noctua: Plataforma B2B Avanzada de IA con GraphRAG (TFG)

Bienvenido a **Noctua**, un Trabajo de Fin de Grado (TFG) diseñado para revolucionar el ecosistema de los asistentes conversacionales en entornos corporativos (B2B). 

## ¿Qué es Noctua?
Noctua es una plataforma SaaS que permite a cualquier empresa integrar un asistente de IA experto en su negocio en menos de 2 minutos. A diferencia de los chatbots tradicionales, Noctua **no requiere entrenamiento manual, configuraciones complejas ni reglas predefinidas**.

## ¿Cómo funciona el motor de Inteligencia Artificial (GraphRAG)?
Para evitar las **alucinaciones** (que el LLM invente respuestas), Noctua utiliza un sistema híbrido que llamamos **GraphRAG (Retrieval-Augmented Generation apoyado en Grafos de Conocimiento)**:
1. **Rastreo Automático (Crawling)**: El sistema raspa la web que le indigues usando `crawl4ai`.
2. **Construcción del Grafo**: A través de modelos OpenSource (Llama3/Zephyr vía Ollama local), extrae entidades y relaciones para formar un "Grafo de Conocimiento".
3. **Almacenamiento**: Estos grafos se almacenan en una base de datos orientada a grafos (**Neo4j Aura Cloud**).
4. **Respuestas Precisas**: Cuando un cliente pregunta en el widget, Noctua primero busca el contexto exacto cruzando los nodos en Neo4j y luego formula una respuesta determinista a través de LangChain y Groq.

## Tecnología y Arquitectura
- **Backend (API Core)**: Python con FastAPI de altísimo rendimiento.
- **Base de Datos Relacional**: PostgreSQL (para almacenar datos de los clientes y sus Client IDs).
- **Base de Datos de Contexto (Conocimiento AI)**: Neo4j Aura, la base de datos de grafos líder del sector.
- **Memoria de Chat**: Redis. Garantiza la persistencia ultra rápida de las sesiones de los usuarios a gran escala.
- **Orquestación de IA**: LangChain.
- **Frontend / Portal Web**: Vanilla HTML, CSS y React (sin build tools), desplegando una interfaz Glassmorphism estilo Vercel.
- **Widget Embebido**: JavaScript puro, optimizado en base a `sessionStorage` para mantener la conversación cliente a cliente.

## Seguridad y Limitación de Contexto (B2B)
El prompt central de Noctua siempre obliga al asistente a **jamás mencionar servicios externos, empresas de la competencia o enlaces fuera del dominio del cliente**. El objetivo de Noctua es retener al cliente dentro de la corporación.

## Despliegue Rápido
Para integrarlo, sólo necesitas copiar y pegar el script `<script src="http://.../noctua-widget.js"></script>` en la etiqueta `<body>` del HTML de la empresa. Noctua hace el resto.
