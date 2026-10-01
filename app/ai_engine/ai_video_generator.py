"""
AI Video Generator — Cliente multi-provider para generación de video con IA.

Soporta múltiples providers de video IA a través de una interfaz unificada:
  - Runway Gen-3/Gen-4 Alpha Turbo
  - Kling AI
  - Luma Dream Machine
  - Replicate (modelos open-source)

Todas las APIs de video IA siguen el mismo patrón async:
  1. Enviar job (POST con el prompt)
  2. Polling del status (GET hasta que termine)
  3. Descargar el resultado (GET del video renderizado)

Usa asyncio para paralelizar la generación de múltiples clips.
"""

import os
import asyncio
import logging
import base64
import httpx
import time
from enum import Enum
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ─── Configuración ────────────────────────────────────────────────────────────

AI_VIDEO_PROVIDER = os.getenv("AI_VIDEO_PROVIDER", "kling").lower()
KLING_API_KEY = os.getenv("KLING_API_KEY", "")

STORAGE_VIDEO_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../storage/videos")
)
os.makedirs(STORAGE_VIDEO_DIR, exist_ok=True)


class VideoProvider(str, Enum):
    RUNWAY = "runway"
    KLING = "kling"
    LUMA = "luma"
    REPLICATE = "replicate"
    MOCK = "mock"


# ─── Interfaz Unificada ──────────────────────────────────────────────────────

async def generate_ai_video(
    prompt: str,
    video_id: int,
    clip_index: int = 0,
    image_url: str | None = None,
    aspect_ratio: str = "9:16",
    duration: float = 5.0,
    provider: str | None = None,
) -> str:
    """
    Genera un video con IA usando el provider configurado.
    Si se provee image_url, usa image-to-video (el producto real).
    Si no, usa text-to-video (producto genérico generado por IA).

    Args:
        prompt: Prompt detallado para la generación de video.
        video_id: ID del video (para organizar archivos).
        clip_index: Índice del clip (0, 1, 2...) cuando se generan múltiples.
        image_url: URL de la foto real del producto (para image-to-video).
        aspect_ratio: Aspecto del video (default "9:16" para Reels).
        duration: Duración en segundos (3-10 según provider).
        provider: Override del provider (None = usar env var).

    Returns:
        Ruta absoluta al archivo de video descargado (.mp4).
    """
    resolved_provider = provider or AI_VIDEO_PROVIDER

    mode = "image-to-video" if image_url else "text-to-video"
    logger.info(
        f"[AI Video] Generando clip {clip_index} para video {video_id} "
        f"con provider: {resolved_provider} ({mode})"
    )

    if resolved_provider == VideoProvider.RUNWAY:
        return await _generate_runway(prompt, video_id, clip_index, image_url, aspect_ratio, duration)
    elif resolved_provider == VideoProvider.KLING:
        return await _generate_kling(prompt, video_id, clip_index, image_url, aspect_ratio, duration)
    elif resolved_provider == VideoProvider.LUMA:
        return await _generate_luma(prompt, video_id, clip_index, image_url, aspect_ratio, duration)
    elif resolved_provider == VideoProvider.REPLICATE:
        return await _generate_replicate(prompt, video_id, clip_index, image_url, aspect_ratio, duration)
    elif resolved_provider == VideoProvider.MOCK:
        return await _generate_mock(prompt, video_id, clip_index, image_url, aspect_ratio, duration)
    else:
        raise ValueError(f"Provider de video IA no soportado: {resolved_provider}")


