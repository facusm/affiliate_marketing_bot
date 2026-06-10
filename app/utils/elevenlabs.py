"""
Módulo utilitario de ElevenLabs TTS.

Extrae la lógica de Text-To-Speech para que sea reutilizable
entre Pipeline A (Pexels) y Pipeline B (AI Video).
Soporta generación de timestamps por palabra para subtítulos dinámicos.
"""

import os
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")

# ─── Mapeo de Voces Nativas por Idioma ─────────────────────────────────────────
# Cada idioma puede tener su propia voz nativa configurada via .env.
# Si no se configura una voz específica, se usa ELEVENLABS_VOICE_ID como fallback.

VOICE_MAP: dict[str, str] = {
    "es": os.getenv("ELEVENLABS_VOICE_ES", ""),
    "en": os.getenv("ELEVENLABS_VOICE_EN", ""),
    "pt": os.getenv("ELEVENLABS_VOICE_PT", ""),
    "de": os.getenv("ELEVENLABS_VOICE_DE", ""),
    "fr": os.getenv("ELEVENLABS_VOICE_FR", ""),
    "it": os.getenv("ELEVENLABS_VOICE_IT", ""),
}


def resolve_voice_for_language(language_code: str, override: str | None = None) -> str:
    """
    Resuelve el voice_id a usar para un idioma dado.
    Prioridad: override > VOICE_MAP[language_code] > ELEVENLABS_VOICE_ID (fallback global).
    """
    if override:
        return override
    mapped = VOICE_MAP.get(language_code, "")
    if mapped:
        return mapped
    return ELEVENLABS_VOICE_ID or ""


# Directorio por defecto para guardar audios
DEFAULT_AUDIO_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../storage/audio")
)
os.makedirs(DEFAULT_AUDIO_DIR, exist_ok=True)


async def generate_tts(
    video_id: int,
    text: str,
    output_dir: str | None = None,
    voice_id: str | None = None,
    model_id: str = "eleven_multilingual_v2",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
) -> str:
    """
    Genera audio con ElevenLabs TTS y lo guarda localmente.

    Args:
        video_id: ID del video (para nombrar el archivo).
        text: Texto completo a sintetizar.
        output_dir: Directorio de salida. Si es None, usa el default.
        voice_id: ID de la voz. Si es None, usa la variable de entorno.
        model_id: Modelo de ElevenLabs a usar.
        stability: Parámetro de estabilidad de la voz (0.0 - 1.0).
        similarity_boost: Parámetro de similitud (0.0 - 1.0).

    Returns:
        Ruta absoluta al archivo de audio generado (.mp3).
    """
    save_dir = output_dir or DEFAULT_AUDIO_DIR
    os.makedirs(save_dir, exist_ok=True)
    audio_path = os.path.join(save_dir, f"{video_id}.mp3")

    if not ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY no está configurada en las variables de entorno.")

    resolved_voice_id = voice_id or ELEVENLABS_VOICE_ID
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{resolved_voice_id}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY or "",
    }

    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
        },
    }

    logger.info(f"[TTS] Generando audio para video {video_id} ({len(text)} chars)")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=60.0)
            if response.status_code != 200:
                logger.error(f"[TTS] Error de ElevenLabs ({response.status_code}): {response.text}")
            response.raise_for_status()

            with open(audio_path, "wb") as f:
                f.write(response.content)

            logger.info(f"[TTS] Audio guardado en: {audio_path}")
            return audio_path

        except Exception as e:
            logger.error(f"[TTS] Error generando audio con ElevenLabs: {e}")
            raise


async def generate_tts_with_timestamps(
    video_id: int,
    text: str,
    output_dir: str | None = None,
    voice_id: str | None = None,
    model_id: str = "eleven_multilingual_v2",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
) -> tuple[str, list[dict]]:
    """
    Genera audio con ElevenLabs TTS incluyendo timestamps por caracter/palabra.
    Usa el endpoint 'with-timestamps' para obtener alineación temporal.

    Returns:
        Tupla de (ruta_audio, lista_de_timestamps).
        Cada timestamp es: {"word": str, "start": float, "end": float}
    """
    save_dir = output_dir or DEFAULT_AUDIO_DIR
    os.makedirs(save_dir, exist_ok=True)
    audio_path = os.path.join(save_dir, f"{video_id}.mp3")

    if not ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY no está configurada.")

    resolved_voice_id = voice_id or ELEVENLABS_VOICE_ID
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{resolved_voice_id}/with-timestamps"

    headers = {
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY or "",
    }

    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
        },
    }

    logger.info(f"[TTS+Timestamps] Generando audio con timestamps para video {video_id}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=60.0)
            if response.status_code != 200:
                logger.error(f"[TTS+Timestamps] Error ({response.status_code}): {response.text}")
            response.raise_for_status()

            data = response.json()

            # Decodificar el audio base64 y guardarlo
            import base64
            audio_bytes = base64.b64decode(data["audio_base64"])
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)

            # Procesar la alineación de caracteres en timestamps por palabra
            alignment = data.get("alignment", {})
            characters = alignment.get("characters", [])
            char_start_times = alignment.get("character_start_times_seconds", [])
            char_end_times = alignment.get("character_end_times_seconds", [])

            word_timestamps = _chars_to_word_timestamps(
                characters, char_start_times, char_end_times
            )

            logger.info(
                f"[TTS+Timestamps] Audio guardado: {audio_path} | "
                f"{len(word_timestamps)} palabras detectadas"
            )
            return audio_path, word_timestamps

        except Exception as e:
            logger.error(f"[TTS+Timestamps] Error: {e}")
            raise


def _chars_to_word_timestamps(
    characters: list[str],
    start_times: list[float],
    end_times: list[float],
) -> list[dict]:
    """
    Convierte la alineación caracter-por-caracter de ElevenLabs
    en timestamps por palabra.

    Returns:
        Lista de dicts: [{"word": "Hola", "start": 0.0, "end": 0.35}, ...]
    """
    if not characters or not start_times or not end_times:
        return []

    words = []
    current_word_chars = []
    word_start = None

    for i, char in enumerate(characters):
        if char == " " or char == "\n":
            # Fin de una palabra
            if current_word_chars:
                words.append({
                    "word": "".join(current_word_chars),
                    "start": word_start,
                    "end": end_times[i - 1] if i > 0 else 0.0,
                })
                current_word_chars = []
                word_start = None
        else:
            if word_start is None:
                word_start = start_times[i]
            current_word_chars.append(char)

    # Última palabra (si no terminó en espacio)
    if current_word_chars:
        words.append({
            "word": "".join(current_word_chars),
            "start": word_start,
            "end": end_times[-1] if end_times else 0.0,
        })

    return words
