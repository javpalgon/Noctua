import asyncio
import httpx
from fastapi import FastAPI, Depends,  HTTPException, BackgroundTasks    
from pydantic import BaseModel, HttpUrl
from db.database import engine, Base, get_db
from sqlalchemy.orm import Session
import db.models_db as models_db # Importar modelos para que SQLAlchemy los reconozca
from models import ClientConfig
from schedule_knowledge import rastreo_web

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Noctua - Plataforma de Grafos de Conocimiento")

class ClienteCreate(BaseModel):
    company_name: str
    url_portal: HttpUrl

async def validar_url(url: HttpUrl):
    """Valida que la URL existe haciendo una petición HTTP HEAD."""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.head(str(url))
        if response.status_code == 404:
            raise HTTPException(status_code=422, detail="La URL no existe (404)")
        elif response.status_code in (401,403):
            raise HTTPException(status_code=422, detail="La URL requiere autenticación o está bloqueada (401/403)")
        elif response.status_code >= 500:
            raise HTTPException(status_code=422, detail="Error del servidor de la URL está caído temporalmente")
    except httpx.ConnectError:
        raise HTTPException(status_code=422, detail="No se pudo conectar a la URL")
    except httpx.TimeoutException:
        raise HTTPException(status_code=422, detail="La URL superó el timeout")
    
def generar_grafo_segundo_plano(cliente_id: str, company_name: str, url_portal: HttpUrl):
    """Función que se ejecuta en segundo plano para generar el grafo de conocimiento."""
    cliente_config = ClientConfig(
        company_name=company_name,
        url_portal=url_portal,
        client_id=cliente_id
    )
    asyncio.run(rastreo_web(cliente_config))

# ── Endpoints ────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"message": "Bienvenido a Noctua - Plataforma de Grafos de Conocimiento"}

@app.post("/clientes")
async def create_cliente(cliente: ClienteCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    
    await validar_url(cliente.url_portal)
    
    nuevo_cliente = models_db.Cliente(
        company_name=cliente.company_name,
        url_portal=str(cliente.url_portal)
    )

    db.add(nuevo_cliente)
    db.commit()
    db.refresh(nuevo_cliente)

    background_tasks.add_task(
        generar_grafo_segundo_plano,
        cliente_id=nuevo_cliente.id,
        company_name=nuevo_cliente.company_name,
        url_portal=nuevo_cliente.url_portal
    )

    return {
        "id": nuevo_cliente.id,
        "company_name": nuevo_cliente.company_name,
        "url_portal": nuevo_cliente.url_portal,
        "message": "Cliente creado y proceso de generación de grafo iniciado en segundo plano"
    }