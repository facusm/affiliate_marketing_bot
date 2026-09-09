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
import io
from PIL import Image
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
            "Códigos de idioma separados por coma (default: es,es_latam,es_mx,en,pt,de,fr,it). "
            "Ej: 'es,es_latam,es_mx' para generar solo las variantes de español."
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
        # 1. Crear el producto en la DB con un path temporal
        db_product = Product(
            url=f"direct-upload-{uuid.uuid4().hex[:8]}",
            title=title,
            price=price,
            features=description,
            image_url="", # Se actualiza enseguida
            rating=rating,
            reviews_count=reviews_count,
            status=ContentStatus.SCRAPED,
        )
        db.add(db_product)
        db.commit()
        db.refresh(db_product)

        logger.info(f"[Pipeline] Producto creado en BD: ID {db_product.id} — {title}")

        # 2. Guardar la imagen localmente en la carpeta del producto
        allowed_extensions = {".png", ".jpg", ".jpeg", ".webp"}
        file_ext = os.path.splitext(image.filename or "upload.png")[1].lower()
        if file_ext not in allowed_extensions:
            # Rollback: borrar el producto huérfano
            db.delete(db_product)
            db.commit()
            raise HTTPException(
                status_code=400,
                detail=f"Formato de imagen no soportado: '{file_ext}'. Usá PNG, JPG o WEBP.",
            )

        product_images_dir = os.path.join(STORAGE_IMAGES_DIR, str(db_product.id))
        os.makedirs(product_images_dir, exist_ok=True)

        image_filename = f"{uuid.uuid4()}{file_ext}"
        image_path = os.path.join(product_images_dir, image_filename)

        try:
            content = await image.read()
            
            # Auto-crop inteligente a 9:16 y redimensionar a 1080x1920
            img = Image.open(io.BytesIO(content))
            
            # Convertir a RGB si tiene canal alfa
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
                
            w, h = img.size
            target_ratio = 9 / 16
            current_ratio = w / h
            
            if current_ratio > target_ratio:
                # Imagen demasiado ancha, cortar los lados
                new_w = int(h * target_ratio)
                offset = (w - new_w) // 2
                img = img.crop((offset, 0, offset + new_w, h))
            elif current_ratio < target_ratio:
                # Imagen demasiado alta, cortar arriba y abajo
                new_h = int(w / target_ratio)
                offset = (h - new_h) // 2
                img = img.crop((0, offset, w, offset + new_h))
                
            # Redimensionar al estándar de Reels
            img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
            
            # Guardar la imagen modificada
            img.save(image_path, format="JPEG", quality=95)
            
        except Exception as e:
            # Rollback: borrar el producto huérfano si falla el guardado físico
            db.delete(db_product)
            db.commit()
            logger.error(f"[Pipeline] Error guardando imagen física: {e}")
            raise HTTPException(status_code=500, detail="Error al guardar la imagen física.")

        # 2.5 Actualizar el producto con la ruta final de la imagen
        db_product.image_url = image_path
        db.commit()
        db.refresh(db_product)

        logger.info(f"[Pipeline] Imagen guardada en: {image_path} ({len(content)} bytes)")

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
            "Códigos de idioma separados por coma (default: es,es_latam,es_mx,en,pt,de,fr,it). "
            "Ej: 'es,es_latam,es_mx' para generar solo las variantes de español."
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
