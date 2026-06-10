import httpx
import logging
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Headers que imitan un navegador real para evitar bloqueos
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}


async def scrape_mercadolibre_product(url: str) -> dict:
    """
    Scrapea un producto de Mercado Libre usando HTTP directo + BeautifulSoup.
    
    Extrae los datos del producto desde los meta tags del HTML (OG tags),
    que están disponibles sin necesidad de ejecutar JavaScript.
    Esto evita los captchas que MercadoLibre muestra a navegadores automatizados (Playwright).
    """
    async with httpx.AsyncClient(
        headers=_HEADERS,
        follow_redirects=True,
        timeout=20.0
    ) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP al acceder a MercadoLibre ({e.response.status_code})")
            raise ValueError(f"No se pudo acceder al producto. HTTP {e.response.status_code}.")
        except Exception as e:
            logger.error(f"Error de red al acceder a MercadoLibre: {e}")
            raise e

    # Verificar que no nos redirigió al captcha
    if "/captcha/" in str(response.url):
        raise ValueError("MercadoLibre bloqueó la solicitud con un captcha. Intentá de nuevo en unos minutos.")

    soup = BeautifulSoup(response.text, "html.parser")

    # --- Extraer Título ---
    title = None
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title:
        title = og_title.get("content")
    elif soup.title:
        title = soup.title.string

    # --- Extraer Precio ---
    price = None
    price_match = re.search(r'"price"\s*:\s*([\d.]+)', response.text)
    if price_match:
        try:
            price = float(price_match.group(1))
        except ValueError:
            pass
    if price is None:
        price_meta = soup.find("meta", attrs={"itemprop": "price"})
        if price_meta:
            try:
                price = float(price_meta["content"])
            except (ValueError, KeyError):
                pass

    # --- Extraer Imagen ---
    image_url = None
    og_image = soup.find("meta", attrs={"property": "og:image"})
    if og_image:
        image_url = og_image.get("content")

    # --- Extraer Descripción / Características ---
    features = None
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        features = meta_desc.get("content")

    # --- Extraer Rating (estrellas) ---
    rating = None
    rating_match = re.search(r'"ratingValue"\s*:\s*"?([\d.]+)"?', response.text)
    if rating_match:
        try:
            rating = float(rating_match.group(1))
        except ValueError:
            pass

    # --- Extraer Cantidad de Opiniones ---
    reviews_count = None
    reviews_match = re.search(r'"reviewCount"\s*:\s*"?(\d+)"?', response.text)
    if reviews_match:
        try:
            reviews_count = int(reviews_match.group(1))
        except ValueError:
            pass
    # Fallback: buscar en el texto visible de la página
    if reviews_count is None:
        opinions_match = re.search(r'(\d+)\s*opini', response.text)
        if opinions_match:
            try:
                reviews_count = int(opinions_match.group(1))
            except ValueError:
                pass

    return {
        "url": url,
        "title": title,
        "price": price,
        "image_url": image_url,
        "features": features,
        "rating": rating,
        "reviews_count": reviews_count
    }
