"""
CafeMarkt scraper for HorecaMark.

Site: https://www.cafemarkt.com
Platform: Custom .NET/PHP with JavaScript lazy loading

Strategy:
- Infinite scroll with JavaScript-triggered lazy loading
- Scroll to load 20-30 products at a time
- Click "load more" button when present
- URL patterns: /endustriyel-[kategori], /[urun-adi]-p-[id]
"""

import asyncio
import re
from decimal import Decimal
from typing import Any, Optional

from httpx import HTTPError

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


class CafeMarktScraper(BaseScraper):
    """Scraper for CafeMarkt - custom .NET/PHP site with infinite scroll."""

    # Site-specific constants
    LOAD_MORE_SELECTOR = ".load-more, .btn-load-more, a[data-ajax=true]"
    PRODUCT_GRID_SELECTOR = ".product-grid, .product-list, .urun-listesi"
    INFINITE_SCROLL_THRESHOLD = 100  # pixels from bottom

    # Maximum products to scrape per category (prevents infinite loops)
    MAX_PRODUCTS_PER_CATEGORY = 250
    SCROLL_PAUSE_TIME = 1.5  # seconds to wait after scroll
    MAX_SCROLL_ATTEMPTS = 10

    def __init__(self):
        """Initialize CafeMarkt scraper with site configuration."""
        config_dict = SITE_CONFIGS["cafemarkt"]
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

    def _build_category_url(self, category: Optional[str]) -> str:
        """Build category URL for CafeMarkt.

        Args:
            category: Category slug (e.g., "endustriyel-bulasik-makinesi")

        Returns:
            Full category URL
        """
        if category:
            return self._build_url(f"/endustriyel-{category}")
        return self._build_url("/endustriyel-urunler")

    async def _scroll_and_load_products(self) -> list[Any]:
        """Handle infinite scroll to load all products.

        Scrolls down page to trigger lazy loading, clicking "load more" if present.

        Returns:
            List of all product elements found
        """
        products = []
        scroll_attempts = 0
        last_product_count = 0

        while scroll_attempts < self.MAX_SCROLL_ATTEMPTS:
            # Check for "load more" button first
            try:
                load_more_btn = await self._page.query_selector(self.LOAD_MORE_SELECTOR)
                if load_more_btn:
                    is_visible = await load_more_btn.is_visible()
                    if is_visible:
                        self.logger.info("Clicking 'load more' button")
                        await load_more_btn.click()
                        await asyncio.sleep(self.SCROLL_PAUSE_TIME)
            except Exception:
                pass  # No load more button or not clickable

            # Scroll to bottom of page
            await self._page.evaluate(
                f"window.scrollTo(0, document.body.scrollHeight - {self.INFINITE_SCROLL_THRESHOLD})"
            )
            await asyncio.sleep(self.SCROLL_PAUSE_TIME)

            # Find all product elements
            current_products = await self._page.query_all(
                self.config.selectors["product"]
            )
            product_count = len(current_products)

            self.logger.info(f"Found {product_count} products after scroll {scroll_attempts + 1}")

            # Check if we got new products
            if product_count == last_product_count:
                # No new products, check if we should stop
                if product_count >= self.MAX_PRODUCTS_PER_CATEGORY:
                    self.logger.info(f"Reached max products limit: {self.MAX_PRODUCTS_PER_CATEGORY}")
                    break
                scroll_attempts += 1
                if scroll_attempts >= 3:
                    self.logger.info("No new products after 3 scrolls, stopping")
                    break
            else:
                scroll_attempts = 0  # Reset counter on new products
                last_product_count = product_count

                if product_count >= self.MAX_PRODUCTS_PER_CATEGORY:
                    self.logger.info(f"Reached max products limit: {self.MAX_PRODUCTS_PER_CATEGORY}")
                    break

        return await self._page.query_all(self.config.selectors["product"])

    async def _extract_product_id(self, element: Any) -> Optional[str]:
        """Extract product ID from URL or data attribute.

        CafeMarkt uses pattern: /[urun-adi]-p-[id]

        Args:
            element: Product element

        Returns:
            Product ID if found
        """
        try:
            # Try data-product-id attribute
            product_id = await element.get_attribute("data-product-id")
            if product_id:
                return product_id

            # Try extracting from URL
            link_el = await element.query_selector("a[href]")
            if link_el:
                href = await link_el.get_attribute("href")
                if href:
                    # Match pattern: -p-[digits]
                    match = re.search(r"-p-(\d+)", href)
                    if match:
                        return match.group(1)
        except Exception as e:
            self.logger.debug(f"Failed to extract product ID: {e}")

        return None

    async def parse_product(self, element: Any) -> Optional[ProductData]:
        """Parse product data from CafeMarkt product element.

        Args:
            element: Playwright ElementHandle for product container

        Returns:
            ProductData if parsing successful, None otherwise
        """
        try:
            # Extract product name
            name_el = await element.query_selector(self.config.selectors["name"])
            if not name_el:
                name_el = await element.query_selector("h3, h4, .product-title a")

            if name_el:
                name = (await name_el.text_content() or "").strip()
            else:
                # Try getting from title attribute or link text
                link_el = await element.query_selector("a[href]")
                if link_el:
                    name = (await link_el.get_attribute("title") or "").strip()
                    if not name:
                        name = (await link_el.text_content() or "").strip()
                else:
                    self.logger.debug("Could not find product name")
                    return None

            if not name:
                return None

            # Extract price
            price = Decimal("0")
            price_el = await element.query_selector(self.config.selectors["price"])
            if price_el:
                price_text = await price_el.text_content()
                if price_text:
                    price_float = clean_price(price_text)
                    if price_float:
                        price = Decimal(str(price_float))

            # Extract URL
            url = None
            link_el = await element.query_selector(self.config.selectors["url"])
            if link_el:
                href = await link_el.get_attribute("href")
                if href:
                    url = self._build_url(href) if href.startswith("/") else href

            # Extract stock status
            stock_el = await element.query_selector(self.config.selectors["stock"])
            stock_status = "unknown"
            if stock_el:
                stock_text = await stock_el.text_content()
                stock_status = normalize_stock_status(stock_text or "")
            else:
                # Assume in stock if no status shown
                stock_status = "in_stock"

            # Extract category
            category_el = await element.query_selector(self.config.selectors["category"])
            category = None
            if category_el:
                category = (await category_el.text_content() or "").strip() or None

            # Extract brand from name
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

    async def get_products(self, category: Optional[str] = None) -> list[ProductData]:
        """Scrape all products from CafeMarkt.

        Handles:
        - Category navigation
        - Infinite scroll loading
        - Product parsing

        Args:
            category: Optional category slug

        Returns:
            List of ProductData objects
        """
        url = self._build_category_url(category)
        self.logger.info(f"Scraping CafeMarkt category: {url}")

        await self._navigate_with_retry(url)

        # Wait for product grid to load
        try:
            await self._wait_for_selector(self.PRODUCT_GRID_SELECTOR, timeout=10000)
        except ParseError:
            # Try alternative selector
            await self._wait_for_selector(self.config.selectors["product"], timeout=10000)

        # Scroll to load all products
        product_elements = await self._scroll_and_load_products()
        self.logger.info(f"Found {len(product_elements)} product elements")

        # Parse each product
        products = []
        for element in product_elements:
            product = await self.parse_product(element)
            if product and self.validate_product(product):
                products.append(product)

        self.logger.info(f"Successfully parsed {len(products)} products from CafeMarkt")
        return products


def create_scraper() -> CafeMarktScraper:
    """Factory function to create CafeMarkt scraper instance."""
    return CafeMarktScraper()
