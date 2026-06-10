"""
Pipeline API Router — Endpoint unificado para ejecutar pipelines.

Soporta dos modos de entrada:
  1. Ingesta directa: Le pasás los datos del producto (foto, título, precio, etc.)
     → Funciona con cualquier marketplace (MeLi, Amazon, AliExpress, etc.)
  2. Desde producto existente: Usa un product_id previamente scrapeado.

Pipeline B (engine=ai) genera 1 video mudo con Kling y produce N reels multi-idioma.
El link de afiliado es OPCIONAL y puede agregarse después via PATCH /products/{id}/affiliate-link.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.database.models import Product, ContentStatus
from app.orchestrator import run_pipeline
from app.llm.script_generator import DEFAULT_LANGUAGES

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


# ─── Modelo de Entrada Directa ────────────────────────────────────────────────

class ProductInput(BaseModel):
    """
    Datos del producto ingresados manualmente.
    Funciona con cualquier producto de cualquier marketplace.
    """
    title: str = Field(
        description="Nombre del producto (ej: 'Mandolina de Cocina Profesional')"
    )
    image_url: str = Field(
        description="URL de la foto del producto (copiar del marketplace)"
    )
    description: str = Field(
        default="",
        description="Descripción o características del producto"
    )
    price: float = Field(
        default=0.0,
        description="Precio del producto"
    )
    rating: float | None = Field(
        default=None,
        description="Puntuación del producto (ej: 4.8)"
    )
    reviews_count: int | None = Field(
        default=None,
        description="Cantidad de reseñas/opiniones (ej: 523)"
    )
    source_url: str | None = Field(
        default=None,
        description="URL original del producto en el marketplace (opcional, para referencia)"
    )
    affiliate_url: str | None = Field(
        default=None,
        description="Link de afiliado (opcional, se puede agregar después via PATCH /products/{id}/affiliate-link)"
    )


# ─── Endpoint Principal: Ingesta Directa ──────────────────────────────────────

@router.post("/run")
async def execute_pipeline_direct(
    product: ProductInput,
    engine: str = Query(
        default="ai",
        description="Motor de video: 'pexels' (Pipeline A - stock) o 'ai' (Pipeline B - IA generativa multi-idioma)",
        pattern="^(pexels|ai)$",
    ),
    languages: str = Query(
        default=",".join(DEFAULT_LANGUAGES),
        description=(
            "Códigos de idioma separados por coma para Pipeline B (default: es,en,pt,de,fr,it). "
            "Ej: 'es,en,pt' para generar solo 3 idiomas. Ignorado si engine=pexels."
        ),
    ),
    language: str = Query(
        default="Spanish (LATAM)",
        description="Idioma del guion para Pipeline A (engine=pexels). Ignorado si engine=ai.",
    ),
    db: Session = Depends(get_db),
):
    """
    Genera video(s) viral(es) a partir de los datos de un producto.

    Le pasás directamente: foto, título, precio, rating y reseñas.
    Funciona con cualquier producto de cualquier marketplace (MeLi, Amazon, AliExpress, etc.).

    - **engine=ai** (default): Pipeline B — 1 video IA mudo + N reels multi-idioma
      con subtítulos dinámicos estilo Hormozi y voces nativas por idioma.
    - **engine=pexels**: Pipeline A — Videos de stock Pexels + renderer básico (single-language).

    El **affiliate_url** es opcional. Podés agregarlo después con:
    `PATCH /products/{product_id}/affiliate-link`

    **Ejemplo de body:**
    ```json
    {
        "title": "Mandolina de Cocina Profesional 5 en 1",
        "image_url": "https://http2.mlstatic.com/D_NQ_NP_...",
        "description": "Corta verduras en segundos. Acero inoxidable, 5 cuchillas intercambiables.",
        "price": 15999,
        "rating": 4.8,
        "reviews_count": 523,
        "source_url": "https://articulo.mercadolibre.com.ar/...",
        "affiliate_url": null
    }
    ```
    """
    try:
        # 1. Crear el producto en la DB a partir de los datos directos
        db_product = Product(
            url=product.source_url or f"direct-input-{product.title[:50]}",
            title=product.title,
            price=product.price,
            features=product.description,
            image_url=product.image_url,
            rating=product.rating,
            reviews_count=product.reviews_count,
            affiliate_url=product.affiliate_url,
            status=ContentStatus.SCRAPED,
        )
        db.add(db_product)
        db.commit()
        db.refresh(db_product)

        # 2. Parsear los idiomas para Pipeline B
        lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]

        # 3. Ejecutar el pipeline completo
        result = await run_pipeline(
            product_id=db_product.id,
            engine=engine,
            db=db,
            language=language,
            languages=lang_list,
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error ejecutando pipeline '{engine}': {str(e)}",
        )


# ─── Endpoint Legacy: Desde producto scrapeado ────────────────────────────────

@router.post("/run/{product_id}")
async def execute_pipeline_from_db(
    product_id: int,
    engine: str = Query(
        default="ai",
        description="Motor de video: 'pexels' (Pipeline A - stock) o 'ai' (Pipeline B - IA generativa multi-idioma)",
        pattern="^(pexels|ai)$",
    ),
    languages: str = Query(
        default=",".join(DEFAULT_LANGUAGES),
        description=(
            "Códigos de idioma separados por coma para Pipeline B (default: es,en,pt,de,fr,it). "
            "Ignorado si engine=pexels."
        ),
    ),
    language: str = Query(
        default="Spanish (LATAM)",
        description="Idioma del guion para Pipeline A (engine=pexels). Ignorado si engine=ai.",
    ),
    db: Session = Depends(get_db),
):
    """
    Ejecuta el pipeline para un producto previamente scrapeado (por ID).

    Mantiene retrocompatibilidad con el flujo original:
    /scraper/run → /pipeline/run/{product_id}
    """
    try:
        lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]

        result = await run_pipeline(
            product_id=product_id,
            engine=engine,
            db=db,
            language=language,
            languages=lang_list,
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error ejecutando pipeline '{engine}': {str(e)}",
        )
