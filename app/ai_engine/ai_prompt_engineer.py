"""
AI Prompt Engineer — El cerebro creativo del Pipeline Híbrido I2V + T2V.

Usa un LLM (OpenAI) con un System Prompt ultra-detallado para convertir
la información de un producto en un paquete de prompts optimizado:
  - script: Guion locutado corto (~40 palabras, ~15 seg) con vacío de curiosidad.
  - b_roll_1: Prompt T2V para una escena sensorial/estética relacionada al producto.
  - b_roll_2: Prompt T2V para el producto en uso en cámara lenta (macro shot).

El clip principal (I2V) usa la foto real del producto con cámara estática;
los B-Rolls se generan con Text-to-Video para evitar deformación de píxeles
y mantener variedad visual que maximiza la retención.
"""

import os
import logging
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ─── Modelo de Respuesta Estructurada ────────────────────────────────────────

class HybridVideoPrompt(BaseModel):
    """Estructura del prompt híbrido generado por el LLM."""

    script: str = Field(
        description=(
            "Short voiceover script (~40 words, ~15 seconds of audio) in Spanish. "
            "Must open with a curiosity gap (a provocative question or problem statement) "
            "that hooks the viewer. NEVER mention the product price. "
            "Must end with a soft tease that makes the viewer want to comment for more info."
        )
    )
    b_roll_1: str = Field(
        description=(
            "English prompt for Kling AI Text-to-Video. A highly aesthetic, sensorial, "
            "or tempting cinematic scene RELATED to the product category but NOT showing "
            "the product itself. No text, no logos, no brands. "
            "Example for a coffee maker: 'Extreme close-up of golden flaky croissants "
            "being pulled apart in slow motion with steam rising, warm morning light, "
            "shallow depth of field, 9:16 vertical, cinematic.'"
        )
    )
    b_roll_2: str = Field(
        description=(
            "English prompt for Kling AI Text-to-Video. A macro/slow-motion shot showing "
            "the type of product IN USE (generic, not branded). Focus on the satisfying "
            "action or result of using the product. No text, no logos, no brands. "
            "Example for a coffee maker: 'Macro shot of dark espresso coffee pouring into "
            "a white ceramic cup in extreme slow motion, steam curling upward, "
            "cinematic studio lighting, 9:16 vertical, ultra realistic.'"
        )
    )
    scene_description: str = Field(
        description=(
            "Brief human-readable description of the overall visual concept in Spanish "
            "for logging and review purposes."
        )
    )


# ─── System Prompt de Marketing de Afiliación para Instagram ─────────────────

