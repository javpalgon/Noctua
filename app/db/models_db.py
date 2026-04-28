from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base
import uuid
from datetime import datetime


class User(Base):
    __tablename__ = "User"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    chatbots = relationship("Cliente", back_populates="user", cascade="all, delete-orphan")

class Cliente(Base):
    __tablename__ = "Cliente"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))  # ID único generado automáticamente
    company_name = Column(String, nullable=False)
    url_portal = Column(String, unique=True, nullable=False)
    user_id = Column(String, ForeignKey("User.id"), nullable=False, index=True)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chatbots")