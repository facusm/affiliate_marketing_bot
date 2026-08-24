"""
Pipeline API Router — Endpoint unificado para ejecutar el pipeline de video IA.

Soporta dos modos de entrada:
  1. Ingesta directa: Sube la foto del producto + datos via multipart/form-data.
     → Funciona con cualquier marketplace (MeLi, Amazon, AliExpress, etc.)
  2. Desde producto existente: Usa un product_id previamente cargado.

Genera 1 video mudo con Kling y produce N reels multi-idioma.
El link de afiliado es OPCIONAL y puede agregarse después via PATCH /products/{id}/affiliate-link.
"""

import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Form, UploadFile, File
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.database.models import Product, ContentStatus
from app.orchestrator import run_pipeline
from app.llm.script_generator import DEFAULT_LANGUAGES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])

# Directorio para guardar las imágenes subidas
STORAGE_IMAGES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../storage/images")
)
os.makedirs(STORAGE_IMAGES_DIR, exist_ok=True)


# ─── Endpoint Principal: Subida Física (multipart/form-data) ──────────────────

@router.post("/run")
async def execute_pipeline(
    title: str = Form(
        ...,
        description="Nombre del producto (ej: 'Mandolina de Cocina Profesional')",
    ),
    image: UploadFile = File(
        ...,
        description="Foto del producto (PNG, JPG, JPEG o WEBP)",
    ),
    price: float = Form(
        default=0.0,
        description="Precio del producto",
    ),
    description: str = Form(
        default="",
        description="Descripción o características del producto",
    ),
    rating: float | None = Form(
        default=None,
        description="Puntuación del producto (ej: 4.8)",
    ),
    reviews_count: int | None = Form(
        default=None,
        description="Cantidad de reseñas/opiniones (ej: 523)",
    ),
    languages: str = Query(
        default=",".join(DEFAULT_LANGUAGES),
        description=(
            "Códigos de idioma separados por coma (default: es,en,pt,de,fr,it). "
            "Ej: 'es,en,pt' para generar solo 3 idiomas."
        ),
    ),
    db: Session = Depends(get_db),
):
    """
    Genera reels virales multi-idioma a partir de una foto y datos del producto.

    - Subí la **foto del producto** como archivo (multipart/form-data).
    - Completá **título**, **precio** y **descripción** como campos de formulario.
    - El **affiliate_url** se agrega después con:
      `PATCH /products/{product_id}/affiliate-link`

    El pipeline genera 1 video IA mudo + N reels con subtítulos dinámicos
    estilo Hormozi y voces nativas por idioma.
    """
    try:
        # 1. Validar y guardar la imagen localmente
        allowed_extensions = {".png", ".jpg", ".jpeg", ".webp"}
        file_ext = os.path.splitext(image.filename or "upload.png")[1].lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Formato de imagen no soportado: '{file_ext}'. Usá PNG, JPG o WEBP.",
            )

        image_filename = f"{uuid.uuid4()}{file_ext}"
        image_path = os.path.join(STORAGE_IMAGES_DIR, image_filename)

        content = await image.read()
        with open(image_path, "wb") as f:
            f.write(content)

        logger.info(f"[Pipeline] Imagen guardada: {image_path} ({len(content)} bytes)")

        # 2. Crear el producto en la DB
        db_product = Product(
            url=f"direct-upload-{uuid.uuid4().hex[:8]}",
            title=title,
            price=price,
            features=description,
            image_url=image_path,
            rating=rating,
            reviews_count=reviews_count,
            status=ContentStatus.SCRAPED,
        )
        db.add(db_product)
        db.commit()
        db.refresh(db_product)

        logger.info(f"[Pipeline] Producto creado: ID {db_product.id} — {title}")

        # 3. Parsear los idiomas
        lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]

        # 4. Ejecutar el pipeline completo
        result = await run_pipeline(
            product_id=db_product.id,
            db=db,
            languages=lang_list,
        )
        return result

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Pipeline] Error ejecutando pipeline: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error ejecutando pipeline: {str(e)}",
        )


# ─── Endpoint Legacy: Desde producto existente ────────────────────────────────

@router.post("/run/{product_id}")
async def execute_pipeline_from_db(
    product_id: int,
    languages: str = Query(
        default=",".join(DEFAULT_LANGUAGES),
        description=(
            "Códigos de idioma separados por coma (default: es,en,pt,de,fr,it). "
            "Ej: 'es,en,pt' para generar solo 3 idiomas."
        ),
    ),
    db: Session = Depends(get_db),
):
    """
    Ejecuta el pipeline para un producto previamente cargado (por ID).
    """
    try:
        lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]

        result = await run_pipeline(
            product_id=product_id,
            db=db,
            languages=lang_list,
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Pipeline] Error ejecutando pipeline: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error ejecutando pipeline: {str(e)}",
        )
