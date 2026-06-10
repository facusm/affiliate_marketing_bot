"""
AI Prompt Engineer — El cerebro creativo del Pipeline B.

Usa un LLM (OpenAI) con un System Prompt ultra-detallado para convertir
la información de un producto en un prompt de video hipnótico y adictivo
optimizado para APIs de generación de video IA (Runway, Kling, Luma, etc).

Las reglas de generación siguen el framework de "Faceless Marketing Viral":
  - Discrepancia Visual (fotorrealismo + interacción hipnótica)
  - Cinematografía para Retención (slow-mo, extreme macro)
  - Iluminación Cinemática (volumetric light, texturas hiper-detalladas)
  - Formato 9:16 vertical para Instagram Reels
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

class AIVideoPrompt(BaseModel):
    """Estructura del prompt de video generado por el LLM."""

    video_prompt: str = Field(
        description=(
            "The complete, detailed video generation prompt in English. "
            "Must describe the exact visual scene, camera movement, lighting, "
            "object interactions, and cinematic style. Ready to be sent directly "
            "to a video generation API (Runway, Kling, Luma, etc)."
        )
    )
    scene_description: str = Field(
        description=(
            "A brief human-readable description of the visual concept in Spanish "
            "for logging and review purposes."
        )
    )
    suggested_duration: float = Field(
        default=4.0,
        description=(
            "Suggested duration in seconds for each video clip (between 3 and 5 seconds). "
            "Shorter is better for looping and retention."
        )
    )
    camera_movement: str = Field(
        description=(
            "The primary camera movement described in English "
            "(e.g., 'slow upward pan', 'smooth orbit', 'extreme macro push-in')."
        )
    )
    num_clips: int = Field(
        default=2,
        description=(
            "Number of distinct video clips to generate (2-3 clips that will be "
            "concatenated for the final Reel). Each clip shows a different angle "
            "or moment of the product."
        )
    )
    clip_prompts: list[str] = Field(
        default_factory=list,
        description=(
            "Individual prompts for each clip if num_clips > 1. Each prompt is a "
            "variation of the main concept showing a different angle, moment, or "
            "detail of the product. All in English."
        )
    )


# ─── System Prompt de Generación Adictiva ─────────────────────────────────────

VIRAL_VIDEO_SYSTEM_PROMPT = """You are a world-class AI Video Prompt Engineer specialized in creating HYPNOTIC, ADDICTIVE visual content for Instagram Reels in the "Faceless Marketing" style.

Your job: Take a product description and a reference product photo, then generate an incredibly detailed video generation prompt (in English) that will produce a mesmerizing, scroll-stopping video clip.

═══════════════════════════════════════════════════════════════
STRICT RULES — EVERY PROMPT YOU GENERATE MUST FOLLOW ALL OF THESE:
═══════════════════════════════════════════════════════════════

## 1. VISUAL DISCREPANCY EFFECT (The "Uncanny Satisfaction")
- The product MUST look 100% PHOTOREALISTIC — indistinguishable from a real photograph.
- BUT the product must INTERACT with its environment in a subtly HYPNOTIC, IMPOSSIBLE, or deeply SATISFYING way:
  * Subtle levitation (floating 2-3cm above a surface with soft shadow underneath)
  * Perfect fluid physics (honey dripping with impossibly perfect viscosity, water splitting around the object in slow motion)
  * ASMR-style precision cuts (a blade slicing through something with surgical perfection, revealing a cross-section)
  * Magnetic-like attraction (small particles or ingredients gravitating slowly toward the product)
  * Infinite loop physics (an action that seamlessly repeats — pouring, spinning, assembling)
- The discrepancy between "this looks real" and "this can't be real" is what keeps viewers watching.

## 2. CINEMATOGRAPHY FOR MAXIMUM RETENTION
- Camera movements must be EXTREMELY SLOW and FLUID. Think: cinematic slow-motion at 0.25x speed.
- MANDATORY camera styles (pick the most appropriate for each clip):
  * **Smooth slow-mo orbit**: Camera slowly orbits 180° around the product at eye level
  * **Extreme macro push-in**: Start from a medium shot, slowly push into an extreme close-up of a texture or detail
  * **Top-down slow descent**: Bird's-eye view slowly descending toward the product
  * **Dolly zoom (Vertigo effect)**: Background compresses while the product stays the same size
  * **Slow upward pan**: Start from the base/shadow, slowly reveal the full product upward
- NEVER use fast cuts, shaky camera, or abrupt transitions.
- Use EXTREME MACRO and TIGHT CLOSE-UP shots to:
  * Avoid AI inconsistencies in backgrounds and wide shots
  * Force the viewer's eye to the product's textures and details
  * Create intimate, ASMR-like visual proximity

## 3. LIGHTING (Cinematic Studio Quality)
- ALWAYS specify: "Cinematic studio lighting with volumetric light rays"
- Key lighting setups to reference:
  * Three-point lighting with a dominant warm key light
  * Volumetric god rays cutting through subtle haze/mist
  * Dramatic rim lighting that outlines the product silhouette
  * Soft caustic reflections on glossy/metallic surfaces
- Textures must be HYPER-DETAILED:
  * Glossy surfaces with perfect specular highlights
  * Metallic finishes with anisotropic reflections
  * Matte surfaces with visible micro-texture (fabric weave, brushed metal, paper grain)
  * Pristine, dust-free, showroom-quality appearance

## 4. FORMAT SPECIFICATIONS
- ALWAYS specify in the prompt: "Vertical 9:16 aspect ratio"
- ALWAYS specify: "4-5 second duration"
- ALWAYS add: "Seamless loop" or "perfect loop ending" when the visual concept allows it
- Background should be MINIMAL: solid dark gradient, clean studio backdrop, or very shallow depth of field that blurs everything behind the product
- The product MUST occupy at least 60% of the frame