async def generate_hybrid_clips(
    i2v_prompt: str,
    b_roll_1_prompt: str,
    b_roll_2_prompt: str,
    video_id: int,
    image_url: str | None = None,
    aspect_ratio: str = "9:16",
    duration: float = 5.0,
    provider: str | None = None,
) -> dict[str, str]:
    """
    Genera 3 clips de video en paralelo con arquitectura híbrida I2V + T2V.

    Lanza 3 tareas simultáneas:
      - Tarea A (I2V): Foto del producto con cámara estática.
      - Tarea B (T2V): B-Roll sensorial/aspiracional.
      - Tarea C (T2V): B-Roll del producto en uso (macro).

    Args:
        i2v_prompt: Prompt para el clip I2V (se le agrega instrucción de cámara estática).
        b_roll_1_prompt: Prompt T2V para B-Roll sensorial.
        b_roll_2_prompt: Prompt T2V para B-Roll producto en uso.
        video_id: ID del video (para organizar archivos).
        image_url: URL/ruta de la foto real del producto (para I2V).
        aspect_ratio: Aspecto del video (default "9:16").
        duration: Duración en segundos por clip.
        provider: Override del provider (None = usar env var).

    Returns:
        Dict con claves "i2v", "b_roll_1", "b_roll_2" → rutas a los .mp4.
    """
    # Instrucción estricta de cámara estática para el clip I2V
    static_camera_instruction = (
        "Locked-off camera, static shot, absolute no camera movement. "
        "Only the liquid/steam/context is moving. Ultra realistic."
    )
    i2v_full_prompt = f"{i2v_prompt} {static_camera_instruction}"

    logger.info(
        f"[AI Video Hybrid] Lanzando 3 clips en paralelo para video {video_id}: "
        f"1 I2V + 2 T2V"
    )

    # Lanzar las 3 tareas en paralelo
    results = await asyncio.gather(
        # Tarea A: I2V con foto del producto (cámara estática)
        generate_ai_video(
            prompt=i2v_full_prompt,
            video_id=video_id,
            clip_index=0,
            image_url=image_url,
            aspect_ratio=aspect_ratio,
            duration=duration,
            provider=provider,
        ),
        # Tarea B: T2V B-Roll 1 (sensorial/aspiracional)
        generate_ai_video(
            prompt=b_roll_1_prompt,
            video_id=video_id,
            clip_index=1,
            image_url=None,  # T2V: sin imagen
            aspect_ratio=aspect_ratio,
            duration=duration,
            provider=provider,
        ),
        # Tarea C: T2V B-Roll 2 (producto en uso, macro)
        generate_ai_video(
            prompt=b_roll_2_prompt,
            video_id=video_id,
            clip_index=2,
            image_url=None,  # T2V: sin imagen
            aspect_ratio=aspect_ratio,
            duration=duration,
            provider=provider,
        ),
        return_exceptions=True,
    )

    # Procesar resultados
    labels = ["i2v", "b_roll_1", "b_roll_2"]
    clip_paths = {}
    errors = []

    for i, (label, result) in enumerate(zip(labels, results)):
        if isinstance(result, Exception):
            logger.error(f"[AI Video Hybrid] Error en {label} (clip {i}): {result}")
            errors.append(f"{label}: {result}")
        else:
            clip_paths[label] = result
            logger.info(f"[AI Video Hybrid] {label} completado: {result}")

    if not clip_paths:
        raise RuntimeError(
            f"No se pudo generar ningún clip de video con IA. Errores: {errors}"
        )

    if "i2v" not in clip_paths:
        logger.warning(
            "[AI Video Hybrid] El clip I2V falló. Usando primer B-Roll como fallback."
        )

    logger.info(
        f"[AI Video Hybrid] {len(clip_paths)}/3 clips generados exitosamente."
    )

    return clip_paths


async def generate_ai_video_batch(
    prompts: list[str],
    video_id: int,
    image_url: str | None = None,
    aspect_ratio: str = "9:16",
    duration: float = 5.0,
    provider: str | None = None,
) -> list[str]:
    """
    Genera múltiples clips de video en paralelo con asyncio.gather().

    Args:
        prompts: Lista de prompts (uno por clip).
        video_id: ID del video.
        image_url: URL de la foto real del producto (para image-to-video).
        aspect_ratio: Aspecto del video.
        duration: Duración por clip.
        provider: Override del provider.

    Returns:
        Lista de rutas a los videos descargados.
    """
    tasks = [
        generate_ai_video(
            prompt=prompt,
            video_id=video_id,
            clip_index=i,
            image_url=image_url,
            aspect_ratio=aspect_ratio,
            duration=duration,
            provider=provider,
        )
        for i, prompt in enumerate(prompts)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filtrar errores y retornar solo los paths exitosos
    paths = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"[AI Video] Error en clip {i}: {result}")
        else:
            paths.append(result)

    if not paths:
        raise RuntimeError("No se pudo generar ningún clip de video con IA.")

    return paths


