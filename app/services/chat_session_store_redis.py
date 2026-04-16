from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from redis import Redis

from app.services.chat_session_store import ChatSession, ChatMessage

class RedisChatSessionStore:
    """ Guarda las sesiones en Redis"""

    def __init__(self, redis_url: str, ttl_minutes: int=30, max_messages: int = 20):
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.ttl_seconds = int(ttl_minutes*60)
        self.max_messages = max_messages

    @staticmethod
    def _key(client_id: str, session_id: str) -> str:
        return f"chat_session:{client_id}:{session_id}"
    
    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
    
    def _serialize(self, session: ChatSession) -> str:
        payload= {
            "client_id": session.client_id,
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
            "last_activity_at": session.last_activity_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "ts": msg.ts.isoformat()
                } 
                for msg in session.messages
            ]
        }
        return json.dumps(payload, ensure_ascii=False)
    
    def _deserialize(self, raw: str) -> ChatSession:
        data = json.loads(raw)
        return ChatSession(
            client_id=data["client_id"],
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_activity_at=datetime.fromisoformat(data["last_activity_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            messages=[
                ChatMessage(
                    role=msg["role"],
                    content=msg["content"],
                    ts=datetime.fromisoformat(msg["ts"])
                )
                for msg in data.get("messages", [])
            ]
        )
    
    def _touch(self, session: ChatSession) -> None:
        now = self._now()
        session.last_activity_at = now
        session.expires_at = now + timedelta(seconds=self.ttl_seconds)
    
    def start_session(self, client_id: str, session_id: Optional[str] = None) -> ChatSession:
        from uuid import uuid4

        sid = session_id or str(uuid4())
        key = self._key(client_id, sid)

        existing_raw = self.redis.get(key)
        if existing_raw:
            session = self._deserialize(existing_raw)
            self._touch(session)
            self.redis.setex(key, self.ttl_seconds, self._serialize(session))
            return session
        
        now = self._now()
        session = ChatSession(
            client_id=client_id,
            session_id=sid,
            created_at=now,
            last_activity_at=now,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
            messages=[]
        )
        self.redis.setex(key, self.ttl_seconds, self._serialize(session))
        return session
    
    def get_session(self, client_id: str, session_id: str) -> Optional[ChatSession]:
        key = self._key(client_id, session_id)
        raw = self.redis.get(key)
        if not raw:
            return None
        
        session = self._deserialize(raw)
        self._touch(session)
        self.redis.setex(key, self.ttl_seconds, self._serialize(session))
        return session
    
    def append_message(self, client_id: str, session_id: str, role: str, content: str) -> bool:
        key = self._key(client_id, session_id)
        raw = self.redis.get(key)
        if not raw: 
            return False
        
        session = self._deserialize(raw)
        session.messages.append(ChatMessage(role=role, content=content))
        if len(session.messages) > self.max_messages:
            session.messages = session.messages[-self.max_messages:]
        self._touch(session)
        self.redis.setex(key, self.ttl_seconds, self._serialize(session))
        return True
    
    def end_session(self, client_id: str, session_id: str) -> bool:
        key = self._key(client_id, session_id)
        deleted = self.redis.delete(key)
        return deleted > 0
    
    def cleanup_expired(self) -> int:
        return 0  # Redis se encarga de eliminar las claves expiradas automáticamente