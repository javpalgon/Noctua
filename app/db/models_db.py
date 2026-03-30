from sqlalchemy import Column, String, Boolean, DateTime
from app.db.database import Base
import uuid
from datetime import datetime

class Cliente(Base):
    __tablename__ = "Cliente"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))  # ID único generado automáticamente
    company_name = Column(String, nullable=False)
    url_portal = Column(String, unique=True, nullable=False)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)