"""
Webhook Router — Recepción de eventos de Instagram y respuesta automática por DM.

Flujo:
  1. Meta envía un evento de comentario a POST /webhook
  2. Se limpia el texto del comentario y se busca en la tabla Video.cta_keyword
  3. Si hay match, se envía un DM con el affiliate_url del producto asociado
  4. El mensaje DM se adapta al idioma del video que matcheó

El affiliate_url viene de Video.affiliate_url (puede agregarse después via PATCH o la UI).
"""

import os
import string
import logging
import httpx
from fastapi import APIRouter, Request, Response, BackgroundTasks, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db, SessionLocal
from app.database.models import Video, Product
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhook"])

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")

# ─── Templates de DM por Idioma ───────────────────────────────────────────────
# Cada idioma tiene su propio mensaje de DM adaptado culturalmente.

DM_TEMPLATES: dict[str, str] = {
    "es": "¡Hola! Aquí tienes el link que pediste: {url}",
    "en": "Hey! Here's the link you requested: {url}",
    "pt": "Olá! Aqui está o link que você pediu: {url}",
    "de": "Hallo! Hier ist der Link, den du angefordert hast: {url}",
    "fr": "Salut ! Voici le lien que tu as demandé : {url}",
    "it": "Ciao! Ecco il link che hai richiesto: {url}",
}

# Fallback genérico si el idioma no está mapeado
DM_TEMPLATE_FALLBACK = "Here's the link you requested: {url}"

# ─── Universal Purchase Intents por Idioma ────────────────────────────────────
UNIVERSAL_INTENTS = {
    "es": ["precio", "info", "quiero", "link"],
    "en": ["price", "info", "want", "link"],
    "pt": ["preço", "info", "quero", "link"],
    "de": ["preis", "info", "will", "link"],
    "fr": ["prix", "info", "veux", "lien"],
    "it": ["prezzo", "info", "voglio", "link"],
}

# ─── Respuestas Públicas Automáticas por Idioma ───────────────────────────────
PUBLIC_REPLIES = {
    "es": "¡Te envié el link por privado! 🚀",
    "en": "I sent you the link via DM! 🚀",
    "pt": "Te enviei o link por mensagem privada! 🚀",
    "de": "Ich habe dir den Link per DM geschickt! 🚀",
    "fr": "Je t'ai envoyé le lien en privé ! 🚀",
    "it": "Ti ho inviato il link in privato! 🚀",
}
PUBLIC_REPLY_FALLBACK = "I sent you the link via DM! 🚀"


# ─── 1. Verificación del Webhook (GET) ────────────────────────────────────────

