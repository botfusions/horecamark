"""
HorecaMark scraper for HorecaMark.

Site: https://www.horecamark.com
Platform: WooCommerce (own company - baseline site)

NOTE: This is a reference scraper for the company's own site.
For production use, prefer CSV/XML export or WooCommerce REST API
rather than scraping.

This scraper is useful for:
- Price comparison verification
- Testing data normalization
- Baseline product catalog validation
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


class HorecaMarkScraper(BaseScraper):
    """Scraper for HorecaMark - company's own WooCommerce site.

    This is the baseline scraper for comparison with competitor sites.
    Prefers API methods over scraping when available.
    """

    # WooCommerce API endpoint
    WC_API_URL = "/wp-json/wc/v3/products"
    WC_API_PER_PAGE = 100

    # Pagination settings
    MAX_API_PAGES = 20

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """Initialize HorecaMark scraper.

        Args:
            api_key: WooCommerce API key (Consumer Key)
            api_secret: WooCommerce API secret (Consumer Secret)
        """
        config_dict = SITE_CONFIGS["horecamark"]
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
        self._api_key = api_key
        self._api_secret = api_secret

    async def __aenter__(self):
        """Initialize browser and HTTP client."""
        await super().__aenter__()

        # Set up HTTP client with optional auth
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }

        auth = None
        if self._api_key and self._api_secret:
            # Use HTTP Basic Auth for WooCommerce API
            auth = (self._api_key, self._api_secret)
            headers["Authorization"] = f"Basic {self._api_key}:{self._api_secret}"

        self._http_client = AsyncClient(
            base_url=self.config.base_url,
            headers=headers,
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close browser and HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
        await super().__aexit__(exc_type, exc_val, exc_tb)

    def _build_category_url(self, category: Optional[str]) -> str:
        """Build category URL.

        Args:
            category: Category slug

        Returns:
            Full category URL
        """
        if category:
            return self._build_url(f"/product-category/{category}")
        return self._build_url("/shop")

    async def _try_wc_api(self) -> list[ProductData]:
        """Try fetching products via WooCommerce REST API.

        Requires API credentials for full access.

        Returns:
            List of ProductData objects, empty list if API unavailable
        """
        if not self._http_client:
            return []

        products = []
        page = 1

        try:
            while page <= self.MAX_API_PAGES:
                params = {
                    "per_page": self.WC_API_PER_PAGE,
                    "page": page,
                    "status": "publish",
                }

                self.logger.info(f"Fetching WC API page {page}")

                response = await self._http_client.get(self.WC_API_URL, params=params)

                # Check if we got valid response
                if response.status_code == 401:
                    self.logger.warning("WC API authentication required")
                    break
                if response.status_code == 404:
                    self.logger.info("WC API endpoint not found")
                    break

                response.raise_for_status()

                data = response.json()

                if not data:
                    break

                # Parse products
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
            self.logger.info(f"WC API request failed: {e}")
            return []

        except Exception as e:
            self.logger.warning(f"WC API error: {e}")
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

            # Extract price
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

            # Use brand attribute if available
            attributes = item.get("attributes", [])
            brand = None
            for attr in attributes:
                if attr.get("name") in ["marka", "brand", "Marka", "Brand"]:
                    options = attr.get("options", [])
                    if options:
                        brand = options[0]
                        break

            if not brand:
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
        """Parse product from HTML (fallback).

        Args:
            element: Playwright ElementHandle for product container

        Returns:
            ProductData if parsing successful
        """
        try:
            # Extract name
            name_selectors = [
                "h2.woocommerce-loop-product__title",
                ".title",
                ".product-title",
                "h2",
                "h3",
            ]
            name = None
            for selector in name_selectors:
                name_el = await element.query_selector(selector)
                if name_el:
                    name = (await name_el.text_content() or "").strip()
                    if name:
                        break

            if not name:
                return None

            # Extract price
            price = Decimal("0")
            price_el = await element.query_selector(".price, .amount, .woocommerce-Price-amount")
            if price_el:
                price_text = await price_el.text_content()
                if price_text:
                    price_float = clean_price(price_text)
                    if price_float:
                        price = Decimal(str(price_float))

            # Extract URL
            url = None
            link_el = await element.query_selector("a.woocommerce-LoopProduct-link, a")
            if link_el:
                href = await link_el.get_attribute("href")
                if href:
                    url = href if href.startswith("http") else self._build_url(href)

            # Extract stock status
            stock_status = "in_stock"  # Default
            stock_el = await element.query_selector(".stock, .availability")
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
        """Scrape products from HTML (fallback).

        Args:
            category: Optional category filter

        Returns:
            List of ProductData objects
        """
        url = self._build_category_url(category)
        self.logger.info(f"Scraping HorecaMark HTML: {url}")

        await self._navigate_with_retry(url)

        # Wait for products
        try:
            await self._wait_for_selector(self.config.selectors["product"], timeout=10000)
        except ParseError:
            self.logger.warning("No products found")
            return []

        # Get product elements
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
        """Scrape all products from HorecaMark.

        For production, prefer CSV export or API.

        Args:
            category: Optional category filter

        Returns:
            List of ProductData objects
        """
        # Try WC API first
        products = await self._try_wc_api()

        if products:
            self.logger.info(f"Got {len(products)} products from WC API")
            return products

        # Fallback to HTML scraping
        self.logger.info("WC API unavailable, falling back to HTML scraping")
        products = await self._scrape_html(category)

        self.logger.info(f"Total products from HorecaMark: {len(products)}")
        return products


def create_scraper(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None
) -> HorecaMarkScraper:
    """Factory function to create HorecaMark scraper instance.

    Args:
        api_key: WooCommerce API key (Consumer Key)
        api_secret: WooCommerce API secret (Consumer Secret)

    Returns:
        HorecaMarkScraper instance
    """
    return HorecaMarkScraper(api_key=api_key, api_secret=api_secret)
