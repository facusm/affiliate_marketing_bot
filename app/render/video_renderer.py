import os
import asyncio
import logging
import httpx
from moviepy import VideoFileClip, AudioFileClip, TextClip, ImageClip, CompositeVideoClip, concatenate_videoclips, vfx

logger = logging.getLogger(__name__)

# Directorio final para los renders
STORAGE_OUTPUTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../storage/outputs"))
STORAGE_IMAGES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../storage/images"))
os.makedirs(STORAGE_OUTPUTS_DIR, exist_ok=True)
os.makedirs(STORAGE_IMAGES_DIR, exist_ok=True)


def _download_image(image_url: str, video_id: int) -> str | None:
    """
    Descarga la imagen del producto y la guarda localmente.
    """
    image_path = os.path.join(STORAGE_IMAGES_DIR, f"{video_id}_product.png")
    try:
        response = httpx.get(image_url, follow_redirects=True, timeout=15.0)
        response.raise_for_status()
        with open(image_path, "wb") as f:
            f.write(response.content)
        return image_path
    except Exception as e:
        logger.warning(f"No se pudo descargar la imagen del producto: {e}")
        return None


def _render_video_sync(
    video_id: int,
    audio_path: str,
    stock_paths: list[str],
    hook_text: str,
    cta_keyword: str | None = None,
    product_image_url: str | None = None
) -> str:
    """
    Función sincrónica pesada que ejecuta la composición de MoviePy.
    Incluye overlay de producto + CTA en los últimos 4 segundos.
    """
    output_path = os.path.join(STORAGE_OUTPUTS_DIR, f"{video_id}.mp4")
    
    # 1. Cargar el audio principal
    audio_clip = AudioFileClip(audio_path)
    total_duration = audio_clip.duration
    
    if not stock_paths:
        raise ValueError("No hay clips de video de stock disponibles para renderizar.")

    # 2. Calcular la duración que tendrá cada clip (se dividen equitativamente en el tiempo del audio)
    num_clips = len(stock_paths)
    duration_per_clip = total_duration / num_clips
    
    # 3. Cargar, ajustar y procesar los clips
    processed_clips = []
    for path in stock_paths:
        try:
            clip = VideoFileClip(path)
            
            # Si el clip es más corto que lo asignado, lo ponemos en bucle. Si es más largo, lo cortamos.
            if clip.duration < duration_per_clip:
                clip = clip.fx(vfx.Loop, duration=duration_per_clip)
            else:
                clip = clip.subclipped(0, duration_per_clip)
                
            processed_clips.append(clip)
        except Exception as e:
            logger.warning(f"Error procesando el clip {path}: {e}")
            
    if not processed_clips:
        raise ValueError("Ningún clip de video pudo ser cargado correctamente.")

    # 4. Concatenar la secuencia de videos
    final_video = concatenate_videoclips(processed_clips, method="compose")
    
    # 5. Sincronizar con el audio final
    final_video = final_video.with_audio(audio_clip)
    
    # Lista de overlays para componer sobre el video
    overlay_layers = [final_video]
    
    # 6. Agregar Text Overlay (Hook) durante los primeros 3 segundos
    try:
        txt_clip = TextClip(
            text=hook_text, 
            font_size=65, 
            color='white', 
            stroke_color='black', 
            stroke_width=2,
            font='Arial-Bold',
            method='caption',
            size=(final_video.w * 0.85, None)
        )
        txt_clip = txt_clip.with_position('center').with_duration(min(3.0, total_duration))
        overlay_layers.append(txt_clip)
    except Exception as e:
        logger.warning(f"Error al generar TextClip del hook: {e}. Se exportará sin texto de hook.")

    # 7. Agregar overlay de producto + CTA en los últimos 4 segundos
    if cta_keyword:
        cta_duration = min(4.0, total_duration)
        cta_start = total_duration - cta_duration
        
        # 7a. Descargar y superponer la imagen del producto
        if product_image_url:
            product_image_path = _download_image(product_image_url, video_id)
            if product_image_path:
                try:
                    img_clip = ImageClip(product_image_path)
                    # Escalar la imagen al 40% del ancho del video
                    target_width = int(final_video.w * 0.4)
                    img_clip = img_clip.resized(width=target_width)
                    img_clip = (
                        img_clip
                        .with_duration(cta_duration)
                        .with_start(cta_start)
                        .with_position(('center', final_video.h * 0.25))
                    )
                    overlay_layers.append(img_clip)
                except Exception as e:
                    logger.warning(f"Error al superponer imagen del producto: {e}")

        # 7b. Agregar texto de CTA grande y llamativo
        try:
            cta_text = f"Comentá {cta_keyword}"
            cta_clip = TextClip(
                text=cta_text,
                font_size=75,
                color='yellow',
                stroke_color='black',
                stroke_width=3,
                font='Arial-Bold',
                method='caption',
                size=(final_video.w * 0.9, None)
            )
            cta_clip = (
                cta_clip
                .with_duration(cta_duration)
                .with_start(cta_start)
                .with_position(('center', final_video.h * 0.70))
            )
            overlay_layers.append(cta_clip)
        except Exception as e:
            logger.warning(f"Error al generar TextClip del CTA: {e}")

    # 8. Componer todas las capas
    final_video = CompositeVideoClip(overlay_layers)

    # 9. Renderizar a archivo MP4
    logger.info(f"Comenzando renderizado del video {video_id}...")
    final_video.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        threads=4,
        logger=None
    )
    
    # Liberar memoria de los objetos MoviePy
    audio_clip.close()
    for c in processed_clips:
        c.close()
    final_video.close()
    
    return output_path

async def render_final_video(
    video_id: int,
    audio_path: str,
    stock_paths: list[str],
    hook_text: str,
    cta_keyword: str | None = None,
    product_image_url: str | None = None
) -> str:
    """
    Función asíncrona que mueve la carga pesada de MoviePy a un hilo en segundo plano 
    para no bloquear el event loop de FastAPI.
    """
    return await asyncio.to_thread(
        _render_video_sync, video_id, audio_path, stock_paths, hook_text, cta_keyword, product_image_url
    )
