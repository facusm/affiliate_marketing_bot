from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database.database import init_db
from app.api import scraper, llm, media, render, pipeline, webhook, products

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializar la base de datos al arrancar la aplicación
    init_db()
    yield
    # Lógica de cierre (si la hubiera) al detener la aplicación

app = FastAPI(
    title="Affiliate Marketing Automation API",
    description="Orchestrator Module for Affiliate Marketing Video Automation — Multi-Language Pipeline",
    version="3.0.0",
    lifespan=lifespan
)

# Incluir los routers de cada módulo
app.include_router(scraper.router)
app.include_router(llm.router)
app.include_router(media.router)
app.include_router(render.router)
app.include_router(pipeline.router)
app.include_router(webhook.router)
app.include_router(products.router)

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Orchestrator is running. Ready to automate!"
    }
