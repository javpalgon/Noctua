from pydantic import BaseModel, HttpUrl
from typing import Optional, List
import os
from dotenv import load_dotenv

# ═══════════════════════════════════════════════════════════
# CONFIGURACIÓN DE BASES DE DATOS
# ═══════════════════════════════════════════════════════════
load_dotenv()

class DatabaseConfig:
    """Configuración centralizada de conexiones a BD."""
    
    # PostgreSQL (clientes, logs)
    POSTGRES_URL = os.getenv(
        "DATABASE_URL", 
        "postgresql://user:password@localhost:5432/noctua"
    )
    
    # Neo4j (grafos de conocimiento)
    NEO4J_URI = os.getenv("NEO4J_URI", "")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


# ═══════════════════════════════════════════════════════════
# MODELOS PYDANTIC (para validación y API)
# ═══════════════════════════════════════════════════════════

class ClientConfig(BaseModel):
    """Configuración de cliente para scraping."""
    company_name: str
    url_portal: HttpUrl
    client_id: Optional[str] = None
    api_key: Optional[str] = None
    single_url: bool = False