# ─── Helpers Comunes ──────────────────────────────────────────────────────────

def _resolve_image_ref(image_ref: str | None) -> str | None:
    """
    Resuelve la referencia de imagen para APIs de video IA.
    Si es una URL (http/https), la retorna tal cual.
    Si es una ruta local, la convierte a base64 string para la API.
    """
    if not image_ref:
        return None

    if image_ref.startswith(("http://", "https://")):
        return image_ref

    # Ruta local → leer y convertir a base64
    if os.path.isfile(image_ref):
        with open(image_ref, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        ext = os.path.splitext(image_ref)[1].lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }
        mime = mime_map.get(ext, "image/png")
        logger.info(f"[AI Video] Imagen local convertida a base64 ({len(data)} bytes)")
        return f"data:{mime};base64,{b64}"

    logger.warning(f"[AI Video] Referencia de imagen no resuelta: {image_ref}")
    return image_ref


def _get_output_path(video_id: int, clip_index: int) -> str:
    """Genera la ruta de salida para un clip de video IA."""
    video_dir = os.path.join(STORAGE_VIDEO_DIR, str(video_id))
    os.makedirs(video_dir, exist_ok=True)
    return os.path.join(video_dir, f"{clip_index}.mp4")


async def _poll_and_download(
    client: httpx.AsyncClient,
    status_url: str,
    headers: dict,
    output_path: str,
    status_field: str = "status",
    success_value: str = "succeeded",
    failure_values: list[str] | None = None,
    video_url_field: str = "output",
    max_wait_seconds: int = 1100,
    poll_interval: int = 10,
) -> str:
    """
    Polling genérico: espera a que el job termine y descarga el video.

    Args:
        client: Cliente HTTP async.
        status_url: URL para consultar el estado del job.
        headers: Headers de autenticación.
        output_path: Ruta donde guardar el video descargado.
        status_field: Nombre del campo de status en la respuesta JSON.
        success_value: Valor que indica que el job terminó exitosamente.
        failure_values: Valores que indican error.
        video_url_field: Campo que contiene la URL del video generado.
        max_wait_seconds: Tiempo máximo de espera antes de timeout.
        poll_interval: Intervalo entre consultas en segundos.

    Returns:
        Ruta al video descargado.
    """
    failure_values = failure_values or ["failed", "error", "cancelled"]
    elapsed = 0

    while elapsed < max_wait_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        try:
            response = await client.get(status_url, headers=headers, timeout=15.0)
            response.raise_for_status()
            data = response.json()

            status = _extract_nested(data, status_field) or "unknown"
            logger.info(f"[AI Video Poll] Status: {status} ({elapsed}s elapsed)")

            if status == success_value:
                # Extraer la URL del video (puede estar anidada)
                video_url = _extract_nested(data, video_url_field)
                if not video_url:
                    raise RuntimeError(f"Job exitoso pero no se encontró URL de video en campo '{video_url_field}'")

                # Descargar el video
                await _download_video(client, video_url, output_path)
                return output_path

            elif status in failure_values:
                error_msg = data.get("error", data.get("failure_reason", "Error desconocido"))
                raise RuntimeError(f"Job de video IA falló: {error_msg}")

        except httpx.HTTPStatusError as e:
            logger.warning(f"[AI Video Poll] HTTP Error {e.response.status_code}, reintentando...")

    raise TimeoutError(f"Timeout: el job de video IA no terminó en {max_wait_seconds}s")


def _extract_nested(data: dict, field_path: str):
    """Extrae un valor de un dict, soportando paths con punto (ej: 'output.video')."""
    keys = field_path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and key.isdigit():
            current = current[int(key)]
        else:
            return None
    return current


