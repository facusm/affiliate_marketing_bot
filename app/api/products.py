"""
Products API Router — CRUD de productos y gestión de affiliate links.

Permite:
  - Listar todos los productos con indicador de si tienen link de afiliado
  - Ver detalle de un producto con todos sus videos por idioma
  - Agregar/actualizar el link de afiliado de un producto (PATCH)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.database.models import Product, Video

router = APIRouter(prefix="/products", tags=["Products"])


# ─── Modelos de Request ───────────────────────────────────────────────────────

class AffiliateLinkUpdate(BaseModel):
    """Body para actualizar los links de afiliado por idioma."""
    links: dict[str, str] = Field(
        description="Diccionario de códigos de idioma a URLs (ej: {'es': 'amazon.es/...', 'en': 'amazon.com/...'})"
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/")
async def list_products(db: Session = Depends(get_db)):
    """
    Lista todos los productos con indicador de si tienen link de afiliado
    (si al menos un video tiene link) y la cantidad de videos generados.
    """
    products = db.query(Product).order_by(Product.created_at.desc()).all()

    response_products = []
    for p in products:
        videos = p.videos
        has_affiliate_link = any(v.affiliate_url for v in videos)
        
        video_data = [
            {
                "language": v.language,
                "affiliate_url": v.affiliate_url
            }
            for v in videos
        ]
        
        response_products.append({
            "id": p.id,
            "title": p.title,
            "price": p.price,
            "features": p.features,
            "image_url": p.image_url,
            "source_url": p.url,
            "has_affiliate_link": has_affiliate_link,
            "videos_count": len(videos),
            "videos": video_data,
            "status": p.status.value if p.status else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return {
        "status": "success",
        "count": len(products),
        "products": response_products,
    }


@router.get("/{product_id}")
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """
    Detalle de un producto con todos sus videos organizados por idioma.
    Muestra el estado del link de afiliado por video.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    videos = db.query(Video).filter(Video.product_id == product_id).all()
    has_affiliate_link = any(v.affiliate_url for v in videos)

    return {
        "status": "success",
        "product": {
            "id": product.id,
            "title": product.title,
            "price": product.price,
            "image_url": product.image_url,
            "features": product.features,
            "rating": product.rating,
            "reviews_count": product.reviews_count,
            "source_url": product.url,
            "has_affiliate_link": has_affiliate_link,
            "status": product.status.value if product.status else None,
            "created_at": product.created_at.isoformat() if product.created_at else None,
            "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        },
        "videos": [
            {
                "id": v.id,
                "language": v.language,
                "engine": v.engine,
                "hook": v.hook,
                "cta_keyword": v.cta_keyword,
                "final_video_path": v.final_video_path,
                "audio_path": v.audio_path,
                "affiliate_url": v.affiliate_url,
                "status": v.status.value if v.status else None,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in videos
        ],
        "videos_count": len(videos),
    }


@router.patch("/{product_id}/affiliate-link")
async def update_affiliate_link(
    product_id: int,
    body: AffiliateLinkUpdate,
    db: Session = Depends(get_db),
):
    """
    Agrega o actualiza los links de afiliado para los videos de un producto.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    updated_count = 0
    for video in product.videos:
        if video.language in body.links:
            video.affiliate_url = body.links[video.language]
            updated_count += 1
            
    db.commit()

    return {
        "status": "success",
        "message": f"Links de afiliado actualizados ({updated_count} videos).",
        "product_id": product.id,
        "webhook_active": updated_count > 0,
    }


@router.delete("/{product_id}/affiliate-link")
async def remove_affiliate_link(
    product_id: int,
    db: Session = Depends(get_db),
):
    """
    Elimina los links de afiliado de todos los videos de un producto.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    for video in product.videos:
        video.affiliate_url = None
        
    db.commit()

    return {
        "status": "success",
        "message": f"Links de afiliado eliminados para '{product.title}'.",
        "product_id": product.id,
        "webhook_active": False,
    }
