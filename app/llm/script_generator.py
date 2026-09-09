import os
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Instanciamos el cliente asíncrono de OpenAI
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ─── Mapeo de códigos de idioma a nombres legibles ─────────────────────────────

LANGUAGE_MAP = {
    "es": "Spanish (Spain / Castellano)",
    "es_latam": "Spanish (Argentina / Rioplatense)",
    "es_mx": "Spanish (Mexico)",
    "en": "English",
    "pt": "Portuguese (Brazil)",
    "de": "German",
    "fr": "French",
    "it": "Italian",
}

DEFAULT_LANGUAGES = ["es", "es_latam", "es_mx", "en", "pt", "de", "fr", "it"]


# ─── Modelos de Respuesta ─────────────────────────────────────────────────────

class VideoScriptResponse(BaseModel):
    hook: str = Field(description="Gancho inicial de 3 segundos, atractivo, picante y que plantee un problema.")
    body: str = Field(description="Desarrollo del video explicando la solución y beneficios del producto de forma dinámica. Debe mencionar el rating y las opiniones si están disponibles.")
    cta_keyword: str = Field(description="Palabra clave del CTA en MAYÚSCULAS, en el IDIOMA NATIVO de este guion. Debe ser corta y fácil de escribir en un comentario.")
    cta: str = Field(description="Llamado a la acción EXACTO. Debe ser: 'Comentá la palabra [cta_keyword] y te envío el link por mensaje privado' (adaptado al idioma).")
    keywords: list[str] = Field(description="Lista de 3 a 5 palabras clave en INGLÉS para buscar videos de stock en Pexels (ej: ['chopping onions', 'kitchen gadget']).")


class LangScript(BaseModel):
    """Guion de video para un idioma específico."""
    language_code: str = Field(description="Código del idioma: es, es_latam, es_mx, en, pt, de, fr, it.")
    hook: str = Field(description="Gancho inicial de 3 segundos en el idioma indicado.")
    body: str = Field(description="Desarrollo del video en el idioma indicado.")
    cta_keyword: str = Field(description="Palabra clave del CTA en MAYÚSCULAS, en el IDIOMA NATIVO de este guion (ej: OFERTA, OFFER, ANGEBOT). Debe ser corta y fácil de escribir.")
    cta: str = Field(description="Llamado a la acción adaptado culturalmente al idioma.")
    keywords: list[str] = Field(description="3-5 palabras clave en INGLÉS para Pexels (iguales para todos los idiomas).")


class MultiLangScriptResponse(BaseModel):
    """Respuesta con guiones en múltiples idiomas generados en una sola llamada."""
    scripts: list[LangScript] = Field(description="Lista de guiones, uno por cada idioma solicitado.")


# ─── Función Original (Pipeline A y retrocompatibilidad) ──────────────────────

async def generate_video_script(
    title: str,
    price: float,
    features: str,
    rating: float | None = None,
    reviews_count: int | None = None,
    language: str = "Spanish (LATAM)",
) -> VideoScriptResponse:
    """
    Genera el guion del video y las keywords usando OpenAI y Structured Outputs.
    Incluye datos de rating/opiniones para generar prueba social en el guion.
    """
    system_prompt = f"""
    Eres un experto Copywriter y estratega de contenido viral para Reels, TikTok y Shorts de YouTube, enfocado en Marketing de Afiliados con automatización de DMs por comentarios.
    Tu objetivo es crear un guion altamente retentivo y persuasivo basado en los datos de un producto.
    
    EL IDIOMA DEL GUION Y EL TEXTO DEBE SER ESTRICTAMENTE: {language}.
    
    ESTRUCTURA Y REGLAS DEL GUION:
    1. Hook (Gancho): Máximo 3 segundos. Tiene que ser disruptivo, polémico o plantear un problema muy común con el que la audiencia se identifique al instante.
    2. Body (Desarrollo): Explica cómo este producto en específico es la solución definitiva. Destaca beneficios reales y usa un tono dinámico y coloquial. Oraciones cortas. Si hay datos de rating y opiniones, NUNCA menciones el número exacto de reseñas o el rating preciso. Usa validación social relativa o rangos abstractos (ej. "miles de reseñas positivas", "uno de los mejor valorados", "con excelentes calificaciones").
    3. CTA (Llamado a la acción): El final del guion SIEMPRE debe pedir que comenten una palabra para enviarles el link por mensaje privado.
    4. Keywords Visuales: Genera palabras clave SIEMPRE EN INGLÉS que describan visualmente el problema o la solución. Se usarán para buscar clips de stock de fondo (ej: 'person tired cleaning', 'satisfying slicing').
    
    MUY IMPORTANTE: 
    - CRITICAL: The final script MUST be under 30 words in total. It must result in less than 12 seconds of spoken audio. Do not write polite intros, jump directly into the aggressive hook.
    - NO uses emojis en los campos de texto, ya que este guion será leído por una IA de Text-To-Speech (ElevenLabs).
    - La palabra clave del CTA debe ser UNA SOLA PALABRA, corta, directa y en mayúsculas.
    - EL CONTENIDO DEBE ESTAR TRADUCIDO Y ADAPTADO CULTURALMENTE AL IDIOMA: {language}.
    """

    # Construir el user prompt con datos disponibles
    rating_info = ""
    if rating is not None:
        rating_info += f"\n    Rating: {rating} estrellas"
    if reviews_count is not None:
        rating_info += f"\n    Cantidad de opiniones: {reviews_count}"
    if not rating_info:
        rating_info = "\n    Rating/opiniones: No disponibles (no los menciones en el guion)."

    user_prompt = f"""
    Producto: {title}
    Precio: ${price}{rating_info}
    Características principales:
    {features}
    """

    # Utilizamos Structured Outputs de OpenAI (parse) para garantizar el formato Pydantic
    response = await client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format=VideoScriptResponse
    )

    return response.choices[0].message.parsed