async def _download_video(client: httpx.AsyncClient, url: str, output_path: str):
    """Descarga un video desde una URL a disco."""
    logger.info(f"[AI Video] Descargando video desde: {url[:80]}...")
    async with client.stream("GET", url, timeout=120.0, follow_redirects=True) as stream:
        stream.raise_for_status()
        with open(output_path, "wb") as f:
            async for chunk in stream.aiter_bytes(chunk_size=8192):
                f.write(chunk)
    logger.info(f"[AI Video] Video descargado: {output_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# PROVIDER IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Runway Gen-3/Gen-4 ──────────────────────────────────────────────────────

async def _generate_runway(
    prompt: str, video_id: int, clip_index: int,
    image_url: str | None, aspect_ratio: str, duration: float,
) -> str:
    """
    Genera video con Runway API (Gen-3 Alpha Turbo).
    Usa image-to-video si se provee image_url.
    Docs: https://docs.dev.runwayml.com/
    """
    output_path = _get_output_path(video_id, clip_index)
    api_key = AI_VIDEO_API_KEY

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Runway-Version": "2024-11-06",
    }

    # Runway usa duración en segundos (5 o 10)
    runway_duration = 5 if duration <= 5 else 10

    payload = {
        "promptText": prompt,
        "model": "gen3a_turbo",
        "duration": runway_duration,
        "ratio": aspect_ratio.replace(":", ":"),  # "9:16"
        "watermark": False,
    }

    # Si hay imagen del producto, usarla como referencia visual
    if image_url:
        payload["promptImage"] = image_url

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.dev.runwayml.com/v1/image_to_video",
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        job_id = response.json().get("id")

        logger.info(f"[Runway] Job creado: {job_id}")

        status_url = f"https://api.dev.runwayml.com/v1/tasks/{job_id}"
        return await _poll_and_download(
            client=client,
            status_url=status_url,
            headers=headers,
            output_path=output_path,
            status_field="status",
            success_value="SUCCEEDED",
            failure_values=["FAILED", "CANCELLED"],
            video_url_field="output.0",
        )


# ─── Kling AI ────────────────────────────────────────────────────────────────

async def _generate_kling(
    prompt: str, video_id: int, clip_index: int,
    image_url: str | None, aspect_ratio: str, duration: float,
) -> str:
    """
    Genera video con Kling AI API usando API Key Auth (Bearer token).
    Usa image-to-video si se provee image_url (la foto real del producto).
    Docs: https://docs.qingque.cn/d/home/eZQBMqNmerEIbJ_GBwojkGqtl
    """
    output_path = _get_output_path(video_id, clip_index)
    
    if not KLING_API_KEY:
        logger.error("[Kling] Falta KLING_API_KEY en .env")

    headers = {
        "Authorization": f"Bearer {KLING_API_KEY}",
        "Content-Type": "application/json",
    }

    # Resolver la imagen (URL o ruta local → base64)
    resolved_image = _resolve_image_ref(image_url)

    # Decidir entre image-to-video o text-to-video
    if resolved_image:
        # IMAGE-TO-VIDEO: usa la foto real del producto como referencia
        endpoint = "https://api.klingai.com/v1/videos/image2video"
        payload = {
            "model_name": "kling-v3",
            "mode": "std",
            "image": resolved_image,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "duration": str(int(duration)),
        }
        logger.info(f"[Kling] Usando image-to-video con foto del producto (Modelo V3.0 Estándar)")
    else:
        # TEXT-TO-VIDEO: genera producto genérico desde el prompt
        endpoint = "https://api.klingai.com/v1/videos/text2video"
        payload = {
            "model_name": "kling-v3",
            "mode": "std",
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "duration": str(int(duration)),
        }
        logger.info(f"[Kling] Usando text-to-video (sin imagen de referencia) (Modelo V1.6)")

    async with httpx.AsyncClient() as client:
        max_retries = 5
        for attempt in range(max_retries):
            response = await client.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            
            if response.status_code == 429 and attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s, 8s
                logger.warning(f"[Kling] 429 Too Many Requests. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
                
            try:
                response.raise_for_status()
            except Exception as e:
                logger.error(f"[Kling] Error de la API: {response.text}")
                raise
            break

        data = response.json()
        task_id = data.get("data", {}).get("task_id")

        logger.info(f"[Kling] Task creado: {task_id}")

        # El endpoint de status es el mismo para ambos modos
        status_url = f"https://api.klingai.com/v1/videos/image2video/{task_id}" if image_url else f"https://api.klingai.com/v1/videos/text2video/{task_id}"
        return await _poll_and_download(
            client=client,
            status_url=status_url,
            headers=headers,
            output_path=output_path,
            status_field="data.task_status",
            success_value="succeed",
            failure_values=["failed"],
            video_url_field="data.task_result.videos.0.url",
        )


# ─── Luma Dream Machine ──────────────────────────────────────────────────────

async def _generate_luma(
    prompt: str, video_id: int, clip_index: int,
    image_url: str | None, aspect_ratio: str, duration: float,
) -> str:
    """
    Genera video con Luma AI (Dream Machine) API.
    Docs: https://docs.lumalabs.ai/docs/api
    """
    output_path = _get_output_path(video_id, clip_index)
    api_key = AI_VIDEO_API_KEY

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "loop": True,
    }

    # Si hay imagen, usarla como frame de referencia
    if image_url:
        payload["image_url"] = image_url

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.lumalabs.ai/dream-machine/v1/generations",
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        generation_id = response.json().get("id")

        logger.info(f"[Luma] Generation creada: {generation_id}")

        status_url = f"https://api.lumalabs.ai/dream-machine/v1/generations/{generation_id}"
        return await _poll_and_download(
            client=client,
            status_url=status_url,
            headers=headers,
            output_path=output_path,
            status_field="state",
            success_value="completed",
            failure_values=["failed"],
            video_url_field="assets.video",
        )


