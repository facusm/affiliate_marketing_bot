from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database.database import init_db
from app.api import llm, pipeline, webhook, products, publish

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializar la base de datos al arrancar la aplicación
    init_db()
    yield
    # Lógica de cierre (si la hubiera) al detener la aplicación

app = FastAPI(
    title="Affiliate Marketing Automation API",
    description="AI Video Pipeline — Multi-Language Reel Generator",
    version="4.0.0",
    lifespan=lifespan
)

import os
from fastapi.staticfiles import StaticFiles

# Incluir los routers activos
app.include_router(pipeline.router)
app.include_router(products.router)
app.include_router(llm.router)
app.include_router(webhook.router)
app.include_router(publish.router)

# Exponer la carpeta de videos para acceso público (necesario para publicar en Meta)
storage_outputs = os.path.abspath(os.path.join(os.path.dirname(__file__), "../storage/outputs"))
os.makedirs(storage_outputs, exist_ok=True)
app.mount("/videos", StaticFiles(directory=storage_outputs), name="videos")


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Orchestrator is running. Ready to automate!"
    }
