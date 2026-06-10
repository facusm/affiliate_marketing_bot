from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from app.database.database import get_db
from app.database.models import Video, Product, ContentStatus
from app.render.video_renderer import render_final_video

router = APIRouter(prefix="/render", tags=["Render"])

@router.post("/assemble/{video_id}")
async def assemble_video(video_id: int, db: Session = Depends(get_db)):
    # 1. Buscar video y su producto asociado
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado en la base de datos.")
        
    # Verificar que el estado permita renderizar
    if not video.audio_path or not video.stock_videos_paths:
        raise HTTPException(status_code=400, detail="Los recursos multimedia no están listos. Ejecuta el módulo Media primero.")
    
    # Obtener el producto asociado para la imagen
    product = db.query(Product).filter(Product.id == video.product_id).first()
        
    try:
        stock_paths = json.loads(video.stock_videos_paths)
        hook_text = video.hook or "¡No te pierdas este producto!"
        
        # 2. Ejecutar Renderizado Asíncrono en Background Thread
        final_video_path = await render_final_video(
            video_id=video.id,
            audio_path=video.audio_path,
            stock_paths=stock_paths,
            hook_text=hook_text,
            cta_keyword=video.cta_keyword,
            product_image_url=product.image_url if product else None
        )
        
        # 3. Guardar ruta final y actualizar estado
        video.final_video_path = final_video_path
        video.status = ContentStatus.RENDERED
        
        db.commit()
        db.refresh(video)
        
        return {
            "status": "success",
            "module": "render",
            "video_id": video.id,
            "message": "¡Video renderizado exitosamente y listo para publicar!",
            "data": {
                "final_video_path": video.final_video_path
            }
        }
        
    except Exception as e:
        video.status = ContentStatus.ERROR
        db.commit()
        raise HTTPException(status_code=500, detail=f"Error fatal durante el renderizado: {str(e)}")