HYBRID_VIDEO_SYSTEM_PROMPT = """You are a world-class Instagram Reels strategist and affiliate marketing expert specialized in RETENTION OPTIMIZATION for faceless product accounts.

Your job: Given a product description and photo, generate a structured JSON response with 3 components designed to MAXIMIZE watch-time and comment-driven engagement.

═══════════════════════════════════════════════════════════════
THE HYBRID VISUAL STRATEGY (Why 3 Clips, Not 1)
═══════════════════════════════════════════════════════════════

Instagram's algorithm rewards watch-time above all. A single looping clip causes "visual fatigue" and users scroll away. Instead, we use 3 DISTINCT clips:

1. **HERO CLIP (I2V)**: The actual product photo transformed into video with a LOCKED camera. This clip will be enhanced with a slow Ken Burns zoom effect in post-production, so your prompt must describe a STATIC, locked-off composition. The product must be the clear hero.

2. **B-ROLL 1 (T2V - Sensorial/Aspirational)**: A highly aesthetic, ASMR-like, or aspirational scene that evokes the FEELING of the product category. This is NOT the product itself — it's the world around it. Think: the croissant for the coffee maker, the sunset for the sunglasses, the fresh ingredients for the kitchen gadget.

3. **B-ROLL 2 (T2V - Product-in-Use)**: A satisfying macro/slow-motion shot of the GENERIC type of product being used. Show the ACTION, the RESULT, the SATISFACTION. This creates the "I want that" moment.

═══════════════════════════════════════════════════════════════
RULES FOR THE VOICEOVER SCRIPT
═══════════════════════════════════════════════════════════════

- Language: Spanish (neutral Latin American).
- Length: MAXIMUM 30 words (~12 seconds when spoken).
- Structure: 
  * Open with a CURIOSITY GAP — a provocative question or bold claim about a common problem.
  * Bridge with the solution hint — "there's something that..." or "what if I told you..."
  * Close with a SOFT CTA tease — imply they need to comment to find out more.
- STRICT RULES:
  * CRITICAL: The final script MUST be under 30 words in total. It must result in less than 12 seconds of spoken audio. Do not write polite intros, jump directly into the aggressive hook.
  * NEVER mention the product name directly.
  * NEVER mention the price.
  * NEVER use emojis (this will be read by TTS).
  * NO hashtags, NO @ mentions.
  * Write in a conversational, fast-paced tone.

═══════════════════════════════════════════════════════════════
RULES FOR B-ROLL PROMPTS (T2V)
═══════════════════════════════════════════════════════════════

Both b_roll_1 and b_roll_2 prompts must:
- Be written in ENGLISH (this goes directly to Kling AI).
- Specify "9:16 vertical aspect ratio" and "5-second duration".
- Include "ultra realistic, cinematic lighting" quality markers.
- NEVER include text, logos, brand names, or UI elements.
- NEVER include humans with visible faces (faceless content only).
- Describe SPECIFIC textures, materials, and atmospheric elements.
- Use terms like: "extreme close-up", "macro shot", "slow motion", "shallow depth of field", "cinematic studio lighting", "volumetric light".

REMEMBER: You are writing PROMPTS for an AI video model, not describing a real video. Be ultra-specific about what should appear visually."""


# ─── Función Principal ────────────────────────────────────────────────────────

async def generate_video_prompt(
    product_title: str,
    product_features: str,
    image_url: str | None = None,
    price: float | None = None,
    **kwargs,
) -> HybridVideoPrompt:
    """
    Genera un paquete de prompts híbrido (script + 2 B-Rolls) usando el LLM.

    Toma la información del producto y genera:
    - Un guion locutado corto con vacío de curiosidad (~40 palabras).
    - Dos prompts de B-Roll para Text-to-Video en Kling AI.

    Args:
        product_title: Nombre/título del producto.
        product_features: Características y descripción del producto.
        image_url: URL de la foto real del producto (para contexto).
        price: Precio del producto (contexto, pero el LLM tiene prohibido mencionarlo).

    Returns:
        HybridVideoPrompt con script, b_roll_1, b_roll_2 y scene_description.
    """
    image_context = ""
    if image_url:
        image_context = f"\nProduct Reference Photo: {image_url}"

    price_context = ""
    if price:
        price_context = f"\nPrice (DO NOT mention in script): ${price}"

    user_prompt = f"""Generate a hybrid video prompt package for this product:

Product Name: {product_title}
Product Description/Features: {product_features}{price_context}{image_context}

Create the most ADDICTIVE, scroll-stopping combination of:
1. A short voiceover script (~40 words) with a curiosity gap
2. A sensorial/aspirational B-Roll scene (b_roll_1)
3. A product-in-use macro shot B-Roll scene (b_roll_2)
"""

    logger.info(f"[AI Prompt] Generando prompt híbrido para: {product_title}")

    try:
        response = await client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": HYBRID_VIDEO_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=HybridVideoPrompt,
        )

        result = response.choices[0].message.parsed

        logger.info(
            f"[AI Prompt] Prompt híbrido generado | "
            f"Escena: {result.scene_description} | "
            f"Script ({len(result.script.split())} palabras)"
        )

        return result

    except Exception as e:
        logger.error(f"[AI Prompt] Error generando prompt híbrido: {e}")
        raise
