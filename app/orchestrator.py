"""
Orchestrator — Factory Pattern para selección de pipeline.

Punto central que ejecuta el pipeline completo según el engine:
  - engine="pexels" → Pipeline A (flujo actual intacto)
  - engine="ai"     → Pipeline B (1 video Kling mudo → N reels multi-idioma)

Ambos pipelines comparten:
  - Scraper de MercadoLibre (datos del producto)

Pipeline A:
  - LLM Script Generator (guion single-language)
  - ElevenLabs TTS (voz en off)
  - Videos de stock de Pexels + Renderer básico

Pipeline B:
  - LLM genera prompt de video hipnótico (ai_prompt_engineer)
  - Kling API genera 1 video mudo (image-to-video, siempre con foto del producto)
  - LLM genera guiones en N idiomas en una sola llamada
  - ElevenLabs TTS genera audio con timestamps × N idiomas (voces nativas)
  - Viral renderer compone N reels finales (video mudo + audio por idioma)
"""

import json
import logging
import asyncio
from sqlalchemy.orm import Session

from app.database.models import Product, Video, ContentStatus
from app.llm.script_generator import (
    generate_video_script,
    generate_multilang_scripts,
    DEFAULT_LANGUAGES,
    LANGUAGE_MAP,
)

# Pipeline A imports (existente)
from app.media.media_manager import process_media_for_video
from app.render.video_renderer import render_final_video

# Pipeline B imports (nuevo)
from app.ai_engine.ai_prompt_engineer import generate_video_prompt
from app.ai_engine.ai_video_generator import generate_ai_video_batch
from app.utils.elevenlabs import generate_tts_with_timestamps, resolve_voice_for_language
from app.render.viral_renderer import render_viral_video

logger = logging.getLogger(__name__)


async def run_pipeline(
    product_id: int,
    engine: str,
    db: Session,
    strategy: str = "problem_first",
    language: str = "Spanish (LATAM)",
    languages: list[str] | None = None,
) -> dict:
    """
    Ejecuta el pipeline completo de generación de video.

    Args:
        product_id: ID del producto en la base de datos.
        engine: Motor a usar ("pexels" para Pipeline A, "ai" para Pipeline B).
        db: Sesión de SQLAlchemy.
        strategy: Estrategia para Pipeline A (ignorada en Pipeline B).
        language: Idioma para Pipeline A (single-language).
        languages: Lista de códigos de idioma para Pipeline B multi-idioma.

    Returns:
        Dict con el resultado del pipeline, incluyendo video_id(s) y paths.
    """
    # ── 1. Validar Producto ───────────────────────────────────────────────────
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise ValueError(f"Producto con ID {product_id} no encontrado.")

    logger.info(
        f"[Orchestrator] Iniciando pipeline '{engine}' para producto {product_id}: "
        f"{product.title}"
    )

    # ── 2. Ejecutar el Pipeline según el Engine ───────────────────────────────
    try:
        if engine == "pexels":
            # Pipeline A: single-language (flujo original intacto)
            script_data = await generate_video_script(
                title=product.title or "Producto genérico",
                price=product.price or 0.0,
                features=product.features or "Excelente producto.",
                rating=product.rating,
                reviews_count=product.reviews_count,
                language=language,
            )

            video = Video(
                product_id=product.id,
                hook=script_data.hook,
                script=script_data.body,
                call_to_action=script_data.cta,
                cta_keyword=script_data.cta_keyword,
                keywords=json.dumps(script_data.keywords),
                engine=engine,
                language="es",
                status=ContentStatus.SCRIPT_GENERATED,
            )
            db.add(video)
            db.commit()
            db.refresh(video)

            result = await _run_pipeline_pexels(product, video, script_data, db)

        elif engine == "ai":
            # Pipeline B: multi-idioma (1 video Kling → N reels)
            result = await _run_pipeline_ai(
                product=product,
                db=db,
                languages=languages or DEFAULT_LANGUAGES,
            )

        else:
            raise ValueError(f"Engine no soportado: {engine}. Usa 'pexels' o 'ai'.")

        return result

    except Exception as e:
        logger.error(f"[Orchestrator] Error en pipeline '{engine}': {e}")
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE A — PEXELS (Flujo existente, sin modificaciones)
# ═══════════════════════════════════════════════════════════════════════════════

