# Conexión SQLAlchemy y configuración de base de datos
from sqlalchemy import create_engine  # Conexión a PostGreSQL. Con text para ejecutar comandos SQL directos sin necesidad de poner SQLs.
from sqlalchemy.orm import sessionmaker, declarative_base # sessionmaker para crear sesiones de base de datos, declarative_base para definir modelos ORM
from models import DatabaseConfig # Importar configuración de base de datos desde models.py

# Crear la conexión a la base de datos
engine = create_engine(DatabaseConfig.POSTGRES_URL)
# Crear el sessionmaker para manejar sesiones de base de datos
SessionLocal = sessionmaker(bind=engine)
# Crear la clase base para los modelos ORM
Base = declarative_base() 

# get_db es la función que permite dar conexión a cada petición web a la base de datos, creando una sesión y cerrándola al finalizar
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally: 
        db.close()

def create_tables():
    """Función para crear las tablas en la base de datos."""
    from db import models_db  # Importar modelos para que SQLAlchemy los reconozca
    Base.metadata.create_all(bind=engine)  # Crear tablas basadas en los modelos definidos