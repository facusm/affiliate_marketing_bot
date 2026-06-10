import os
import httpx
import logging
import asyncio
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")

# Creamos las carpetas dinámicamente si no existen
STORAGE_AUDIO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../storage/audio"))
STORAGE_VIDEO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../storage/videos"))

os.makedirs(STORAGE_AUDIO_DIR, exist_ok=True)
os.makedirs(STORAGE_VIDEO_DIR, exist_ok=True)

async def generate_audio(video_id: int, text: str) -> str:
    """
    Genera audio usando ElevenLabs REST API y lo guarda localmente.
    Se usa httpx para garantizar compatibilidad asíncrona independientemente de la versión del SDK.
    """
    audio_path = os.path.join(STORAGE_AUDIO_DIR, f"{video_id}.mp3")
    
    if not ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY no está configurada en las variables de entorno.")
        
    voice_id = ELEVENLABS_VOICE_ID
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY or ""
    }
    
    print(f"[DEBUG generate_audio] Texto a procesar: '{text[:200]}...' (largo total: {len(text)} chars)")

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)

            if response.status_code != 200:
                print(f"[DEBUG generate_audio] Error real de ElevenLabs ({response.status_code}): {response.text}")
            response.raise_for_status()

            with open(audio_path, "wb") as f:
                f.write(response.content)
            return audio_path
        except Exception as e:
            logger.error(f"Error generando audio con ElevenLabs: {e}")
            raise e

async def download_pexels_video(keyword: str, video_id: int, index: int) -> str:
    """
    Busca y descarga un video de stock vertical desde Pexels.
    """
    if not PEXELS_API_KEY:
        logger.warning("PEXELS_API_KEY no está configurada en las variables de entorno.")
        
    url = f"https://api.pexels.com/v1/videos/search?query={keyword}&orientation=portrait&per_page=1"
    headers = {"Authorization": PEXELS_API_KEY or ""}
    
    # Carpeta dedicada para este video_id
    video_dir = os.path.join(STORAGE_VIDEO_DIR, str(video_id))
    os.makedirs(video_dir, exist_ok=True)
    file_path = os.path.join(video_dir, f"clip_{index}.mp4")

    async with httpx.AsyncClient() as client:
        try:
            # 1. Buscar video en API
            response = await client.get(url, headers=headers, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("videos"):
                logger.warning(f"No se encontraron videos para la keyword: {keyword}")
                return None
                
            # 2. Obtener enlace del archivo (calidad HD si está disponible)
            video_files = data["videos"][0]["video_files"]
            video_file = next((vf for vf in video_files if vf["quality"] == "hd"), video_files[0])
            download_link = video_file["link"]
            
            # 3. Descargar el archivo de video
            async with client.stream("GET", download_link, timeout=60.0) as stream_resp:
                stream_resp.raise_for_status()
                with open(file_path, "wb") as f:
                    async for chunk in stream_resp.aiter_bytes():
                        f.write(chunk)
                        
            return file_path
        except Exception as e:
            logger.error(f"Error descargando video de Pexels para la palabra clave '{keyword}': {e}")
            raise e

async def process_media_for_video(video_id: int, full_text: str, keywords: list[str]) -> tuple[str, list[str]]:
    """
    Orquesta la generación de audio y la descarga de videos de forma concurrente (en paralelo).
    """
    # Tarea de generación de Audio
    audio_task = generate_audio(video_id, full_text)
    
    # Lista de tareas para descargas de Pexels
    video_tasks = []
    for i, keyword in enumerate(keywords, start=1):
        video_tasks.append(download_pexels_video(keyword, video_id, i))
        
    # Ejecutamos todas las tareas al mismo tiempo (asyncio.gather)
    results = await asyncio.gather(audio_task, *video_tasks, return_exceptions=False)
    
    # El primer resultado es el audio, el resto son las rutas de los videos
    audio_path = results[0]
    stock_videos_paths = [path for path in results[1:] if path is not None]
    
    return audio_path, stock_videos_paths
