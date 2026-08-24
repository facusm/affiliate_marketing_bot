"""
Orchestrator — Pipeline de generación de video IA multi-idioma.

Punto central que ejecuta el pipeline completo:
  1. LLM genera prompt de video hipnótico (ai_prompt_engineer)
  2. Kling API genera 1 video mudo (image-to-video, siempre con foto del producto)
  3. LLM genera guiones en N idiomas en una sola llamada
  4. Para cada idioma (en paralelo, con sesiones DB independientes):
     a. ElevenLabs TTS genera audio CON timestamps (voz nativa del idioma)
     b. Viral renderer compone el Reel final (video mudo + audio + subtítulos)
     c. Se persiste el resultado en la DB
"""

import json
import logging
import asyncio
import os
import httpx

from app.database.models import Product, Video, ContentStatus
from app.database.database import SessionLocal
from app.llm.script_generator import (
    generate_multilang_scripts,
    DEFAULT_LANGUAGES,
    LANGUAGE_MAP,
)
from app.ai_engine.ai_prompt_engineer import generate_video_prompt
from app.ai_engine.ai_video_generator import generate_ai_video_batch
from app.utils.elevenlabs import generate_tts_with_timestamps, resolve_voice_for_language
from app.render.viral_renderer import render_viral_video

logger = logging.getLogger(__name__)


async def run_pipeline(
    product_id: int,
    db,
    languages: list[str] | None = None,
) -> dict:
    """
    Ejecuta el pipeline completo de generación de video IA multi-idioma.

    Args:
        product_id: ID del producto en la base de datos.
        db: Sesión de SQLAlchemy (solo lectura del producto).
        languages: Lista de códigos de idioma (default: es, en, pt, de, fr, it).

    Returns:
        Dict con el resultado del pipeline, incluyendo video_ids y paths.
    """
    # ── 1. Validar Producto ───────────────────────────────────────────────────
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise ValueError(f"Producto con ID {product_id} no encontrado.")

    logger.info(
        f"[Orchestrator] Iniciando pipeline para producto {product_id}: "
        f"{product.title}"
    )

    # Capturar datos del producto como valores simples para evitar
    # problemas de sesión cuando se usen en tareas paralelas.
    product_data = {
        "id": product.id,
        "title": product.title or "Producto genérico",
        "features": product.features or "Excelente producto.",
        "image_url": product.image_url,
        "price": product.price,
        "rating": product.rating,
        "reviews_count": product.reviews_count,
    }

    # ── 2. Ejecutar Pipeline AI Multi-Idioma ──────────────────────────────────
    try:
        result = await _run_pipeline_ai(
            product_data=product_data,
            languages=languages or DEFAULT_LANGUAGES,
        )
        return result

    except Exception as e:
        logger.error(f"[Orchestrator] Error en pipeline: {e}")
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-FLIGHT CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

async def _preflight_checks():
    """
    Realiza ping a las APIs críticas antes de comenzar el pipeline.
    Si alguna falla o no hay saldo, arroja ValueError abortando el proceso.
    """
    logger.info("[Orchestrator] 🔍 Ejecutando Pre-flight checks de APIs...")
    
    # 1. OpenAI (gpt-4o-mini)
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        raise ValueError("Falta OPENAI_API_KEY")
    async with httpx.AsyncClient() as client:
        res = await client.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {openai_key}"})
        if res.status_code != 200:
            raise ValueError(f"OpenAI API check falló: {res.status_code}")
            
    # 2. ElevenLabs
    eleven_key = os.getenv("ELEVENLABS_API_KEY", "")
    if not eleven_key:
        raise ValueError("Falta ELEVENLABS_API_KEY")
    async with httpx.AsyncClient() as client:
        res = await client.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": eleven_key})
        if res.status_code == 200:
            data = res.json()
            subs = data.get("subscription", {})
            chars_count = subs.get("character_count", 0)
            chars_limit = subs.get("character_limit", 0)
            if chars_count >= chars_limit and chars_limit > 0:
                raise ValueError("ElevenLabs: No quedan caracteres disponibles.")
        else:
            raise ValueError(f"ElevenLabs API check falló: {res.status_code}")
            
    # 3. Kling AI
    kling_key = os.getenv("KLING_API_KEY", "")
    if not kling_key:
        raise ValueError("Falta KLING_API_KEY")
    async with httpx.AsyncClient() as client:
        res = await client.get("https://api.klingai.com/v1/videos/text2video", headers={"Authorization": f"Bearer {kling_key}"})
        if res.status_code == 401:
            raise ValueError("Kling AI: Token inválido (401 Unauthorized)")
            
    logger.info("[Orchestrator] ✅ Pre-flight checks OK. APIs operativas.")

# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE AI VIDEO MULTI-IDIOMA
# ═══════════════════════════════════════════════════════════════════════════════