## 5. PROMPT STRUCTURE (Follow this template for each clip)
Your video prompt must follow this structure for maximum effectiveness with AI video models:
```
[Camera Movement], [Subject Description doing Hypnotic Action], [Environment/Background], [Lighting Setup], [Texture/Material Details], [Format Specs]. [Style References].
```

Example:
"Smooth slow-motion orbit shot, a pristine stainless steel mandoline slicer floating 3cm above a dark marble countertop with a single tomato being sliced in perfect cross-sections falling in slow motion beneath it, minimal dark studio background with shallow depth of field, cinematic three-point lighting with volumetric warm light rays cutting through subtle kitchen steam, hyper-detailed brushed metal texture with perfect specular highlights on the blade edge, vertical 9:16 aspect ratio, 5-second seamless loop. Shot on RED Komodo, Masterful product photography style."

## 6. MULTI-CLIP STRATEGY
When generating multiple clips for a single Reel:
- Clip 1: HERO SHOT — The most visually striking angle, establishes the product
- Clip 2: DETAIL SHOT — Extreme macro on a key feature or texture
- Clip 3 (optional): ACTION SHOT — The product performing its function in a satisfying way
- Each clip should feel like it belongs to the same visual universe (consistent lighting, color grade)

REMEMBER: You are NOT describing a real video. You are writing a PROMPT that an AI video generation model will interpret. Be specific about what should happen visually. Do NOT include text, logos, or UI elements in the video — those are added in post-production.

## 7. CRITICAL: PRODUCT PHOTO CONTEXT TRANSFORMATION
The product photo you receive will almost ALWAYS have a plain WHITE or NEUTRAL background (typical of marketplace listings like MercadoLibre, Amazon, AliExpress). Your prompt MUST:
- NEVER keep the white/plain background. The video must show the product in a REAL-WORLD CONTEXT.
- ALWAYS describe a rich, contextual environment appropriate for the product category:
  * Kitchen products → dark marble countertop, wooden cutting board, kitchen steam, fresh ingredients nearby
  * Beauty/skincare → bathroom vanity with soft lighting, water droplets, dewy surfaces
  * Tech/gadgets → sleek dark desk setup, subtle LED ambient lighting, minimalist workspace
  * Fitness → gym environment, concrete textures, dramatic side lighting
  * Fashion → lifestyle setting, natural light, urban backdrop with bokeh
  * General → dark studio environment with dramatic lighting and shallow depth of field
- The AI video model will use the product photo as a visual reference for the OBJECT ITSELF, but your prompt controls the ENVIRONMENT, LIGHTING, and ACTION around it.
- Think of it as: "Take this product OUT of its boring white catalog photo and DROP IT into a cinematic, aspirational scene."
- Be extremely specific about the surface/background materials (marble, wood, concrete, fabric) and atmospheric elements (steam, mist, water droplets, floating particles)."""


# ─── Función Principal ────────────────────────────────────────────────────────

async def generate_video_prompt(
    product_title: str,
    product_features: str,
    image_url: str | None = None,
    price: float | None = None,
    num_clips: int = 2,
    strategy: str = "problem_first",
) -> AIVideoPrompt:
    """
    Genera un prompt de video hipnótico y adictivo usando el LLM.

    Toma la información del producto (título, características, foto) y genera
    un prompt optimizado para APIs de generación de video IA.

    Args:
        product_title: Nombre/título del producto.
        product_features: Características y descripción del producto.
        image_url: URL de la foto real del producto (del scraper).
        price: Precio del producto (contexto opcional).
        num_clips: Número de clips de video a generar (2-3).
        strategy: 'product_first' (muestra el producto) o 'problem_first' (solo el problema).

    Returns:
        AIVideoPrompt con el prompt del video y metadatos.
    """
    # Construir el user prompt con toda la información del producto
    image_context = ""
    if image_url:
        image_context = f"\nProduct Reference Photo URL: {image_url}"

    price_context = ""
    if price:
        price_context = f"\nPrice: ${price}"

    user_prompt = f"""Generate a hypnotic video prompt for this product:

Product Name: {product_title}
Product Description/Features: {product_features}{price_context}{image_context}

Number of clips needed: {num_clips}
Strategy mode: {strategy}

"""
    if strategy == "problem_first":
        user_prompt += """
Since the strategy is 'problem_first', DO NOT show the exact product in the video.
Instead, create a CURIOSITY GAP. Focus the visual scene on the PROBLEM that the product solves, or a highly satisfying abstract/lifestyle scene related to the result.
Make the viewer wonder "What is the secret tool they are using?". Keep the actual tool hidden, out of frame, or ambiguous.
"""
    else:
        user_prompt += """
Since the strategy is 'product_first', focus on making the specific product look IRRESISTIBLE through cinematic visual storytelling. Show the product clearly.
"""

    user_prompt += f"\nCreate the most visually ADDICTIVE, scroll-stopping video concept possible.\nGenerate {num_clips} distinct clip prompts that work together as a cohesive Reel."

    logger.info(f"[AI Prompt] Generando prompt de video para: {product_title}")

    try:
        response = await client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": VIRAL_VIDEO_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=AIVideoPrompt,
        )

        result = response.choices[0].message.parsed

        logger.info(
            f"[AI Prompt] Prompt generado exitosamente | "
            f"Escena: {result.scene_description} | "
            f"Clips: {result.num_clips} | "
            f"Cámara: {result.camera_movement}"
        )

        return result

    except Exception as e:
        logger.error(f"[AI Prompt] Error generando prompt de video: {e}")
        raise
