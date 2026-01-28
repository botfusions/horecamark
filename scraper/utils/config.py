"""
Configuration management for HorecaMark.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Site configurations for all Turkish e-commerce targets
SITE_CONFIGS = {
    "cafemarkt": {
        "name": "CafeMarkt",
        "base_url": "https://www.cafemarkt.com",
        "platform_type": "custom",
        "selectors": {
            "product": ".product-item, .product, .urun-karti",
            "name": "h3.product-name, .product-title, .urun-baslik, a.product-link",
            "price": ".current-price, .fiyat, .price, .money",
            "old_price": ".old-price, .eski-fiyat",
            "stock": ".stock-status, .stok-durumu",
            "url": "a.product-link, .product-link a, a",
            "category": ".category, .kategori",
        },
        "timeout": 30000,
        "rate_limit": 3.0,
        "requires_js": True,
    },
    "arigastro": {
        "name": "AriGastro",
        "base_url": "https://www.arigastro.com",
        "platform_type": "woocommerce",
        "selectors": {
            "product": ".product, .product-item, .type-product",
            "name": ".product-title, h2.woocommerce-loop-product__title, .woocommerce-loop-product__title",
            "price": ".amount, .price, .woocommerce-Price-amount",
            "old_price": ".old-price, del .amount",
            "stock": ".stock-status, .availability",
            "url": "a.woocommerce-LoopProduct-link, a.product-link",
            "category": ".cat-name, .product-category",
        },
        "timeout": 30000,
        "rate_limit": 2.5,
        "requires_js": False,
    },
    "horecamarkt": {
        "name": "HorecaMarkt",
        "base_url": "https://www.horecamarkt.com.tr",
        "platform_type": "shopify",
        "selectors": {
            "product": ".grid-item, .product-item, .product-card",
            "name": ".product-title, .product-card-title, h3 a",
            "price": ".money, .price, .product-price",
            "old_price": ".was-price, .compare-at-price",
            "stock": ".stock-badge, .availability",
            "url": "a.product-link, .product-card a",
            "category": ".product-type, .vendor",
        },
        "timeout": 35000,
        "rate_limit": 3.0,
        "requires_js": True,
    },
    "kariyermutfak": {
        "name": "KariyerMutfak",
        "base_url": "https://www.kariyermutfak.com",
        "platform_type": "custom",
        "selectors": {
            "product": ".product, .urun-kart, .product-card",
            "name": ".urun-baslik, .product-name, h3",
            "price": ".fiyat, .price, .current-price",
            "old_price": ".eski-fiyat, .old-price",
            "stock": ".stok, .stock-status",
            "url": "a.urun-link, .product-link a",
            "category": ".kategori, .category",
        },
        "timeout": 30000,
        "rate_limit": 2.0,
        "requires_js": True,
    },
    "mutbex": {
        "name": "Mutbex",
        "base_url": "https://www.mutbex.com",
        "platform_type": "shopify",
        "selectors": {
            "product": ".product, .product-item, .product-card",
            "name": ".title, .product-title, h3",
            "price": ".price, .money, .product-price",
            "old_price": ".was-price, .compare-at-price",
            "stock": ".stock-badge, .availability",
            "url": "a.product-link, .product-card a",
            "category": ".product-type, .product-category",
        },
        "timeout": 35000,
        "rate_limit": 3.0,
        "requires_js": True,
    },
    "horecamark": {
        "name": "HorecaMark",
        "base_url": "https://www.horecamark.com",
        "platform_type": "woocommerce",
        "selectors": {
            "product": ".product, .product-item, .type-product",
            "name": ".title, .product-title, h2.woocommerce-loop-product__title",
            "price": ".price, .amount, .woocommerce-Price-amount",
            "old_price": ".old-price, del .amount",
            "stock": ".stock, .availability, .stock-status",
            "url": "a.woocommerce-LoopProduct-link, a.product-link",
            "category": ".cat-name, .product-category",
        },
        "timeout": 30000,
        "rate_limit": 2.5,
        "requires_js": False,
    },
}


class Config:
    """Application configuration loaded from environment variables."""

    # Site configurations (reference to module-level constant)
    SITE_CONFIGS = SITE_CONFIGS

    # Database
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "horecemark")
    DB_USER: str = os.getenv("DB_USER", "horeca")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # SMTP Email
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "")
    EMAIL_TO: str = os.getenv("EMAIL_TO", "")

    # Scheduling
    SCRAPE_TIME: str = os.getenv("SCRAPE_TIME", "08:00")

    # Scraper settings
    SCRAPE_HEADLESS: bool = os.getenv("SCRAPE_HEADLESS", "true").lower() == "true"
    SCRAPE_TIMEOUT: int = int(os.getenv("SCRAPE_TIMEOUT", "30000"))
    PRICE_CHANGE_THRESHOLD: float = float(os.getenv("PRICE_CHANGE_THRESHOLD", "5.0"))

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    LOGS_DIR: Path = BASE_DIR / "logs"
    REPORTS_DIR: Path = BASE_DIR / "reports"

    @classmethod
    def database_url(cls) -> str:
        """Generate SQLAlchemy database URL.

        Uses DATABASE_URL if provided (Docker environment),
        otherwise constructs from individual components.
        """
        if cls.DATABASE_URL:
            return cls.DATABASE_URL
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"

    @classmethod
    def ensure_dirs(cls) -> None:
        """Ensure required directories exist."""
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        cls.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
