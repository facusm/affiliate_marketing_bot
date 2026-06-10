import httpx
import re
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}
r = httpx.get("https://www.mercadolibre.com.ar/mandolina-filoshark-premium-picadora-verdura-rallador-color-blanco/p/MLA45717903", headers=headers, follow_redirects=True)

print(f"Status: {r.status_code}")
print(f"URL final: {r.url}")

soup = BeautifulSoup(r.text, "html.parser")
print(f"Title tag: {soup.title.string if soup.title else 'NONE'}")

og_title = soup.find("meta", attrs={"property": "og:title"})
print(f"OG Title: {og_title.get('content') if og_title else 'NONE'}")

og_image = soup.find("meta", attrs={"property": "og:image"})
print(f"OG Image: {og_image.get('content')[:100] if og_image else 'NONE'}")

meta_desc = soup.find("meta", attrs={"name": "description"})
print(f"Meta Desc: {meta_desc.get('content')[:100] if meta_desc else 'NONE'}")

has_captcha = "/captcha/" in str(r.url) or "captcha" in r.text.lower()[:3000]
print(f"Captcha en URL o body: {has_captcha}")

body_text = soup.get_text()[:500]
print(f"\nBody text (500 chars):\n{body_text}")