# ─── Replicate (Open-Source Models) ───────────────────────────────────────────

async def _generate_replicate(
    prompt: str, video_id: int, clip_index: int,
    image_url: str | None, aspect_ratio: str, duration: float,
) -> str:
    """
    Genera video con Replicate API (Wan2.1, CogVideoX, etc).
    Docs: https://replicate.com/docs/reference/http
    """
    output_path = _get_output_path(video_id, clip_index)
    api_key = AI_VIDEO_API_KEY

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    model_version = os.getenv(
        "REPLICATE_VIDEO_MODEL",
        "wan-ai/wan2.1:d83b161e1d2054640044e9a5b3b25e"
    )

    payload = {
        "version": model_version,
        "input": {
            "prompt": prompt,
            "num_frames": int(duration * 24),
            "width": 720,
            "height": 1280,
            "guidance_scale": 7.5,
        },
    }

    # Si hay imagen, pasarla como input de referencia
    if image_url:
        payload["input"]["image"] = image_url

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.replicate.com/v1/predictions",
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        prediction_id = response.json().get("id")

        logger.info(f"[Replicate] Prediction creada: {prediction_id}")

        status_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        return await _poll_and_download(
            client=client,
            status_url=status_url,
            headers=headers,
            output_path=output_path,
            status_field="status",
            success_value="succeeded",
            failure_values=["failed", "canceled"],
            video_url_field="output",
        )


# ─── Mock Provider (Para Pruebas) ─────────────────────────────────────────────

async def _generate_mock(
    prompt: str, video_id: int, clip_index: int,
    image_url: str | None, aspect_ratio: str, duration: float,
) -> str:
    """
    Genera un video falso (color sólido) usando MoviePy sin gastar créditos.
    Útil para pruebas locales del pipeline y post-producción.
    """
    output_path = _get_output_path(video_id, clip_index)
    logger.info(f"[Mock] Simulando generación de video... (clip {clip_index})")
    
    # Espera simulada
    await asyncio.sleep(2)
    
    width, height = 1080, 1920
    if aspect_ratio == "16:9":
        width, height = 1920, 1080
        
    # Colores distintos para diferenciar clips (RGB)
    colors = [(255, 100, 100), (100, 255, 100), (100, 100, 255)]
    color = colors[clip_index % len(colors)]
    
    def _write_mock_video():
        from moviepy import ColorClip
        clip = ColorClip(size=(width, height), color=color, duration=duration)
        clip.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio=False,
            logger=None,
        )
        clip.close()
        
    await asyncio.to_thread(_write_mock_video)
    logger.info(f"[Mock] Video falso generado exitosamente: {output_path}")
    return output_path