async def _run_pipeline_pexels(
    product: Product,
    video: Video,
    script_data,
    db: Session,
) -> dict:
    """
    Pipeline A: Usa videos de stock de Pexels + renderer básico.
    Replica el flujo actual sin modificar los módulos originales.
    """
    # Texto completo para TTS
    full_text = f"{video.hook} {video.script} {video.call_to_action}"
    keywords = json.loads(video.keywords) if video.keywords else []

    # Generar audio + descargar stock en paralelo
    audio_path, stock_paths = await process_media_for_video(
        video_id=video.id,
        full_text=full_text,
        keywords=keywords,
    )

    video.audio_path = audio_path
    video.stock_videos_paths = json.dumps(stock_paths)
    video.status = ContentStatus.MEDIA_DOWNLOADED
    db.commit()

    # Renderizar video final con el renderer original
    final_path = await render_final_video(
        video_id=video.id,
        audio_path=audio_path,
        stock_paths=stock_paths,
        hook_text=video.hook or "¡No te pierdas este producto!",
        cta_keyword=video.cta_keyword,
        product_image_url=product.image_url,
    )

    video.final_video_path = final_path
    video.status = ContentStatus.RENDERED
    db.commit()
    db.refresh(video)

    return {
        "status": "success",
        "engine": "pexels",
        "video_id": video.id,
        "product_id": product.id,
        "message": "¡Video renderizado con Pipeline A (Pexels)!",
        "data": {
            "final_video_path": final_path,
            "audio_path": audio_path,
            "stock_videos_count": len(stock_paths),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE B — AI VIDEO MULTI-IDIOMA
# ═══════════════════════════════════════════════════════════════════════════════

async def _run_pipeline_ai(
    product: Product,
    db: Session,
    languages: list[str],
) -> dict:
    """
    Pipeline B: 1 video mudo de Kling → N reels finales multi-idioma.

    Flujo:
      1. LLM genera prompt hipnótico de video (ai_prompt_engineer)
      2. Kling API genera 1 video mudo (image-to-video, siempre con foto del producto)
      3. LLM genera guiones en N idiomas en una sola llamada
      4. Para cada idioma (en paralelo):
         a. ElevenLabs TTS genera audio CON timestamps (voz nativa del idioma)
         b. Viral renderer compone el Reel final (video mudo + audio + subtítulos)
         c. Se crea un registro Video en la DB

    Los pasos 2 y 3 se ejecutan en paralelo con asyncio.gather().
    """
    # ── Paso 1: Generar Prompt de Video Hipnótico ─────────────────────────────
    logger.info(f"[Pipeline B] Generando prompt de video IA para producto {product.id}")

    ai_prompt = await generate_video_prompt(
        product_title=product.title or "Producto genérico",
        product_features=product.features or "Excelente producto.",
        image_url=product.image_url,
        price=product.price,
        num_clips=2,
        strategy="product_first",  # Siempre image-to-video en Pipeline B
    )

    logger.info(f"[Pipeline B] Prompt generado: {ai_prompt.scene_description}")

    # ── Paso 2 + 3: Generar Video IA + Guiones Multi-Idioma en Paralelo ──────
    clip_prompts = ai_prompt.clip_prompts if ai_prompt.clip_prompts else [ai_prompt.video_prompt]

    logger.info(
        f"[Pipeline B] Lanzando {len(clip_prompts)} clips IA + guiones multi-idioma "
        f"({len(languages)} idiomas) en paralelo..."
    )

    # Usamos un video_id temporal (0) para Kling; se renombrará después
    video_task = generate_ai_video_batch(
        prompts=clip_prompts,
        video_id=product.id,  # Usar product_id para organizar archivos base
        image_url=product.image_url,  # SIEMPRE image-to-video
        aspect_ratio="9:16",
        duration=ai_prompt.suggested_duration,
    )

    scripts_task = generate_multilang_scripts(
        title=product.title or "Producto genérico",
        price=product.price or 0.0,
        features=product.features or "Excelente producto.",
        rating=product.rating,
        reviews_count=product.reviews_count,
        languages=languages,
    )

    # asyncio.gather para máxima paralelización
    ai_clips_paths, lang_scripts = await asyncio.gather(video_task, scripts_task)

    logger.info(
        f"[Pipeline B] Video IA generado ({len(ai_clips_paths)} clips) + "
        f"{len(lang_scripts)} guiones multi-idioma listos"
    )

    # ── Paso 4: Para cada idioma → TTS + Render + DB (en paralelo) ────────────
    async def _process_language(lang_script) -> dict:
        """Procesa un idioma: crea Video en DB → TTS → Render → actualiza DB."""
        lang_code = lang_script.language_code
        lang_name = LANGUAGE_MAP.get(lang_code, lang_code)

        # Crear registro Video para este idioma
        video = Video(
            product_id=product.id,
            hook=lang_script.hook,
            script=lang_script.body,
            call_to_action=lang_script.cta,
            cta_keyword=lang_script.cta_keyword,
            keywords=json.dumps(lang_script.keywords),
            engine="ai",
            language=lang_code,
            ai_video_prompt=ai_prompt.video_prompt,
            base_video_path=json.dumps(ai_clips_paths),
            stock_videos_paths=json.dumps(ai_clips_paths),
            status=ContentStatus.SCRIPT_GENERATED,
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        logger.info(f"[Pipeline B/{lang_code}] Video {video.id} creado para {lang_name}")

        try:
            # TTS con voz nativa del idioma
            full_text = f"{video.hook} {video.script} {video.call_to_action}"
            voice_id = resolve_voice_for_language(lang_code)

            audio_path, word_timestamps = await generate_tts_with_timestamps(
                video_id=video.id,
                text=full_text,
                voice_id=voice_id,
            )

            video.audio_path = audio_path
            video.status = ContentStatus.MEDIA_DOWNLOADED
            db.commit()

            logger.info(
                f"[Pipeline B/{lang_code}] Audio generado: {len(word_timestamps)} palabras"
            )

            # Renderizar reel viral con video mudo + audio del idioma
            final_path = await render_viral_video(
                video_id=video.id,
                ai_clips_paths=ai_clips_paths,
                audio_path=audio_path,
                hook_text=video.call_to_action or video.hook or "",
                word_timestamps=word_timestamps,
                cta_keyword=video.cta_keyword,
                dark_overlay_opacity=0.15,
                subtitle_words_per_group=3,
            )

            video.final_video_path = final_path
            video.status = ContentStatus.RENDERED
            db.commit()
            db.refresh(video)

            logger.info(f"[Pipeline B/{lang_code}] ¡Reel {lang_name} renderizado! → {final_path}")

            return {
                "language": lang_code,
                "language_name": lang_name,
                "video_id": video.id,
                "final_video_path": final_path,
                "audio_path": audio_path,
                "subtitle_words": len(word_timestamps),
                "cta_keyword": video.cta_keyword,
            }

        except Exception as e:
            video.status = ContentStatus.ERROR
            db.commit()
            logger.error(f"[Pipeline B/{lang_code}] Error procesando idioma: {e}")
            return {
                "language": lang_code,
                "language_name": lang_name,
                "video_id": video.id,
                "error": str(e),
            }

    # Ejecutar todos los idiomas en paralelo
    lang_results = await asyncio.gather(
        *[_process_language(script) for script in lang_scripts],
        return_exceptions=True,
    )

    # Procesar resultados
    successful = []
    failed = []
    for result in lang_results:
        if isinstance(result, Exception):
            failed.append({"error": str(result)})
        elif "error" in result:
            failed.append(result)
        else:
            successful.append(result)

    logger.info(
        f"[Pipeline B] Completado: {len(successful)} reels exitosos, {len(failed)} errores"
    )

    return {
        "status": "success" if successful else "error",
        "engine": "ai",
        "product_id": product.id,
        "message": (
            f"¡{len(successful)} reels multi-idioma generados con Pipeline B! "
            f"({len(failed)} errores)"
        ),
        "data": {
            "ai_clips_count": len(ai_clips_paths),
            "ai_prompt_used": ai_prompt.scene_description,
            "camera_movement": ai_prompt.camera_movement,
            "reels": successful,
            "errors": failed,
        },
    }
