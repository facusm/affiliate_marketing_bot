"""
Viral Renderer — Post-producción adictiva para Instagram Reels (Pipeline B).

Aplica el estilo visual típico de Reels virales de marketing faceless:
  1. Tinte oscuro sutil (overlay 15%) para resaltar texto
  2. Texto gancho fijo (CTA) en el tercio superior con fuente gruesa
  3. Subtítulos dinámicos estilo Alex Hormozi (palabra por palabra, centrados)
  4. Audio sincronizado con ElevenLabs TTS

NO modifica el renderer original (video_renderer.py) del Pipeline A.
"""

import os
import asyncio
import logging
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
)

from app.utils.moviepy_helpers import (
    apply_dark_overlay,
    create_hook_text,
    create_subtitle_clips,
    load_and_prepare_clips,
    export_video,
)

logger = logging.getLogger(__name__)

# Directorios de salida
STORAGE_OUTPUTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../storage/outputs")
)
os.makedirs(STORAGE_OUTPUTS_DIR, exist_ok=True)

# Resolución estándar para Reels 9:16
REEL_WIDTH = 1080
REEL_HEIGHT = 1920


def _render_viral_sync(
    video_id: int,
    ai_clips_paths: list[str],
    audio_path: str,
    hook_text: str,
    word_timestamps: list[dict] | None = None,
    cta_keyword: str | None = None,
    dark_overlay_opacity: float = 0.15,
    subtitle_words_per_group: int = 3,
) -> str:
    """
    Función sincrónica de composición viral con MoviePy.

    Capas del video final (de abajo hacia arriba):
      [0] Video base (clips IA concatenados, formato 9:16)
      [1] Dark overlay (negro, opacity configurable)
      [2] Hook/CTA text (fijo, tercio superior, toda la duración)
      [3] Subtítulos dinámicos (sincronizados con audio, centro)

    Args:
        video_id: ID del video para nombrar el archivo final.
        ai_clips_paths: Lista de rutas a los clips de video generados por IA.
        audio_path: Ruta al archivo de audio (ElevenLabs TTS).
        hook_text: Texto gancho/CTA fijo (ej: "Comentá OFERTA y te mando el link").
        word_timestamps: Timestamps por palabra para subtítulos dinámicos.
            Formato: [{"word": str, "start": float, "end": float}, ...]
        cta_keyword: Palabra clave del CTA (para formatear el hook text).
        dark_overlay_opacity: Opacidad del overlay oscuro (0.0 - 1.0).
        subtitle_words_per_group: Palabras por grupo de subtítulo (1=palabra, 3=frase corta).

    Returns:
        Ruta absoluta al video final renderizado (.mp4).
    """
    output_path = os.path.join(STORAGE_OUTPUTS_DIR, f"{video_id}_viral.mp4")

    # ── 1. Cargar Audio ───────────────────────────────────────────────────────
    audio_clip = AudioFileClip(audio_path)
    total_duration = audio_clip.duration

    # ── 2. Cargar y Preparar Clips de Video IA ────────────────────────────────
    processed_clips = load_and_prepare_clips(
        video_paths=ai_clips_paths,
        target_duration=total_duration,
        target_width=REEL_WIDTH,
        target_height=REEL_HEIGHT,
    )

    # Concatenar clips en secuencia
    base_video = concatenate_videoclips(processed_clips, method="compose")

    # Asegurar que el video base tenga las dimensiones correctas
    if base_video.w != REEL_WIDTH or base_video.h != REEL_HEIGHT:
        base_video = base_video.resized((REEL_WIDTH, REEL_HEIGHT))

    # Sincronizar con el audio
    base_video = base_video.with_audio(audio_clip)

    # ── 3. Construir Capas de Overlay ─────────────────────────────────────────
    overlay_layers = [base_video]

    # ── Capa 1: Dark Overlay (tinte oscuro sutil) ─────────────────────────────
    dark_layer = apply_dark_overlay(base_video, opacity=dark_overlay_opacity)
    overlay_layers.append(dark_layer)

    # ── Capa 2: Hook/CTA Text Fijo (tercio superior) ─────────────────────────
    # Formatear el texto del hook con la keyword si existe
    if cta_keyword:
        formatted_hook = f"Comentá {cta_keyword} y te mando el link 🔥"
    else:
        formatted_hook = hook_text

    try:
        hook_clip = create_hook_text(
            text=formatted_hook,
            video_width=REEL_WIDTH,
            video_height=REEL_HEIGHT,
            duration=total_duration,
            font_size=52,
            color="yellow",
            stroke_color="black",
            stroke_width=3,
        )
        overlay_layers.append(hook_clip)
    except Exception as e:
        logger.warning(f"[Viral Render] Error creando hook text: {e}. Continuando sin hook.")

    # ── Capa 3: Subtítulos Dinámicos Estilo Hormozi (centro) ──────────────────
    if word_timestamps:
        try:
            subtitle_layer = create_subtitle_clips(
                word_timestamps=word_timestamps,
                video_width=REEL_WIDTH,
                video_height=REEL_HEIGHT,
                font_size=55,
                color="white",
                highlight_color="#FFD700",
                stroke_color="black",
                stroke_width=3,
                words_per_group=subtitle_words_per_group,
            )
            overlay_layers.extend(subtitle_layer)
            logger.info(
                f"[Viral Render] {len(subtitle_layer)} grupos de subtítulos creados"
            )
        except Exception as e:
            logger.warning(f"[Viral Render] Error creando subtítulos: {e}. Continuando sin subtítulos.")
    else:
        logger.info("[Viral Render] No hay timestamps de audio. Saltando subtítulos dinámicos.")

    # ── 4. Componer Video Final ───────────────────────────────────────────────
    final_video = CompositeVideoClip(overlay_layers, size=(REEL_WIDTH, REEL_HEIGHT))

    # ── 5. Exportar ───────────────────────────────────────────────────────────
    logger.info(f"[Viral Render] Renderizando video viral {video_id}...")
    export_video(final_video, output_path, fps=30)

    # ── 6. Limpiar Memoria ────────────────────────────────────────────────────
    audio_clip.close()
    for clip in processed_clips:
        clip.close()
    base_video.close()
    final_video.close()

    logger.info(f"[Viral Render] ¡Video viral renderizado! → {output_path}")
    return output_path


async def render_viral_video(
    video_id: int,
    ai_clips_paths: list[str],
    audio_path: str,
    hook_text: str,
    word_timestamps: list[dict] | None = None,
    cta_keyword: str | None = None,
    dark_overlay_opacity: float = 0.15,
    subtitle_words_per_group: int = 3,
) -> str:
    """
    Función asíncrona que mueve la carga pesada de MoviePy a un hilo
    en segundo plano para no bloquear el event loop de FastAPI.

    Args:
        (mismos que _render_viral_sync)

    Returns:
        Ruta absoluta al video final renderizado.
    """
    return await asyncio.to_thread(
        _render_viral_sync,
        video_id,
        ai_clips_paths,
        audio_path,
        hook_text,
        word_timestamps,
        cta_keyword,
        dark_overlay_opacity,
        subtitle_words_per_group,
    )
