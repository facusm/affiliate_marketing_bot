import os
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.database.models import Video, ContentStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/publish", tags=["Publishing"])

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

async def _publish_to_instagram(video_id: int, db: Session):
    """Proceso asíncrono para subir y publicar el video en Instagram."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video or not video.final_video_path:
        logger.error(f"[Publish] Video {video_id} no encontrado o sin renderizar.")
        return

    lang = video.language.upper() if video.language else "ES"
    ig_account_id = os.getenv(f"INSTAGRAM_ACCOUNT_ID_{lang}")

    if not META_ACCESS_TOKEN or not ig_account_id:
        logger.error(f"[Publish] Faltan credenciales de Meta para el idioma {lang}.")
        video.status = ContentStatus.ERROR
        db.commit()
        return

    # Extraer nombre del archivo (ej: video_123.mp4)
    filename = os.path.basename(video.final_video_path)
    # URL pública que Meta usará para descargar el video
    video_url = f"{PUBLIC_BASE_URL.rstrip('/')}/videos/{filename}"

    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}"
    }

    async with httpx.AsyncClient() as client:
        # 1. Crear contenedor multimedia
        create_container_url = f"https://graph.facebook.com/v19.0/{ig_account_id}/media"
        caption = f"{video.hook}\n\n{video.body if hasattr(video, 'body') else ''}\n\n{video.call_to_action}\nComenta '{video.cta_keyword}' para recibir el link!\n\n#reels #viral"
        
        payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true"
        }

        try:
            logger.info(f"[Publish] Creando contenedor de Reel para video {video.id} desde {video_url}...")
            res_create = await client.post(create_container_url, data=payload, headers=headers, timeout=30.0)
            res_create.raise_for_status()
            creation_id = res_create.json().get("id")
            
            if not creation_id:
                raise ValueError("No se recibió creation_id de Meta.")
            
            logger.info(f"[Publish] Contenedor creado exitosamente: {creation_id}. Esperando procesamiento...")
            
            # Polling para saber si el contenedor está listo
            status_url = f"https://graph.facebook.com/v19.0/{creation_id}?fields=status_code"
            ready = False
            for _ in range(12): # Max 1 min
                await httpx.AsyncClient().sleep(5)
                res_status = await client.get(status_url, headers=headers)
                status_code = res_status.json().get("status_code")
                if status_code == "FINISHED":
                    ready = True
                    break
                elif status_code == "ERROR":
                    raise RuntimeError("Meta devolvió ERROR al procesar el contenedor del Reel.")
                logger.info(f"[Publish] Estado del contenedor {creation_id}: {status_code}")

            if not ready:
                raise TimeoutError("Timeout esperando que Meta procese el contenedor de video.")

            # 2. Publicar el contenedor
            publish_url = f"https://graph.facebook.com/v19.0/{ig_account_id}/media_publish"
            publish_payload = {
                "creation_id": creation_id
            }
            logger.info(f"[Publish] Publicando contenedor {creation_id}...")
            res_publish = await client.post(publish_url, data=publish_payload, headers=headers, timeout=30.0)
            res_publish.raise_for_status()
            
            ig_media_id = res_publish.json().get("id")
            if not ig_media_id:
                raise ValueError("No se recibió ig_media_id de Meta al publicar.")

            # Actualizar DB
            video.ig_media_id = ig_media_id
            video.status = ContentStatus.PUBLISHED
            db.commit()
            
            logger.info(f"[Publish] ¡Reel publicado exitosamente! ig_media_id: {ig_media_id}")

        except Exception as e:
            logger.error(f"[Publish] Error publicando video {video.id}: {str(e)}")
            video.status = ContentStatus.ERROR
            db.commit()

@router.post("/{video_id}")
async def publish_video(video_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Inicia la publicación asíncrona de un video generado hacia Instagram Reels.
    Requiere que PUBLIC_BASE_URL esté configurado correctamente.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado.")
    
    if not video.final_video_path:
        raise HTTPException(status_code=400, detail="El video aún no tiene final_video_path (no está renderizado).")

    background_tasks.add_task(_publish_to_instagram, video_id, db)
    return {"status": "success", "message": f"Publicación del video {video_id} encolada."}
