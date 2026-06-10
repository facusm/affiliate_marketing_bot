from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.database.models import Product, ContentStatus
from app.scraper.meli_scraper import scrape_mercadolibre_product

router = APIRouter(prefix="/scraper", tags=["Scraper"])

class ScraperRequest(BaseModel):
    url: str

@router.post("/run")
async def run_scraper(request: ScraperRequest, db: Session = Depends(get_db)):
    try:
        # 1. Ejecutar el scraper
        scraped_data = await scrape_mercadolibre_product(request.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante el scraping: {str(e)}")

    # 2. Guardar o actualizar en base de datos
    product = db.query(Product).filter(Product.url == request.url).first()
    
    if not product:
        product = Product(url=request.url)
        db.add(product)
        
    product.title = scraped_data.get("title")
    product.price = scraped_data.get("price")
    product.features = scraped_data.get("features")
    product.image_url = scraped_data.get("image_url")
    product.rating = scraped_data.get("rating")
    product.reviews_count = scraped_data.get("reviews_count")
    product.status = ContentStatus.SCRAPED
    
    db.commit()
    db.refresh(product)
    
    return {
        "status": "success", 
        "module": "scraper", 
        "product_id": product.id,
        "message": "Producto escrapeado exitosamente",
        "data": {
            "title": product.title,
            "price": product.price,
            "image_url": product.image_url,
            "features": product.features,
            "rating": product.rating,
            "reviews_count": product.reviews_count
        }
    }
