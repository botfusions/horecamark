"""
AriGastro scraper for HorecaMark.

Site: https://www.arigastro.com
Platform: WooCommerce

Strategy:
- Try WooCommerce REST API first: /wp-json/wc/v3/products
- Fallback to HTML scraping with .product.type-product class
- Categories: /kategori/xxx or /product-category/xxx
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


class AriGastroScraper(BaseScraper):
    """Scraper for AriGastro - WooCommerce platform.

    Tries WooCommerce REST API first, falls back to HTML scraping.
    """

    # WooCommerce API endpoints
    WC_API_URL = "/wp-json/wc/v3/products"
    WC_API_PER_PAGE = 100

    # Pagination settings for HTML fallback
    HTML_MAX_PAGES = 10

    def __init__(self):
        """Initialize AriGastro scraper with site configuration."""
        config_dict = SITE_CONFIGS["arigastro"]
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
        """Build category URL for AriGastro.

        Args:
            category: Category slug (e.g., "bulasik-makinesi")

        Returns:
            Full category URL
        """
        if category:
            return self._build_url(f"/kategori/{category}")
        return self._build_url("/shop")

    async def _try_wc_api(self, category: Optional[str] = None) -> list[ProductData]:
        """Try fetching products via WooCommerce REST API.

        Args:
            category: Optional category filter

        Returns:
            List of ProductData objects, empty list if API unavailable
        """
        if not self._http_client:
            return []

        products = []
        page = 1

        try:
            while True:
                params = {
                    "per_page": self.WC_API_PER_PAGE,
                    "page": page,
                    "status": "publish",
                }

                if category:
                    params["category"] = category

                self.logger.info(f"Trying WC API page {page}")

                response = await self._http_client.get(self.WC_API_URL, params=params)
                response.raise_for_status()

                data = response.json()

                if not data:
                    break

                # Parse products from JSON
                for item in data:
                    product = self._parse_wc_product(item)
                    if product and self.validate_product(product):
                        products.append(product)

                # Check if we got all products
                if len(data) < self.WC_API_PER_PAGE:
                    break

                page += 1
                self._rate_limit()

            self.logger.info(f"WC API returned {len(products)} products")
            return products

        except HttpxError as e:
            self.logger.info(f"WC API not available: {e}")
            return []

        except Exception as e:
            self.logger.warning(f"WC API request failed: {e}")
            return []

    def _parse_wc_product(self, item: dict) -> Optional[ProductData]:
        """Parse product from WooCommerce API response.

        Args:
            item: Product dict from WooCommerce API

        Returns:
            ProductData if parsing successful
        """
        try:
            name = item.get("name", "")
            if not name:
                return None

            # Extract price (try regular price, then sale price)
            price_val = item.get("regular_price") or item.get("price", "0")
            try:
                price = Decimal(str(price_val))
            except (ValueError, TypeError):
                price = Decimal("0")

            # Extract URL
            url = item.get("permalink")

            # Stock status
            stock_status_raw = item.get("stock_status", "instock")
            stock_map = {
                "instock": "in_stock",
                "outofstock": "out_of_stock",
                "onbackorder": "pre_order",
            }
            stock_status = stock_map.get(stock_status_raw, "unknown")

            # Extract categories
            categories = item.get("categories", [])
            category = None
            if categories:
                category = categories[0].get("name")

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
            self.logger.warning(f"Failed to parse WC product: {e}")
            return None

    async def parse_product(self, element: Any) -> Optional[ProductData]:
        """Parse product from WooCommerce HTML element.

        Args:
            element: Playwright ElementHandle for product container

        Returns:
            ProductData if parsing successful
        """
        try:
            # Extract name - WooCommerce specific selectors
            name_selectors = [
                "h2.woocommerce-loop-product__title",
                ".product-title",
                "h3",
                ".woocommerce-loop-product__title",
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
                link_el = await element.query_selector("a[href]")
                if link_el:
                    name = (await link_el.text_content() or "").strip()

            if not name:
                return None

            # Extract price
            price = Decimal("0")
            price_selectors = [
                ".amount",
                ".price .woocommerce-Price-amount",
                ".woocommerce-Price-amount",
                ".price",
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
            link_selectors = [
                "a.woocommerce-LoopProduct-link",
                "a.product-link",
                "a",
            ]
            for selector in link_selectors:
                link_el = await element.query_selector(selector)
                if link_el:
                    href = await link_el.get_attribute("href")
                    if href:
                        url = href if href.startswith("http") else self._build_url(href)
                        break

            # Extract stock status
            stock_status = "in_stock"  # Default for WooCommerce
            stock_el = await element.query_selector(".stock-status, .availability")
            if stock_el:
                stock_text = await stock_el.text_content()
                stock_status = normalize_stock_status(stock_text or "")

            # Extract category
            category_el = await element.query_selector(".cat-name, .product-category")
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
        self.logger.info(f"Scraping AriGastro HTML: {url}")

        products = []

        for page_num in range(1, self.HTML_MAX_PAGES + 1):
            # Build paginated URL
            page_url = f"{url}?paged={page_num}" if page_num > 1 else url

            await self._navigate_with_retry(page_url)

            # Wait for products
            try:
                await self._wait_for_selector(self.config.selectors["product"], timeout=10000)
            except ParseError:
                self.logger.info(f"No products found on page {page_num}, stopping pagination")
                break

            # Get product elements
            product_elements = await self._page.query_all(self.config.selectors["product"])

            if not product_elements:
                self.logger.info(f"No product elements on page {page_num}, stopping")
                break

            # Parse products
            page_products = []
            for element in product_elements:
                product = await self.parse_product(element)
                if product and self.validate_product(product):
                    page_products.append(product)

            if not page_products:
                self.logger.info(f"No valid products parsed on page {page_num}, stopping")
                break

            products.extend(page_products)
            self.logger.info(f"Page {page_num}: {len(page_products)} products")

            self._rate_limit()

        return products

    async def get_products(self, category: Optional[str] = None) -> list[ProductData]:
        """Scrape all products from AriGastro.

        Tries WooCommerce API first, falls back to HTML scraping.

        Args:
            category: Optional category filter

        Returns:
            List of ProductData objects
        """
        # First try WooCommerce API
        products = await self._try_wc_api(category)

        if products:
            self.logger.info(f"Got {len(products)} products from WC API")
            return products

        # Fallback to HTML scraping
        self.logger.info("WC API unavailable, falling back to HTML scraping")
        products = await self._scrape_html(category)

        self.logger.info(f"Total products from AriGastro: {len(products)}")
        return products


def create_scraper() -> AriGastroScraper:
    """Factory function to create AriGastro scraper instance."""
    return AriGastroScraper()
