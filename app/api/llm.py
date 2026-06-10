from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from app.database.database import get_db
from app.database.models import Product, Video, ContentStatus
from app.llm.script_generator import generate_video_script

router = APIRouter(prefix="/llm", tags=["LLM"])

@router.post("/generate-script/{product_id}")
async def generate_script(product_id: int, db: Session = Depends(get_db)):
    # 1. Buscar el producto en la tabla Products
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
        
    try:
        # 2. Disparar la generación del guion con el LLM (ahora con rating y opiniones)
        script_data = await generate_video_script(
            title=product.title or "Producto genérico",
            price=product.price or 0.0,
            features=product.features or "Excelente producto.",
            rating=product.rating,
            reviews_count=product.reviews_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando el guion con LLM: {str(e)}")

    # 3. Crear un nuevo registro en la tabla Videos asociado al product_id
    video = Video(
        product_id=product.id,
        hook=script_data.hook,
        script=script_data.body,
        call_to_action=script_data.cta,
        cta_keyword=script_data.cta_keyword,
        keywords=json.dumps(script_data.keywords),
        status=ContentStatus.SCRIPT_GENERATED
    )
    
    db.add(video)
    db.commit()
    db.refresh(video)
    
    # 4. Devolver el video_id y el JSON del guion generado
    return {
        "status": "success",
        "module": "llm",
        "video_id": video.id,
        "product_id": product.id,
        "data": {
            "hook": video.hook,
            "body": video.script,
            "cta_keyword": video.cta_keyword,
            "cta": video.call_to_action,
            "keywords": script_data.keywords
        }
    }