# ─── Función Multi-Idioma (Pipeline B) ────────────────────────────────────────

async def generate_multilang_scripts(
    title: str,
    price: float,
    features: str,
    rating: float | None = None,
    reviews_count: int | None = None,
    languages: list[str] | None = None,
    script_guide: str | None = None,
) -> list[LangScript]:
    """
    Genera guiones de video en múltiples idiomas en UNA SOLA llamada al LLM.
    Cada guion tiene su propia cta_keyword nativa. Las keywords de Pexels son compartidas.

    Args:
        title: Nombre del producto.
        price: Precio del producto.
        features: Características del producto.
        rating: Rating del producto (opcional).
        reviews_count: Cantidad de reseñas (opcional).
        languages: Lista de códigos de idioma (default: todos los 6).
        script_guide: Guía de guion del prompt engineer (~40 palabras) como
                      referencia de estructura y vacío de curiosidad.

    Returns:
        Lista de LangScript, uno por cada idioma solicitado.
    """
    langs = languages or DEFAULT_LANGUAGES
    lang_names = [LANGUAGE_MAP.get(code, code) for code in langs]
    lang_list_str = ", ".join(f"{code} ({name})" for code, name in zip(langs, lang_names))

    system_prompt = f"""You are an expert Copywriter and viral content strategist for Reels, TikTok and YouTube Shorts, focused on Affiliate Marketing with comment-triggered DM automation.

Your task: Given product data, generate a highly persuasive, retention-optimized video script in EACH of these languages: {lang_list_str}.

RULES FOR EVERY SCRIPT:
1. Hook (3 seconds max): Disruptive, provocative, or relatable problem statement. Adapted to the cultural tone of the language.
2. Body: Dynamic, short sentences explaining why this product is the definitive solution. If rating/reviews are available, NEVER mention the exact number of reviews or precise rating. Use relative social validation or abstract ranges (e.g., "thousands of positive reviews", "one of the top rated", "with excellent ratings").
3. CTA: MUST ask viewers to comment a keyword to receive the product link via DM. Adapt the phrasing culturally (e.g., Spanish "Comentá"/"Comenta", English "Comment", Portuguese "Comente", German "Kommentiere", French "Commente", Italian "Commenta").
4. Keywords: 3-5 English keywords for Pexels stock search. MUST be IDENTICAL across all languages.

SPANISH REGIONAL VARIANTS — FOLLOW STRICTLY:
- "es" = Spanish from Spain (Castellano peninsular). Use peninsular conjugations ("tú tienes", "vosotros"), modismos españoles ("mola", "flipar", "tío/tía"), and a tone natural for the Spanish market.
- "es_mx" = Mexican neutral Spanish. Use standard Latin American "tú" conjugations, Mexican idioms and expressions natural for Mexico ("chido", "neta", "padre"), and orient the copy to a Mexican audience shopping on Amazon México.
- "es_latam" = Argentine Rioplatense Spanish. It is MANDATORY to use voseo throughout ("vos tenés", "vos sabés", "comentá", "mirá"). Use natural Argentine modismos ("re copado", "bárbaro", "posta", "mortal"). Orient the copy to an Argentine audience that buys products with international shipping. The CTA MUST use the voseo imperative ("Comentá", "Escribí").

CRITICAL RULES:
- CRITICAL: The final script MUST be under 30 words in total. It must result in less than 12 seconds of spoken audio. Do not write polite intros, jump directly into the aggressive hook.
- REGLA ESTRICTA: NUNCA menciones el precio ni el valor monetario del producto en el guion. Tu objetivo es generar curiosidad destacando el dolor que resuelve y sus beneficios. El CTA debe invitar a comentar la palabra clave única generada para este producto (cta_keyword) para recibir el enlace.
- NO emojis in text fields (this will be read by ElevenLabs TTS).
- The cta_keyword MUST be in the NATIVE LANGUAGE of each script and in UPPERCASE. It should be a short, product-related word that feels natural to comment in that language (e.g., Spanish: OFERTA, English: OFFER, German: ANGEBOT, Portuguese: OFERTA, French: OFFRE, Italian: OFFERTA). Each language gets its OWN keyword.
- Each script must feel NATIVE to its language, not a direct translation. Adapt idioms, tone, and cultural references.
- The keywords list must be in ENGLISH and identical for all languages."""

    # Build product info
    rating_info = ""
    if rating is not None:
        rating_info += f"\nRating: {rating} stars"
    if reviews_count is not None:
        rating_info += f"\nReviews: {reviews_count}"
    if not rating_info:
        rating_info = "\nRating/reviews: Not available (do not mention in scripts)."

    # Build script guide context
    guide_context = ""
    if script_guide:
        guide_context = f"""\n\nSCRIPT GUIDE (use as structural reference, do NOT translate literally):
\"\"\"{script_guide}\"\"\"
Adapt this script's curiosity gap structure and flow for each language. Make it feel native, not translated."""

    user_prompt = f"""Product: {title}
Price: ${price}{rating_info}
Key Features:
{features}{guide_context}

Generate scripts for these languages: {lang_list_str}
Each script must feel naturally written by a native speaker of that language."""

    response = await client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format=MultiLangScriptResponse,
    )

    result = response.choices[0].message.parsed
    return result.scripts
