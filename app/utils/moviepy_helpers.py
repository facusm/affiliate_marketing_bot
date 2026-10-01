"""
Módulo utilitario de MoviePy/FFmpeg.

Helpers reutilizables para post-producción de video,
compartidos entre Pipeline A (Pexels) y Pipeline B (AI Video).
"""

import os
import re
import logging
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    TextClip,
    ColorClip,
    CompositeVideoClip,
    concatenate_videoclips,
    vfx,
)

logger = logging.getLogger(__name__)

# Fuentes con fallback (Montserrat Black > Impact > Arial-Bold)
FONT_PRIORITY = [
    "Montserrat-Black", 
    "Montserrat-Bold", 
    "Impact", 
    "Arial-Bold", 
    "Arial",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
]

def _resolve_font(preferred: str | None = None) -> str:
    """
    Intenta resolver la fuente preferida. Si no la encuentra,
    recorre FONT_PRIORITY y retorna la primera disponible.
    """
    if preferred:
        return preferred

    # Intentar encontrar una fuente del sistema
    for font_name in FONT_PRIORITY:
        try:
            # Intentar crear un TextClip de prueba para validar la fuente
            test = TextClip(text="X", font=font_name, font_size=10)
            test.close()
            return font_name
        except Exception:
            continue

    # Fallback absoluto a una fuente garantizada en el contenedor
    return "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def sanitize_text_for_moviepy(text: str) -> str:
    """
    Elimina emojis y símbolos no soportados. 
    Conserva letras (incluidas tildes, diéresis, ñ), números y puntuación básica.
    """
    # \w incluye todos los caracteres de palabras Unicode (á, ñ, ç, ä, etc.)
    return re.sub(r'[^\w\s.,!?"\'¡¿\-]', '', text)


def apply_dark_overlay(
    clip: VideoFileClip | CompositeVideoClip,
    opacity: float = 0.15,
) -> ColorClip:
    """
    Crea una capa oscura semi-transparente sobre el video.
    Útil para que el texto resalte sobre cualquier fondo.

    Args:
        clip: Video base sobre el cual aplicar el overlay.
        opacity: Opacidad del overlay negro (0.0 = transparente, 1.0 = negro total).

    Returns:
        ColorClip negro con la opacidad y duración configurada.
    """
    overlay = ColorClip(
        size=(clip.w, clip.h),
        color=(0, 0, 0),
    )
    overlay = overlay.with_duration(clip.duration).with_opacity(opacity)
    return overlay


def create_hook_text(
    text: str,
    video_width: int,
    video_height: int,
    duration: float,
    font_size: int = 58,
    color: str = "yellow",
    stroke_color: str = "black",
    stroke_width: int = 3,
    font: str | None = None,
) -> TextClip:
    """
    Crea el TextClip del hook/CTA fijo posicionado en el tercio superior.
    Estilo: fuente gruesa, color llamativo, stroke negro para legibilidad.

    Args:
        text: Texto del hook (ej: "Comentá OFERTA y te mando el link").
        video_width: Ancho del video en pixels.
        video_height: Alto del video en pixels.
        duration: Duración total que estará visible el texto.
        font_size: Tamaño de la fuente.
        color: Color del texto.
        stroke_color: Color del borde/stroke.
        stroke_width: Grosor del borde.
        font: Fuente a usar (None = auto-detect con fallback).

    Returns:
        TextClip posicionado en el tercio superior.
    """
    resolved_font = _resolve_font(font)
    text = sanitize_text_for_moviepy(text) + "\n "

    txt_clip = TextClip(
        text=text,
        font_size=font_size,
        color=color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        font=resolved_font,
        method="caption",
        size=(int(video_width * 0.85), None),
        text_align="center",
    )

    # Posicionar en el ~15% superior del video (tercio superior)
    y_position = int(video_height * 0.12)
    txt_clip = (
        txt_clip
        .with_position(("center", y_position))
        .with_duration(duration)
    )

    return txt_clip


def create_subtitle_clips(
    word_timestamps: list[dict],
    video_width: int,
    video_height: int,
    font_size: int = 55,
    color: str = "white",
    highlight_color: str = "#FFD700",
    stroke_color: str = "black",
    stroke_width: int = 3,
    font: str | None = None,
    words_per_group: int = 3,
) -> list[TextClip]:
    """
    Genera subtítulos dinámicos palabra por palabra (estilo Alex Hormozi).
    Cada grupo de palabras aparece sincronizado con el audio.

    Args:
        word_timestamps: Lista de dicts con {"word": str, "start": float, "end": float}.
        video_width: Ancho del video.
        video_height: Alto del video.
        font_size: Tamaño de la fuente de los subtítulos.
        color: Color del texto principal.
        highlight_color: Color de resaltado para la palabra activa.
        stroke_color: Color del borde.
        stroke_width: Grosor del borde.
        font: Fuente (None = auto-detect).
        words_per_group: Cantidad de palabras por grupo visible (1 = palabra por palabra, 3 = frases cortas).

    Returns:
        Lista de TextClips sincronizados para usar como overlays.
    """
    if not word_timestamps:
        return []

    resolved_font = _resolve_font(font)
    subtitle_clips = []

    # Agrupar palabras en chunks
    groups = []
    for i in range(0, len(word_timestamps), words_per_group):
        group = word_timestamps[i : i + words_per_group]
        groups.append(group)

    # Posición Y: centro de la pantalla (~50%)
    y_position = int(video_height * 0.50)

    for group in groups:
        group_text = " ".join(w["word"] for w in group)
        group_text = sanitize_text_for_moviepy(group_text) + "\n "
        group_start = group[0]["start"]
        group_end = group[-1]["end"]
        group_duration = max(group_end - group_start, 0.1)

        try:
            sub_clip = TextClip(
                text=group_text,
                font_size=font_size,
                color=color,
                stroke_color=stroke_color,
                stroke_width=stroke_width,
                font=resolved_font,
                method="caption",
                size=(int(video_width * 0.80), None),
                text_align="center",
            )
            sub_clip = (
                sub_clip
                .with_position(("center", y_position))
                .with_start(group_start)
                .with_duration(group_duration)
            )
            subtitle_clips.append(sub_clip)
        except Exception as e:
            logger.warning(f"Error creando subtítulo para '{group_text}': {e}")
            continue

    return subtitle_clips


