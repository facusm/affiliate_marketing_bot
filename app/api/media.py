from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from app.database.database import get_db
from app.database.models import Video, ContentStatus
from app.media.media_manager import process_media_for_video

router = APIRouter(prefix="/media", tags=["Media"])

@router.post("/process/{video_id}")
async def process_media(video_id: int, db: Session = Depends(get_db)):
    # 1. Buscar el registro en la tabla Videos
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado en la base de datos.")
        
    if not video.hook or not video.script or not video.call_to_action:
        raise HTTPException(status_code=400, detail="El video no tiene guion generado.")
        
    try:
        # Texto completo para el TTS
        full_text = f"{video.hook} {video.script} {video.call_to_action}"
        
        # Keywords generadas
        keywords = json.loads(video.keywords) if video.keywords else []
        
        # 2. Ejecutar generación de audio y descargas de Pexels en paralelo
        audio_path, stock_videos_paths = await process_media_for_video(
            video_id=video.id,
            full_text=full_text,
            keywords=keywords
        )
        
        # 3. Guardar las rutas en la base de datos
        video.audio_path = audio_path
        video.stock_videos_paths = json.dumps(stock_videos_paths)
        
        # 4. Actualizar estado
        video.status = ContentStatus.MEDIA_DOWNLOADED
        
        db.commit()
        db.refresh(video)
        
        return {
            "status": "success",
            "module": "media",
            "video_id": video.id,
            "message": "Recursos multimedia procesados y listos en disco local",
            "data": {
                "audio_path": video.audio_path,
                "stock_videos_paths": stock_videos_paths
            }
        }
        
    except Exception as e:
        # Si falla, actualizamos el estado a ERROR
        video.status = ContentStatus.ERROR
        db.commit()
        raise HTTPException(status_code=500, detail=f"Error durante el procesamiento multimedia: {str(e)}")