@router.get("")
async def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Endpoint requerido por Meta para validar la conexión del Webhook.
    Meta envía un GET con hub.mode, hub.verify_token y hub.challenge.
    """
    if mode and token:
        if mode == "subscribe" and token == META_VERIFY_TOKEN:
            logger.info("WEBHOOK_VERIFIED")
            # Meta exige que se devuelva el challenge como texto plano (entero)
            return Response(content=challenge, status_code=200)
        else:
            raise HTTPException(status_code=403, detail="Forbidden: Token mismatch")
    raise HTTPException(status_code=400, detail="Bad Request: Missing parameters")


# ─── 2. Lógica de Respuesta Asíncrona (Background Task) ───────────────────────

async def process_instagram_comment(comment_text: str, comment_id: str, media_id: str, ig_account_id: str):
    """
    Procesa el comentario, busca coincidencia en DB por ig_media_id y envía el DM con el affiliate link.
    Corre en background para no bloquear el retorno HTTP 200 a Meta.
    """
    if not META_ACCESS_TOKEN or not ig_account_id:
        logger.error("[Webhook] Faltan variables de Meta (Token) o account_id.")
        return

    # 1. Limpiar el texto: quitar puntuación y espacios, y pasar a mayúsculas
    # Ej: "¡oferta!  " -> "OFERTA"
    clean_text = comment_text.translate(str.maketrans('', '', string.punctuation)).strip().upper()
    
    if not clean_text:
        return

    logger.info(f"[Webhook] Comentario recibido y limpiado: '{clean_text}' (ID: {comment_id})")

    # 2. Consultar base de datos
    db: Session = SessionLocal()
    try:
        # Buscar el Video por ig_media_id
        video = db.query(Video).filter(Video.ig_media_id == media_id).first()
        
        if not video:
            logger.info(f"[Webhook] No hay video registrado para media_id: {media_id}")
            return
            
        lang_code = video.language or "es"
        
        # Verificar que el comentario contenga la palabra clave correcta o intent universal
        cta_keyword = video.cta_keyword.upper() if video.cta_keyword else ""
        intents = [intent.upper() for intent in UNIVERSAL_INTENTS.get(lang_code, [])]
        
        is_match = False
        if cta_keyword and cta_keyword in clean_text:
            is_match = True
        elif any(intent in clean_text for intent in intents):
            is_match = True
            
        if not is_match:
            logger.info(f"[Webhook] Comentario '{clean_text}' no matchea la keyword '{cta_keyword}' ni intents universales.")
            return
            
        product = video.product
        if not product:
            logger.error(f"[Webhook] Video {video.id} encontrado pero sin producto asociado.")
            return

        # 3. Verificar que el video tenga affiliate_url configurada
        affiliate_url = video.affiliate_url
        if not affiliate_url:
            logger.info(
                f"[Webhook] Video {video.id} (Producto '{product.title}', ID: {product.id}) no tiene "
                f"affiliate_url configurada. Ignorando comentario. "
                f"Usá la UI para actualizar el link del idioma {video.language}."
            )
            return

        logger.info(
            f"[Webhook] ¡Match! Video {video.id} ({video.language}) → "
            f"Enviando affiliate link: {affiliate_url}"
        )
        
        # 4. Construir mensaje DM en el idioma del video que matcheó
        lang_code = video.language or "es"
        dm_template = DM_TEMPLATES.get(lang_code, DM_TEMPLATE_FALLBACK)
        dm_message = dm_template.format(url=affiliate_url)

        # 5. Enviar Mensaje Directo (DM) vía Meta Graph API respondiendo al comentario
        url = f"https://graph.facebook.com/v19.0/{ig_account_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "recipient": {
                "comment_id": comment_id
            },
            "message": {
                "text": dm_message
            }
        }

        # 4.5 Construir Respuesta Pública
        reply_template = PUBLIC_REPLIES.get(lang_code, PUBLIC_REPLY_FALLBACK)
        reply_url = f"https://graph.facebook.com/v19.0/{comment_id}/replies"
        reply_payload = {
            "message": reply_template
        }

        async with httpx.AsyncClient() as client:
            # Enviar Respuesta Pública
            res_reply = await client.post(reply_url, json=reply_payload, headers=headers)
            if res_reply.status_code == 200:
                logger.info(f"[Webhook] Respuesta pública enviada para el comentario {comment_id}")
            else:
                logger.error(f"[Webhook] Error enviando respuesta pública: {res_reply.text}")
                
            # Enviar DM
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info(
                    f"[Webhook] DM enviado exitosamente ({lang_code}): "
                    f"comment_id={comment_id}"
                )
            else:
                logger.error(
                    f"[Webhook] Error enviando DM ({response.status_code}): "
                    f"{response.text}"
                )
                
    except Exception as e:
        logger.error(f"[Webhook] Error procesando comentario: {e}")
    finally:
        db.close()


# ─── 3. Recepción de Eventos (POST) ───────────────────────────────────────────

@router.post("")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint donde Meta envía los eventos de Instagram (comentarios, mensajes, etc).
    """
    try:
        body = await request.json()
    except Exception:
        return Response(status_code=400)

    # Validamos que sea un evento de la plataforma correcta
    if body.get("object") == "instagram":
        entries = body.get("entry", [])
        for entry in entries:
            ig_account_id_entrante = entry.get("id")
            changes = entry.get("changes", [])
            for change in changes:
                # Nos interesan específicamente los comentarios
                if change.get("field") == "comments":
                    value = change.get("value", {})
                    comment_text = value.get("text", "")
                    comment_id = value.get("id", "")
                    media_id = value.get("media", {}).get("id", "")
                    
                    if comment_text and comment_id and media_id and ig_account_id_entrante:
                        # Delegamos el proceso lento a background para devolver 200 OK urgente
                        background_tasks.add_task(
                            process_instagram_comment, 
                            comment_text, 
                            comment_id, 
                            media_id, 
                            ig_account_id_entrante
                        )
                        
    # Meta EXIGE que devuelvas 200 OK rápido (en menos de 20s), 
    # de lo contrario asume que falló y reintenta varias veces.
    return Response(content="EVENT_RECEIVED", status_code=200)
