# 🦉 Accesos y URLs de Noctua

Aquí tienes los enlaces directos a los servicios de la plataforma tal y como los tienes configurados ahora (Entorno Híbrido: BD en Docker + App en Local).

## 🌍 Aplicación Web (FastAPI)
- **Inicio:** http://localhost:8000
- **Documentación Interactiva (Swagger UI):** http://localhost:8000/docs
- **Documentación Alternativa (Redoc):** http://localhost:8000/redoc

## 🕸️ Bases de Datos (Docker)

### Neo4j (Grafos)
- **Browser (Interfaz Visual):** http://localhost:7474
- **Connect URL:** `bolt://localhost:7687`
- **Usuario:** `neo4j`
- **Contraseña:** `noctua_dev`

### PostgreSQL (Datos Relacionales)
- **Host:** `localhost`
- **Puerto:** `5432`
- **Base de Datos:** `noctua`
- **Usuario:** `noctua`
- **Contraseña:** `noctua_dev`

---

## 🚀 Cómo arrancar todo

1. **Levantar Bases de Datos (Docker):**
   ```bash
   docker compose up -d
   ```

2. **Levantar App Web (Local):**
   ```bash
   ./run_local.sh
   ```
   *(O si prefieres manual)*:
   ```bash
   source venv/bin/activate
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
