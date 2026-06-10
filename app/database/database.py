from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.models import Base
import os
from dotenv import load_dotenv

# Forzamos a que el .env sobreescriba cualquier variable de entorno cacheadada en tu sistema o IDE
load_dotenv(override=True)

# Se espera que el .env contenga DATABASE_URL con formato: postgresql://usuario:contraseña@localhost/basededatos
DATABASE_URL = os.getenv("DATABASE_URL")

# Usamos psycopg (v3) como driver en lugar de psycopg2, que tiene un bug de
# UnicodeDecodeError en Windows con locale cp1252.
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    # Crea las tablas en la base de datos basándose en los modelos de models.py
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
