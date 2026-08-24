from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, Enum, DateTime
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class ContentStatus(enum.Enum):
    PENDING = "pending"
    SCRAPED = "scraped"
    SCRIPT_GENERATED = "script_generated"
    MEDIA_DOWNLOADED = "media_downloaded"
    RENDERED = "rendered"
    PUBLISHED = "published"
    ERROR = "error"

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    features = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    reviews_count = Column(Integer, nullable=True)
    status = Column(Enum(ContentStatus), default=ContentStatus.PENDING)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to videos
    videos = relationship("Video", back_populates="product", cascade="all, delete-orphan")


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    # LLM Generated Content
    hook = Column(Text, nullable=True)
    script = Column(Text, nullable=True)
    call_to_action = Column(Text, nullable=True)
    cta_keyword = Column(String, nullable=True)
    keywords = Column(Text, nullable=True) # JSON string or comma-separated
    
    # Pipeline Engine & Language
    engine = Column(String, default="ai")
    language = Column(String, nullable=True)
    ai_video_prompt = Column(Text, nullable=True)  # Prompt usado para generar video IA

    # Media & Render Paths
    audio_path = Column(String, nullable=True)
    base_video_path = Column(Text, nullable=True)    # JSON string — clips IA base (mudos)
    stock_videos_paths = Column(Text, nullable=True) # JSON string of paths
    final_video_path = Column(String, nullable=True)
    
    # Meta Graph API Integration
    ig_media_id = Column(String, nullable=True)
    affiliate_url = Column(String, nullable=True)
    
    status = Column(Enum(ContentStatus), default=ContentStatus.PENDING)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to product
    product = relationship("Product", back_populates="videos")
