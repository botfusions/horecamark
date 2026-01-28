"""
KariyerMutfak scraper for HorecaMark.

Site: https://www.kariyermutfak.com
Platform: Custom Turkish software

Strategy:
- Use sitemap.xml for category URLs
- Classic pagination: ?page=2, ?p=3
- Selectors: .product, .urun-kart
"""

import re
import xml.etree.ElementTree as ET
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


class KariyerMutfakScraper(BaseScraper):
    """Scraper for KariyerMutfak - custom Turkish platform.

    Uses sitemap for category discovery and classic pagination.
    """

    # Sitemap and pagination settings
    SITEMAP_URL = "/sitemap.xml"
    MAX_PAGES = 15
    PAGINATION_PARAMS = ["page", "p", "sayfa"]

    def __init__(self):
        """Initialize KariyerMutfak scraper with site configuration."""
        config_dict = SITE_CONFIGS["kariyermutfak"]
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
        self._categories: Optional[list[str]] = None

    async def __aenter__(self):
        """Initialize browser and HTTP client."""
        await super().__aenter__()
        self._http_client = AsyncClient(
            base_url=self.config.base_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/xml, text/xml",
            },
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close browser and HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _fetch_sitemap_categories(self) -> list[str]:
        """Fetch category URLs from sitemap.xml.

        Returns:
            List of category URL paths
        """
        if self._categories is not None:
            return self._categories

        self._categories = []
        category_patterns = [
            r"/kategori/.*",
            r"/kategori/.*",
            r"/category/.*",
        ]

        try:
            if not self._http_client:
                return []

            self.logger.info(f"Fetching sitemap: {self.SITEMAP_URL}")
            response = await self._http_client.get(self.SITEMAP_URL)
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.content)

            # Extract URLs
            namespaces = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = [
                elem.text
                for elem in root.findall(".//ns:loc", namespaces)
                if elem.text
            ]

            # Filter for category URLs
            for url in urls:
                for pattern in category_patterns:
                    if re.search(pattern, url):
                        path = url.replace(self.config.base_url, "")
                        if path not in self._categories:
                            self._categories.append(path)
                        break

            self.logger.info(f"Found {len(self._categories)} categories in sitemap")

            # If no categories found, use defaults
            if not self._categories:
                self._categories = [""]  # Empty = homepage/shop

        except Exception as e:
            self.logger.warning(f"Failed to parse sitemap: {e}")
            self._categories = [""]

        return self._categories

    def _build_category_url(self, category: Optional[str], page: int = 1) -> str:
        """Build paginated category URL.

        Args:
            category: Category path
            page: Page number

        Returns:
            Full URL with pagination
        """
        if category:
            base_url = self._build_url(category)
        else:
            base_url = self._build_url("/")

        if page > 1:
            # Try different pagination params
            for param in self.PAGINATION_PARAMS:
                return f"{base_url}?{param}={page}"

        return base_url

    async def _detect_pagination_param(self, base_url: str) -> Optional[str]:
        """Detect which pagination parameter the site uses.

        Args:
            base_url: Base category URL

        Returns:
            Pagination parameter name or None
        """
        for param in self.PAGINATION_PARAMS:
            test_url = f"{base_url}?{param}=2"
            try:
                response = await self._http_client.head(test_url)
                if response.status_code == 200:
                    self.logger.info(f"Detected pagination param: {param}")
                    return param
            except Exception:
                continue

        return None

    async def parse_product(self, element: Any) -> Optional[ProductData]:
        """Parse product from KariyerMutfak HTML element.

        Args:
            element: Playwright ElementHandle for product container

        Returns:
            ProductData if parsing successful
        """
        try:
            # Extract name
            name_selectors = [
                ".urun-baslik",
                ".product-name",
                "h3",
                ".urun-kart h3",
            ]
            name = None
            for selector in name_selectors:
                name_el = await element.query_selector(selector)
                if name_el:
                    name = (await name_el.text_content() or "").strip()
                    if name:
                        break

            if not name:
                # Try link text
                link_el = await element.query_selector("a[href]")
                if link_el:
                    name = (await link_el.text_content() or "").strip()

            if not name:
                return None

            # Extract price
            price = Decimal("0")
            price_selectors = [
                ".fiyat",
                ".price",
                ".current-price",
                ".urun-fiyat",
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
                "a.urun-link",
                ".product-link a",
                "a[href]",
            ]
            for selector in link_selectors:
                link_el = await element.query_selector(selector)
                if link_el:
                    href = await link_el.get_attribute("href")
                    if href:
                        url = href if href.startswith("http") else self._build_url(href)
                        break

            # Extract stock status
            stock_status = "unknown"
            stock_el = await element.query_selector(".stok, .stock-status")
            if stock_el:
                stock_text = await stock_el.text_content()
                stock_status = normalize_stock_status(stock_text or "")
            else:
                stock_status = "in_stock"  # Default

            # Extract category
            category_el = await element.query_selector(".kategori, .category")
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

    async def _scrape_category(self, category_path: str) -> list[ProductData]:
        """Scrape all products from a category with pagination.

        Args:
            category_path: Category URL path

        Returns:
            List of ProductData objects
        """
        products = []

        # Build base URL
        if category_path:
            base_url = self._build_url(category_path)
        else:
            base_url = self._build_url("/")

        # Detect pagination parameter
        pag_param = await self._detect_pagination_param(base_url)

        # Scrape pages
        for page in range(1, self.MAX_PAGES + 1):
            # Build URL for this page
            if page == 1:
                page_url = base_url
            elif pag_param:
                page_url = f"{base_url}?{pag_param}={page}"
            else:
                break

            self.logger.info(f"Scraping page {page}: {page_url}")

            await self._navigate_with_retry(page_url)

            # Wait for products
            try:
                await self._wait_for_selector(self.config.selectors["product"], timeout=10000)
            except ParseError:
                self.logger.info(f"No products on page {page}, stopping pagination")
                break

            # Get product elements
            product_elements = await self._page.query_all(self.config.selectors["product"])

            if not product_elements:
                self.logger.info(f"No product elements on page {page}, stopping")
                break

            # Parse products
            page_products = []
            for element in product_elements:
                product = await self.parse_product(element)
                if product and self.validate_product(product):
                    page_products.append(product)

            if not page_products:
                self.logger.info(f"No valid products on page {page}, stopping")
                break

            products.extend(page_products)
            self.logger.info(f"Page {page}: {len(page_products)} products")

            self._rate_limit()

        return products

    async def get_products(self, category: Optional[str] = None) -> list[ProductData]:
        """Scrape all products from KariyerMutfak.

        Args:
            category: Optional category path (if None, scrapes all categories)

        Returns:
            List of ProductData objects
        """
        if category:
            # Scrape specific category
            products = await self._scrape_category(category)
        else:
            # Scrape all categories from sitemap
            categories = await self._fetch_sitemap_categories()
            products = []

            for cat_path in categories:
                cat_products = await self._scrape_category(cat_path)
                products.extend(cat_products)

        self.logger.info(f"Total products from KariyerMutfak: {len(products)}")
        return products


def create_scraper() -> KariyerMutfakScraper:
    """Factory function to create KariyerMutfak scraper instance."""
    return KariyerMutfakScraper()