async def _run_pipeline_ai(
    product_data: dict,
    languages: list[str],
) -> dict:
    """
    Pipeline: 1 video mudo de Kling → N reels finales multi-idioma.

    Flujo:
      1. LLM genera prompt hipnótico de video (ai_prompt_engineer)
      2. Kling API genera 1 video mudo (image-to-video)           ┐
      3. LLM genera guiones en N idiomas en una sola llamada      ┘ en paralelo
      4. Para cada idioma (en paralelo, sesiones DB independientes):
         a. ElevenLabs TTS genera audio CON timestamps (voz nativa)
         b. Viral renderer compone el Reel final
         c. Se crea un registro Video en la DB

    Cada tarea de idioma instancia su propia SessionLocal()
    para evitar race conditions en escrituras concurrentes.
    """
    product_id = product_data["id"]

    # ── 0. Pre-Flight Checks ──────────────────────────────────────────────────
    await _preflight_checks()

    # ── 1. Buscar Checkpoint (Resumption) ─────────────────────────────────────
    db_check = SessionLocal()
    existing_videos = db_check.query(Video).filter(Video.product_id == product_id).all()
    db_check.close()
    
    ai_clips_paths = []
    ai_prompt_used = ""
    camera_used = ""
    
    for v in existing_videos:
        if v.base_video_path:
            try:
                paths = json.loads(v.base_video_path)
                if paths:
                    ai_clips_paths = paths
                    ai_prompt_used = v.ai_video_prompt or "Recuperado de DB"
                    break
            except Exception:
                pass

    if ai_clips_paths:
        logger.info(f"[Pipeline] ♻️ CHECKPOINT: Video base de Kling ya existe. Omitiendo generación de video IA.")
        # Aún necesitamos los scripts
        lang_scripts = await generate_multilang_scripts(
            title=product_data["title"],
            price=product_data["price"] or 0.0,
            features=product_data["features"],
            rating=product_data["rating"],
            reviews_count=product_data["reviews_count"],
            languages=languages,
        )
    else:
        # ── 2. Generar Video IA + Guiones Multi-Idioma en Paralelo ────────────
        logger.info(f"[Pipeline] Generando prompt de video IA para producto {product_id}")
        ai_prompt = await generate_video_prompt(
            product_title=product_data["title"],
            product_features=product_data["features"],
            image_url=product_data["image_url"],
            price=product_data["price"],
            num_clips=2,
            strategy="product_first",
        )
        ai_prompt_used = ai_prompt.scene_description
        camera_used = getattr(ai_prompt, "camera_movement", "")
        clip_prompts = ai_prompt.clip_prompts if getattr(ai_prompt, "clip_prompts", None) else [ai_prompt.video_prompt]

        logger.info(f"[Pipeline] Lanzando {len(clip_prompts)} clips IA + guiones en paralelo...")
        video_task = generate_ai_video_batch(
            prompts=clip_prompts,
            video_id=product_id,
            image_url=product_data["image_url"],
            aspect_ratio="9:16",
            duration=getattr(ai_prompt, "suggested_duration", 5),
        )
        scripts_task = generate_multilang_scripts(
            title=product_data["title"],
            price=product_data["price"] or 0.0,
            features=product_data["features"],
            rating=product_data["rating"],
            reviews_count=product_data["reviews_count"],
            languages=languages,
        )

        ai_clips_paths, lang_scripts = await asyncio.gather(video_task, scripts_task)
        logger.info(f"[Pipeline] Video IA generado ({len(ai_clips_paths)} clips) + {len(lang_scripts)} guiones.")

    # ── Paso 3: Para cada idioma → TTS + Render + DB (en paralelo) ────────────

    async def _process_language(lang_script) -> dict:
        """
        Procesa un idioma completo: crea Video en DB → TTS → Render.
        Usa su propia sesión de DB para evitar race conditions.
        """
        lang_code = lang_script.language_code
        lang_name = LANGUAGE_MAP.get(lang_code, lang_code)

        # ── Sesión de DB independiente para esta tarea ────────────────────
        db = SessionLocal()
        video = None
        try:
            # Buscar si ya existe el registro Video para reutilizarlo
            video = db.query(Video).filter(
                Video.product_id == product_id,
                Video.language == lang_code
            ).first()
            
            if not video:
                video = Video(product_id=product_id, language=lang_code)
                db.add(video)

            # Actualizar registro
            video.hook = lang_script.hook
            video.script = lang_script.body
            video.call_to_action = lang_script.cta
            video.cta_keyword = lang_script.cta_keyword
            video.keywords = json.dumps(lang_script.keywords)
            video.engine = "ai"
            video.ai_video_prompt = ai_prompt_used
            video.base_video_path = json.dumps(ai_clips_paths)
            video.stock_videos_paths = json.dumps(ai_clips_paths)
            
            if not video.status or video.status == ContentStatus.PENDING:
                video.status = ContentStatus.SCRIPT_GENERATED
                
            db.commit()
            db.refresh(video)

            logger.info(f"[Pipeline/{lang_code}] Video {video.id} creado para {lang_name}")

            # ── TTS con voz nativa del idioma ─────────────────────────────
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
                f"[Pipeline/{lang_code}] Audio generado: {len(word_timestamps)} palabras"
            )

            # ── Renderizar reel viral ─────────────────────────────────────
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

            logger.info(f"[Pipeline/{lang_code}] ¡Reel {lang_name} renderizado! → {final_path}")

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
            db.rollback()
            if video and video.id:
                try:
                    video.status = ContentStatus.ERROR
                    db.commit()
                except Exception:
                    db.rollback()
            logger.error(f"[Pipeline/{lang_code}] Error procesando idioma: {e}")
            return {
                "language": lang_code,
                "language_name": lang_name,
                "video_id": getattr(video, "id", None),
                "error": str(e),
            }
        finally:
            db.close()

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
        f"[Pipeline] Completado: {len(successful)} reels exitosos, {len(failed)} errores"
    )

    return {
        "status": "success" if successful else "error",
        "engine": "ai",
        "product_id": product_id,
        "message": (
            f"¡{len(successful)} reels multi-idioma generados! "
            f"({len(failed)} errores)"
        ),
        "data": {
            "ai_clips_count": len(ai_clips_paths),
            "ai_prompt_used": ai_prompt_used,
            "camera_movement": camera_used,
            "reels": successful,
            "errors": failed,
        },
    }
