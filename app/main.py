from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database.database import init_db
from app.api import llm, pipeline, webhook, products

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

# Incluir los routers activos
app.include_router(pipeline.router)
app.include_router(products.router)
app.include_router(llm.router)
app.include_router(webhook.router)

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Orchestrator is running. Ready to automate!"
    }