def apply_ken_burns(
    clip: VideoFileClip,
    start_scale: float = 1.0,
    end_scale: float = 1.15,
) -> VideoFileClip:
    """
    Aplica un efecto Ken Burns (zoom digital suave) a un clip de video.

    Escala progresivamente el video de start_scale a end_scale a lo largo
    de su duración, recortando (crop) al tamaño original para que las
    dimensiones de salida no cambien.

    Esto aporta dinamismo visual al clip I2V estático sin que la IA
    deforme los píxeles originales del producto.

    Args:
        clip: VideoFileClip al cual aplicar el efecto.
        start_scale: Factor de escala inicial (default 1.0 = tamaño original).
        end_scale: Factor de escala final (default 1.15 = 15% de zoom).

    Returns:
        VideoFileClip con efecto Ken Burns aplicado.
    """
    original_w = clip.w
    original_h = clip.h

    def _ken_burns_frame(get_frame, t):
        """Transforma cada frame aplicando zoom progresivo + crop central."""
        import numpy as np
        from PIL import Image

        frame = get_frame(t)

        # Calcular el factor de escala lineal para este instante
        progress = t / clip.duration if clip.duration > 0 else 0
        current_scale = start_scale + (end_scale - start_scale) * progress

        if current_scale <= 1.0:
            return frame

        # Escalar el frame
        new_w = int(original_w * current_scale)
        new_h = int(original_h * current_scale)

        img = Image.fromarray(frame)
        img_scaled = img.resize((new_w, new_h), Image.LANCZOS)

        # Crop central para volver al tamaño original
        left = (new_w - original_w) // 2
        top = (new_h - original_h) // 2
        img_cropped = img_scaled.crop((left, top, left + original_w, top + original_h))

        return np.array(img_cropped)

    result = clip.transform(_ken_burns_frame)
    logger.info(
        f"[Ken Burns] Efecto aplicado: zoom {start_scale}x → {end_scale}x "
        f"sobre clip de {clip.duration:.1f}s"
    )
    return result


def load_and_prepare_clips(
    video_paths: list[str],
    target_duration: float,
    target_width: int = 1080,
    target_height: int = 1920,
) -> list[VideoFileClip]:
    """
    Carga clips de video, los ajusta al formato 9:16 y distribuye
    equitativamente en la duración objetivo.

    Args:
        video_paths: Lista de rutas a los archivos de video.
        target_duration: Duración total deseada en segundos.
        target_width: Ancho objetivo (default 1080 para 9:16).
        target_height: Alto objetivo (default 1920 para 9:16).

    Returns:
        Lista de VideoFileClips procesados.
    """
    if not video_paths:
        raise ValueError("No hay clips de video disponibles para procesar.")

    duration_per_clip = target_duration / len(video_paths)
    processed = []

    for path in video_paths:
        try:
            clip = VideoFileClip(path)

            # Redimensionar al aspecto 9:16 si es necesario
            if clip.w != target_width or clip.h != target_height:
                clip = clip.resized((target_width, target_height))

            # Ajustar duración: loop si es corto, cortar si es largo
            if clip.duration < duration_per_clip:
                clip = clip.with_effects([vfx.Loop(duration=duration_per_clip)])
            else:
                clip = clip.subclipped(0, duration_per_clip)

            processed.append(clip)
        except Exception as e:
            logger.warning(f"Error procesando clip {path}: {e}")
            continue

    if not processed:
        raise ValueError("Ningún clip de video pudo ser cargado correctamente.")

    return processed


def export_video(
    composite: CompositeVideoClip,
    output_path: str,
    fps: int = 30,
    codec: str = "libx264",
    audio_codec: str = "aac",
    preset: str = "fast",
    threads: int = 4,
) -> str:
    """
    Wrapper estandarizado de exportación de video.

    Args:
        composite: CompositeVideoClip final a exportar.
        output_path: Ruta del archivo de salida.
        fps: Frames por segundo.
        codec: Codec de video.
        audio_codec: Codec de audio.
        preset: Preset de velocidad de encoding.
        threads: Número de hilos para encoding.

    Returns:
        Ruta absoluta al archivo exportado.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    logger.info(f"[Export] Renderizando video a: {output_path}")
    composite.write_videofile(
        output_path,
        fps=fps,
        codec=codec,
        audio_codec=audio_codec,
        preset=preset,
        threads=threads,
        logger=None,
    )
    logger.info(f"[Export] Video exportado exitosamente: {output_path}")

    return output_path
