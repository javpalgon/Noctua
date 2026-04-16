import asyncio
import httpx
from fastapi import FastAPI, Depends,  HTTPException, BackgroundTasks    
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from app.db.database import engine, Base, get_db
from sqlalchemy.orm import Session
import app.db.models_db as models_db # Importar modelos para que SQLAlchemy los reconozca
from app.schemas.client import ClientConfig
from app.services.schedule_knowledge import rastreo_web
from app.services.graph_qa import GraphQAService
from app.services.session_store_factory import create_chat_store
from datetime import datetime

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Noctua - Plataforma de Grafos de Conocimiento")

# CORS para pruebas locales del widget (frontend en otro puerto)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

qa_service = GraphQAService()
chat_store = create_chat_store()

class ClienteCreate(BaseModel):
    company_name: str
    url_portal: HttpUrl

class ChatRequest(BaseModel):
    client_id: str
    company_name: str
    session_id: str # Para que el sistema recuerde el contexto de la conversación
    question: str

class SessionStartRequest(BaseModel):
    client_id: str
    session_id: str | None = None

class SessionStartResponse(BaseModel):
    client_id: str
    session_id: str
    expires_at: datetime

class SessionEndRequest(BaseModel):
    client_id: str
    session_id: str

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

def build_contextual_question(history: list, question: str, max_turns: int = 6) -> str:
    """
    Convierte historial en contexto textual breve.
    history = lista de ChatMessage
    """
    # Cogemos últimos mensajes para no inflar tokens
    window = history[-max_turns:]
    if not window:
        return question

    lines = []
    for m in window:
        prefix = "Usuario" if m.role == "user" else "Asistente"
        lines.append(f"{prefix}: {m.content}")

    history_block = "\n".join(lines)
    return (
        "Contexto de conversación (sesión actual):\n"
        f"{history_block}\n\n"
        f"Pregunta actual del usuario: {question}"
    )

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

@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    """
    Chat con memoria efímera por (client_id, session_id).
    Si sesión no existe/expira, devuelve 410.
    """
    session = chat_store.get_session(request.client_id, request.session_id)
    if not session:
        raise HTTPException(
            status_code=410,
            detail="Sesión no válida o expirada. Inicia una nueva sesión."
        )

    question_with_context = build_contextual_question(
        history=session.messages,
        question=request.question,
        max_turns=6
    )

    respuesta = qa_service.process_question(
        question=question_with_context,
        client_id=request.client_id,
        company_name=request.company_name
    )

    if "error" in respuesta:
        raise HTTPException(status_code=500, detail=respuesta["error"])

    texto_respuesta = respuesta.get("result", "Lo siento, no pude generar una respuesta.")

    # persistimos mensajes en memoria efímera
    chat_store.append_message(request.client_id, request.session_id, "user", request.question)
    chat_store.append_message(request.client_id, request.session_id, "assistant", texto_respuesta)

    # recarga para leer expires_at actualizado
    updated = chat_store.get_session(request.client_id, request.session_id)

    return {
        "session_id": request.session_id,
        "question": request.question,
        "answer": texto_respuesta,
        "expires_at": updated.expires_at if updated else None
    }

@app.post("/chat/session/start", response_model=SessionStartResponse)
def start_chat_session(req: SessionStartRequest):
    s = chat_store.start_session(client_id=req.client_id, session_id=req.session_id)
    return SessionStartResponse(
        client_id=s.client_id,
        session_id=s.session_id,
        expires_at=s.expires_at
    )


@app.post("/chat/session/end")
def end_chat_session(req: SessionEndRequest):
    deleted = chat_store.end_session(client_id=req.client_id, session_id=req.session_id)
    return {"ok": True, "deleted": deleted}