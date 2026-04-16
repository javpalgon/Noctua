from __future__ import annotations 

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4

@dataclass
class ChatMessage:
    role: str # diferencia entre user y assistant
    content: str
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class ChatSession:
    client_id: str
    session_id: str
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    messages: List[ChatMessage] = field(default_factory=list)


class ChatSessionStore: 
    """
    Memoria efímera en proceso:
    - clave por (client_id, session_id) para identificar cada sesión de chat de CADA cliente
    - limite de mensajes por sesión
    """
    def __init__(self, ttl_minutes: int = 30, max_messages: int = 20):
        self._sessions: Dict[str, ChatSession] = {}
        self.ttl_minutes = ttl_minutes
        self.max_messages = max_messages
        self._lock = Lock()

    # Genera la clave única para cada sesión de chat
    @staticmethod
    def _key(client_id: str, session_id: str) -> str:
        return f"{client_id}:{session_id}" 

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
    
    def _is_expired(self, session: ChatSession) -> bool:
        return self._now() >= session.expires_at
    
    def _touch(self, session: ChatSession) -> None:
        now = self._now()
        session.last_activity_at = now
        session.expires_at = now + timedelta(minutes=self.ttl_minutes)

    def cleanup_expired(self) -> int: 
        """Elimina sesiones expiradas. Retorna el número de sesiones eliminadas"""
        with self._lock:
            return self._cleanup_expired_unlocked()

    def _cleanup_expired_unlocked(self) -> int:
        """Elimina sesiones expiradas asumiendo que el lock ya está adquirido."""
        keys_to_delete = [key for key, session in self._sessions.items() if self._is_expired(session)]
        for key in keys_to_delete:
            del self._sessions[key]
        return len(keys_to_delete)

    def start_session(self, client_id: str, session_id: Optional[str] = None) -> ChatSession:
        """ Empezar una nueva sesión de chat para un cliente. Retorna la sesión creada."""
        with self._lock:
            self._cleanup_expired_unlocked()
            
            sid = session_id or str(uuid4())
            key = self._key(client_id, sid)
            now = self._now()

            existing = self._sessions.get(key)
            if existing and not self._is_expired(existing):
                self._touch(existing)
                return existing
            
            session = ChatSession(
                client_id=client_id,
                session_id=sid,
                created_at=now,
                last_activity_at=now,
                expires_at=now + timedelta(minutes=self.ttl_minutes),
            )
            self._sessions[key] = session
            return session
        
    def get_session(self, client_id: str, session_id: str) -> Optional[ChatSession]:
        """ Obtiene una sesión de chat existente. Retorna None si no existe o ha expirado."""
        with self._lock:
            self._cleanup_expired_unlocked()
            key = self._key(client_id, session_id)
            session = self._sessions.get(key)
            if not session:
                return None
            if self._is_expired(session):
                del self._sessions[key]
                return None
            self._touch(session)
            return session
    
    def append_message(self, client_id: str, session_id: str, role: str, content: str) -> bool:
        """ Agrega un mensaje a la sesión de chat. Retorna True si se agregó, False si la sesión no existe o ha expirado."""
        with self._lock:
            key = self._key(client_id, session_id)
            session = self._sessions.get(key)
            if not session or self._is_expired(session):
                self._sessions.pop(key, None)  # Eliminar si existe pero está expirado
                return False
            
            session.messages.append(ChatMessage(role=role, content=content))
            if len(session.messages) >= self.max_messages:
                session.messages  = session.messages[-self.max_messages:]  # Mantener solo los últimos N mensajes
            self._touch(session)
            return True
        
    def end_session(self, client_id: str, session_id: str) -> bool:
        """ Termina una sesión de chat eliminándola. Retorna True si se eliminó, False si no existía."""
        with self._lock:
            key = self._key(client_id, session_id)
            return self._sessions.pop(key, None) is not None