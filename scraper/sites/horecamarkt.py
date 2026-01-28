"""
HorecaMarkt scraper for HorecaMark.

Site: https://www.horecamarkt.com.tr
Platform: Shopify/Custom theme

Strategy:
- Try Shopify products.json endpoint first: site.com/products.json?limit=250
- Fallback to HTML scraping with .grid-item or .product-grid-item classes
- Generic selectors: .money, .price
"""

import json
from decimal import Decimal
from typing import Any, Optional

from httpx import AsyncClient, HTTPError as HttpxError

from scraper.sites.base import (
    BaseScraper,
    ProductData,
    SiteConfig,
    ParseError,
    ScrapingError,
)
from scraper.utils.config import SITE_CONFIGS
from scraper.utils.normalizer import (
    normalize,
    extract_brand,
    clean_price,
    normalize_stock_status,
)


class HorecaMarktScraper(BaseScraper):
    """Scraper for HorecaMarkt - Shopify/Custom platform.

    Tries Shopify JSON API first, falls back to HTML scraping.
    """

    # Shopify API endpoint
    SHOPIFY_PRODUCTS_URL = "/products.json"
    SHOPIFY_MAX_PRODUCTS = 250

    def __init__(self):
        """Initialize HorecaMarkt scraper with site configuration."""
        config_dict = SITE_CONFIGS["horecamarkt"]
        self.config = SiteConfig(
            name=config_dict["name"],
            base_url=config_dict["base_url"],
            platform_type=config_dict["platform_type"],
            selectors=config_dict["selectors"],
            timeout=config_dict["timeout"],
            rate_limit=config_dict["rate_limit"],
            requires_js=config_dict["requires_js"],
        )
        super().__init__(self.config)
        self._http_client: Optional[AsyncClient] = None

    async def __aenter__(self):
        """Initialize browser and HTTP client."""
        await super().__aenter__()
        self._http_client = AsyncClient(
            base_url=self.config.base_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close browser and HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
        await super().__aexit__(exc_type, exc_val, exc_tb)

    def _build_category_url(self, category: Optional[str]) -> str:
        """Build category URL for HorecaMarkt.

        Args:
            category: Category slug or collection name

        Returns:
            Full category/collection URL
        """
        if category:
            return self._build_url(f"/collections/{category}")
        return self._build_url("/collections/all")

    async def _try_shopify_api(self, category: Optional[str] = None) -> list[ProductData]:
        """Try fetching products via Shopify products.json API.

        Args:
            category: Optional collection filter

        Returns:
            List of ProductData objects, empty list if API unavailable
        """
        if not self._http_client:
            return []

        products = []

        try:
            url = self.SHOPIFY_PRODUCTS_URL
            params = {"limit": self.SHOPIFY_MAX_PRODUCTS}

            # If category specified, try collection endpoint
            if category:
                url = f"/collections/{category}/products.json"

            self.logger.info(f"Trying Shopify API: {url}")

            response = await self._http_client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            product_list = data.get("products", [])

            for item in product_list:
                product = self._parse_shopify_product(item)
                if product and self.validate_product(product):
                    products.append(product)

            self.logger.info(f"Shopify API returned {len(products)} products")
            return products

        except HttpxError as e:
            self.logger.info(f"Shopify API not available: {e}")
            return []

        except Exception as e:
            self.logger.warning(f"Shopify API request failed: {e}")
            return []

    def _parse_shopify_product(self, item: dict) -> Optional[ProductData]:
        """Parse product from Shopify API response.

        Args:
            item: Product dict from Shopify API

        Returns:
            ProductData if parsing successful
        """
        try:
            name = item.get("title", "")
            if not name:
                return None

            # Extract price from first variant
            variants = item.get("variants", [])
            price = Decimal("0")
            stock_status = "unknown"

            if variants:
                variant = variants[0]
                price_val = variant.get("price", "0")
                try:
                    price = Decimal(str(price_val))
                except (ValueError, TypeError):
                    pass

                # Check stock availability
                available = variant.get("available")
                if available is True:
                    stock_status = "in_stock"
                elif available is False:
                    stock_status = "out_of_stock"

            # Extract URL
            handle = item.get("handle", "")
            url = self._build_url(f"/products/{handle}") if handle else None

            # Extract vendor as brand
            brand = item.get("vendor")
            if not brand:
                brand = extract_brand(name)

            # Extract product type as category
            category = item.get("product_type")
            if not category:
                category = item.get("tags", [None])[0]

            return ProductData(
                name=name,
                normalized_name=normalize(name),
                brand=brand,
                price=price,
                currency="TRY",
                stock_status=stock_status,
                url=url,
                category=category,
                site_name=self.config.name,
            )

        except Exception as e:
            self.logger.warning(f"Failed to parse Shopify product: {e}")
            return None

    async def parse_product(self, element: Any) -> Optional[ProductData]:
        """Parse product from HorecaMarkt HTML element.

        Args:
            element: Playwright ElementHandle for product container

        Returns:
            ProductData if parsing successful
        """
        try:
            # Extract name - try multiple selectors
            name_selectors = [
                ".product-title",
                ".product-card-title",
                "h3 a",
                "h3",
                ".grid-item h3",
            ]
            name = None
            for selector in name_selectors:
                name_el = await element.query_selector(selector)
                if name_el:
                    name = (await name_el.text_content() or "").strip()
                    if name:
                        break

            if not name:
                # Fallback to link text
                link_el = await element.query_selector("a[href*='/products/']")
                if link_el:
                    name = (await link_el.text_content() or "").strip()

            if not name:
                return None

            # Extract price
            price = Decimal("0")
            price_selectors = [
                ".money",
                ".price",
                ".product-price",
                ".current-price",
            ]
            for selector in price_selectors:
                price_el = await element.query_selector(selector)
                if price_el:
                    price_text = await price_el.text_content()
                    if price_text:
                        price_float = clean_price(price_text)
                        if price_float:
                            price = Decimal(str(price_float))
                            break

            # Extract URL
            url = None
            link_el = await element.query_selector("a[href*='/products/']")
            if link_el:
                href = await link_el.get_attribute("href")
                if href:
                    url = href if href.startswith("http") else self._build_url(href)

            # Extract stock status
            stock_status = "in_stock"  # Default
            stock_el = await element.query_selector(".stock-badge, .availability")
            if stock_el:
                stock_text = await stock_el.text_content()
                stock_status = normalize_stock_status(stock_text or "")

            # Extract category
            category_el = await element.query_selector(".product-type, .vendor")
            category = None
            if category_el:
                category = (await category_el.text_content() or "").strip() or None

            # Extract brand
            brand = extract_brand(name)

            return ProductData(
                name=name,
                normalized_name=normalize(name),
                brand=brand,
                price=price,
                currency="TRY",
                stock_status=stock_status,
                url=url,
                category=category,
                site_name=self.config.name,
            )

        except Exception as e:
            self.logger.warning(f"Failed to parse product: {e}")
            return None

    async def _scrape_html(self, category: Optional[str] = None) -> list[ProductData]:
        """Scrape products from HTML (fallback method).

        Args:
            category: Optional category filter

        Returns:
            List of ProductData objects
        """
        url = self._build_category_url(category)
        self.logger.info(f"Scraping HorecaMarkt HTML: {url}")

        await self._navigate_with_retry(url)

        # Wait for products
        try:
            await self._wait_for_selector(self.config.selectors["product"], timeout=10000)
        except ParseError:
            self.logger.warning("No products found, trying alternative selectors")
            return []

        # Get all product elements
        product_elements = await self._page.query_all(self.config.selectors["product"])
        self.logger.info(f"Found {len(product_elements)} product elements")

        # Parse products
        products = []
        for element in product_elements:
            product = await self.parse_product(element)
            if product and self.validate_product(product):
                products.append(product)

        return products

    async def get_products(self, category: Optional[str] = None) -> list[ProductData]:
        """Scrape all products from HorecaMarkt.

        Tries Shopify API first, falls back to HTML scraping.

        Args:
            category: Optional category/collection filter

        Returns:
            List of ProductData objects
        """
        # First try Shopify API
        products = await self._try_shopify_api(category)

        if products:
            self.logger.info(f"Got {len(products)} products from Shopify API")
            return products

        # Fallback to HTML scraping
        self.logger.info("Shopify API unavailable, falling back to HTML scraping")
        products = await self._scrape_html(category)

        self.logger.info(f"Total products from HorecaMarkt: {len(products)}")
        return products


def create_scraper() -> HorecaMarktScraper:
    """Factory function to create HorecaMarkt scraper instance."""
    return HorecaMarktScraper()
