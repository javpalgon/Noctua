import os

from app.services.chat_session_store import ChatSessionStore  # store en RAM actual
from app.services.chat_session_store_redis import RedisChatSessionStore


def create_chat_store():
    backend = os.getenv("SESSION_BACKEND", "memory").lower()
    ttl = int(os.getenv("SESSION_TTL_MINUTES", "30"))
    max_messages = int(os.getenv("SESSION_MAX_MESSAGES", "20"))

    if backend == "redis":
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return RedisChatSessionStore(
            redis_url=redis_url,
            ttl_minutes=ttl,
            max_messages=max_messages,
        )

    return ChatSessionStore(ttl_minutes=ttl, max_messages=max_messages)