import asyncio
import httpx
import os
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
from datetime import datetime, timedelta, timezone
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Noctua - Plataforma de Grafos de Conocimiento")

# CORS para pruebas locales del widget (frontend en otro puerto)
app.add_middleware(
    CORSMiddleware,
    # Permite embeber el widget desde cualquier dominio.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

qa_service = GraphQAService()
chat_store = create_chat_store()

class ClienteCreate(BaseModel):
    company_name: str
    url_portal: HttpUrl

class ClienteOut(BaseModel):
    id: str
    company_name: str
    url_portal: str
    created_at: datetime

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str

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

VALIDATION_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

ALLOW_INSECURE_TLS_FALLBACK = os.getenv("ALLOW_INSECURE_TLS_FALLBACK", "true").lower() in {
    "1", "true", "yes", "on"
}

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "noctua-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=True)

def _validar_status_url(response: httpx.Response):
    """Normaliza validacion de status HTTP de la URL del cliente."""
    status = response.status_code
    if status < 400:
        return
    if status == 404:
        raise HTTPException(status_code=422, detail="La URL no existe (404)")
    if status in (401, 403):
        raise HTTPException(status_code=422, detail="La URL requiere autenticación o está bloqueada (401/403)")
    if status >= 500:
        raise HTTPException(status_code=422, detail="Error del servidor de la URL o caída temporal")
    raise HTTPException(status_code=422, detail=f"La URL devolvió un estado no válido ({status})")


def _es_error_certificado_tls(exc: Exception) -> bool:
    """Detecta errores típicos de certificado/cadena TLS inválida."""
    textos = []
    current: Exception | None = exc
    for _ in range(6):
        if current is None:
            break
        textos.append(f"{type(current).__name__}: {current}".lower())
        siguiente = current.__cause__ or current.__context__
        if isinstance(siguiente, BaseException):
            current = siguiente  # type: ignore[assignment]
        else:
            break

    joined = " | ".join(textos)
    patrones_tls = (
        "certificate verify failed",
        "unable to get local issuer certificate",
        "self signed certificate",
        "hostname mismatch",
        "ssl",
        "tls",
    )
    return any(p in joined for p in patrones_tls)


async def _hacer_peticion_validacion(target: str, verify_tls: bool) -> httpx.Response:
    async with httpx.AsyncClient(
        timeout=10,
        follow_redirects=True,
        headers=VALIDATION_HEADERS,
        verify=verify_tls,
    ) as client:
        try:
            response = await client.head(target)
        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError):
            # Algunos servidores cortan HEAD sin enviar respuesta completa.
            response = await client.get(target)
        else:
            # Si HEAD no está soportado, reintentamos con GET.
            if response.status_code in (405, 501):
                response = await client.get(target)
    return response

async def validar_url(url: HttpUrl):
    """Valida que la URL existe con fallback HEAD -> GET para servidores no estándar."""
    target = str(url)
    try:
        try:
            response = await _hacer_peticion_validacion(target, verify_tls=True)
        except httpx.ConnectError as e:
            # Fallback opcional para sitios con cadena TLS mal configurada.
            if ALLOW_INSECURE_TLS_FALLBACK and _es_error_certificado_tls(e):
                response = await _hacer_peticion_validacion(target, verify_tls=False)
            else:
                raise

        _validar_status_url(response)
    except HTTPException:
        raise
    except httpx.ConnectError as e:
        if _es_error_certificado_tls(e):
            raise HTTPException(
                status_code=422,
                detail="No se pudo validar TLS de la URL (certificado inválido o cadena incompleta)",
            )
        raise HTTPException(status_code=422, detail="No se pudo conectar a la URL")
    except httpx.TimeoutException:
        raise HTTPException(status_code=422, detail="La URL superó el timeout")
    except httpx.RequestError as e:
        raise HTTPException(status_code=422, detail=f"Error de red validando la URL: {type(e).__name__}")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models_db.User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    user = db.query(models_db.User).filter(models_db.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user
    
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
    # Solo reutilizamos las ultimas preguntas del usuario para no contaminar
    # la recuperacion con respuestas previas del asistente.
    user_turns = [m.content for m in history if m.role == "user"][-max_turns:]
    if not user_turns:
        return question

    lines = []
    for user_msg in user_turns:
        lines.append(f"Usuario: {user_msg}")

    history_block = "\n".join(lines)
    return (
        "Contexto breve de preguntas previas del usuario:\n"
        f"{history_block}\n\n"
        f"Pregunta actual del usuario: {question}"
    )

# ── Endpoints ────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"message": "Bienvenido a Noctua - Plataforma de Grafos de Conocimiento"}


@app.post("/auth/register", response_model=AuthResponse)
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    exists = db.query(models_db.User).filter(models_db.User.email == email).first()
    if exists:
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese email")

    user = models_db.User(
        email=email,
        hashed_password=get_password_hash(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id)
    return AuthResponse(access_token=token, email=user.email)


@app.post("/auth/login", response_model=AuthResponse)
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(models_db.User).filter(models_db.User.email == email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token = create_access_token(subject=user.id)
    return AuthResponse(access_token=token, email=user.email)


@app.get("/me/chatbots", response_model=list[ClienteOut])
def my_chatbots(
    current_user: models_db.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chatbots = (
        db.query(models_db.Cliente)
        .filter(models_db.Cliente.user_id == current_user.id)
        .order_by(models_db.Cliente.created_at.desc())
        .all()
    )
    return chatbots

@app.post("/clientes")
async def create_cliente(
    cliente: ClienteCreate,
    background_tasks: BackgroundTasks,
    current_user: models_db.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    
    await validar_url(cliente.url_portal)
    
    nuevo_cliente = models_db.Cliente(
        company_name=cliente.company_name,
        url_portal=str(cliente.url_portal),
        user_id=current_user.id,
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


@app.post("/clientes/{cliente_id}/refresh")
async def refresh_cliente(
    cliente_id: str,
    background_tasks: BackgroundTasks,
    current_user: models_db.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cliente = (
        db.query(models_db.Cliente)
        .filter(
            models_db.Cliente.id == cliente_id,
            models_db.Cliente.user_id == current_user.id,
        )
        .first()
    )
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    await validar_url(cliente.url_portal)

    background_tasks.add_task(
        generar_grafo_segundo_plano,
        cliente_id=cliente.id,
        company_name=cliente.company_name,
        url_portal=cliente.url_portal,
    )

    return {
        "ok": True,
        "client_id": cliente.id,
        "message": "Actualización de grafo iniciada en segundo plano",
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