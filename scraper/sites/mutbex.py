"""
Mutbex scraper for HorecaMark.

Site: https://www.mutbex.com
Platform: Shopify

Strategy:
- Try Shopify /collections/all/products.json first
- Parse product objects from JSON (easier than HTML)
- Fallback to HTML scraping if JSON unavailable
"""

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


class MutbexScraper(BaseScraper):
    """Scraper for Mutbex - Shopify platform.

    Uses Shopify JSON API for efficient product retrieval.
    """

    # Shopify endpoints
    SHOPIFY_COLLECTIONS_URL = "/collections/all/products.json"
    SHOPIFY_PRODUCTS_URL = "/products.json"

    # Shopify max products per request
    SHOPIFY_MAX_PRODUCTS = 250

    def __init__(self):
        """Initialize Mutbex scraper with site configuration."""
        config_dict = SITE_CONFIGS["mutbex"]
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

    async def _try_shopify_api(self) -> list[ProductData]:
        """Try fetching products via Shopify collections JSON API.

        Returns:
            List of ProductData objects, empty list if API unavailable
        """
        if not self._http_client:
            return []

        products = []

        # Try collections endpoint first, then products
        endpoints = [self.SHOPIFY_COLLECTIONS_URL, self.SHOPIFY_PRODUCTS_URL]

        for endpoint in endpoints:
            try:
                self.logger.info(f"Trying Shopify API: {endpoint}")

                response = await self._http_client.get(
                    endpoint,
                    params={"limit": self.SHOPIFY_MAX_PRODUCTS}
                )
                response.raise_for_status()

                data = response.json()
                product_list = data.get("products", [])

                if not product_list:
                    continue

                for item in product_list:
                    product = self._parse_shopify_product(item)
                    if product and self.validate_product(product):
                        products.append(product)

                if products:
                    self.logger.info(f"Shopify API returned {len(products)} products")
                    return products

            except HttpxError as e:
                self.logger.debug(f"Endpoint {endpoint} failed: {e}")
                continue

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

            # Extract price from first available variant
            variants = item.get("variants", [])
            price = Decimal("0")
            stock_status = "unknown"

            if variants:
                # Find first available variant
                for variant in variants:
                    available = variant.get("available", False)
                    price_val = variant.get("price", "0")

                    try:
                        price = Decimal(str(price_val))
                    except (ValueError, TypeError):
                        price = Decimal("0")

                    if available:
                        stock_status = "in_stock"
                        break
                else:
                    # No available variant found
                    stock_status = "out_of_stock"
                    if variants:
                        price_val = variants[0].get("price", "0")
                        try:
                            price = Decimal(str(price_val))
                        except (ValueError, TypeError):
                            pass

            # Extract URL from handle
            handle = item.get("handle", "")
            url = None
            if handle:
                url = self._build_url(f"/products/{handle}")

            # Extract vendor as brand
            brand = item.get("vendor")
            if not brand:
                brand = extract_brand(name)

            # Extract product type as category
            category = item.get("product_type")
            if not category:
                # Try to get first tag
                tags = item.get("tags", "")
                if tags:
                    category = tags.split(",")[0].strip() or None

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
        """Parse product from Mutbex HTML element (fallback).

        Args:
            element: Playwright ElementHandle for product container

        Returns:
            ProductData if parsing successful
        """
        try:
            # Extract name
            name_selectors = [
                ".title",
                ".product-title",
                "h3",
                ".product-card h3",
            ]
            name = None
            for selector in name_selectors:
                name_el = await element.query_selector(selector)
                if name_el:
                    name = (await name_el.text_content() or "").strip()
                    if name:
                        break

            if not name:
                # Fallback to link
                link_el = await element.query_selector("a[href*='/products/']")
                if link_el:
                    name = (await link_el.get_attribute("title") or "").strip()
                    if not name:
                        name = (await link_el.text_content() or "").strip()

            if not name:
                return None

            # Extract price
            price = Decimal("0")
            price_selectors = [
                ".price",
                ".money",
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
            stock_el = await element.query_selector(".stock-badge, .availability, .sold-out")
            if stock_el:
                stock_text = await stock_el.text_content()
                stock_status = normalize_stock_status(stock_text or "")
                # Check for "sold out" or "tukendi"
                if "sold" in stock_text.lower() or "tukend" in stock_text.lower():
                    stock_status = "out_of_stock"

            # Extract category
            category_el = await element.query_selector(".product-type, .product-category")
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

    async def _scrape_html(self) -> list[ProductData]:
        """Scrape products from HTML (fallback method).

        Returns:
            List of ProductData objects
        """
        url = self._build_url("/collections/all")
        self.logger.info(f"Scraping Mutbex HTML: {url}")

        await self._navigate_with_retry(url)

        # Wait for products
        try:
            await self._wait_for_selector(self.config.selectors["product"], timeout=10000)
        except ParseError:
            self.logger.warning("No products found")
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
        """Scrape all products from Mutbex.

        Tries Shopify JSON API first, falls back to HTML scraping.

        Args:
            category: Not used for Mutbex (all products in /collections/all)

        Returns:
            List of ProductData objects
        """
        # First try Shopify API
        products = await self._try_shopify_api()

        if products:
            self.logger.info(f"Got {len(products)} products from Shopify API")
            return products

        # Fallback to HTML scraping
        self.logger.info("Shopify API unavailable, falling back to HTML scraping")
        products = await self._scrape_html()

        self.logger.info(f"Total products from Mutbex: {len(products)}")
        return products


def create_scraper() -> MutbexScraper:
    """Factory function to create Mutbex scraper instance."""
    return MutbexScraper()
