"""
Base scraper framework for HorecaMark.

Provides abstract interface and common functionality for all site scrapers.
Each site scraper inherits from BaseScraper and implements site-specific logic.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urljoin

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from scraper.utils.logger import get_logger
from scraper.utils.config import Config


@dataclass
class ProductData:
    """Normalized product data structure.

    All scrapers return this format for consistent database storage.
    """

    name: str
    normalized_name: str
    brand: Optional[str]
    price: Decimal
    currency: str
    stock_status: str
    url: Optional[str]
    category: Optional[str]
    site_name: str


@dataclass
class SiteConfig:
    """Configuration for a specific e-commerce site."""

    name: str
    base_url: str
    platform_type: str  # 'woocommerce', 'shopify', 'custom'
    selectors: dict[str, str]
    timeout: int = 30000
    user_agent: Optional[str] = None
    requires_js: bool = True
    rate_limit: float = 2.0  # seconds between requests


class ScrapingError(Exception):
    """Base exception for scraping errors."""

    def __init__(self, site: str, message: str, url: Optional[str] = None):
        self.site = site
        self.message = message
        self.url = url
        super().__init__(f"[{site}] {message}" + (f" at {url}" if url else ""))


class RateLimitError(ScrapingError):
    """Raised when rate limit is detected."""


class ParseError(ScrapingError):
    """Raised when product parsing fails."""


class BaseScraper(ABC):
    """Abstract base scraper for all e-commerce sites.

    Implements common scraping patterns:
    - Playwright browser management
    - Retry logic with exponential backoff
    - Rate limiting
    - Error handling and logging

    Subclasses must implement:
    - parse_product(): Extract product data from a page element
    - get_products(): Navigate site and yield product elements
    """

    # Default configuration (override in subclass or use SITE_CONFIGS)
    config: SiteConfig

    # Maximum retries for failed requests
    MAX_RETRIES: int = 3

    # Base delay for exponential backoff (seconds)
    BASE_RETRY_DELAY: float = 1.0

    def __init__(self, config: SiteConfig):
        """Initialize scraper with site configuration.

        Args:
            config: SiteConfig instance with site-specific settings
        """
        self.config = config
        self.logger = get_logger(f"scraper.{config.name}")

        # Browser instances (initialized in __aenter__)
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def __aenter__(self):
        """Async context manager entry - initialize browser."""
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close browser."""
        await self._close_browser()

    async def _init_browser(self) -> None:
        """Initialize Playwright browser with stealth options.

        Uses headless mode for production, configurable via environment.
        """
        playwright = await async_playwright().start()

        # Launch browser with stealth settings
        self._browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        # Create context with realistic user agent
        user_agent = self.config.user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )

        self._context = await self._browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
        )

        # Add anti-detection scripts
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)

        # Create page
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.config.timeout)

        self.logger.info(f"Browser initialized for {self.config.name}")

    async def _close_browser(self) -> None:
        """Close browser and cleanup resources."""
        if self._page:
            await self._page.close()
            self._page = None
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        self.logger.info(f"Browser closed for {self.config.name}")

    def _rate_limit(self) -> None:
        """Apply rate limiting delay between requests.

        Uses configured rate_limit with small random jitter
        to avoid detection patterns.
        """
        delay = self.config.rate_limit
        time.sleep(delay)
        self.logger.debug(f"Rate limit applied: {delay}s delay")

    async def _navigate_with_retry(
        self, url: str, max_retries: Optional[int] = None
    ) -> Page:
        """Navigate to URL with retry logic.

        Args:
            url: Target URL
            max_retries: Override default MAX_RETRIES

        Returns:
            Page instance after successful navigation

        Raises:
            ScrapingError: If all retries exhausted
        """
        max_retries = max_retries or self.MAX_RETRIES
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                self._rate_limit()

                await self._page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.config.timeout,
                )

                self.logger.info(f"Navigated to: {url}")
                return self._page

            except PlaywrightTimeoutError as e:
                last_error = e
                self.logger.warning(
                    f"Timeout on attempt {attempt}/{max_retries} for {url}"
                )

            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"Error on attempt {attempt}/{max_retries}: {e}"
                )

            # Exponential backoff before retry
            if attempt < max_retries:
                delay = self.BASE_RETRY_DELAY * (2 ** (attempt - 1))
                self.logger.debug(f"Retrying after {delay}s...")
                await asyncio.sleep(delay)

        raise ScrapingError(
            self.config.name,
            f"Failed to navigate after {max_retries} attempts",
            url=url,
        ) from last_error

    async def _wait_for_selector(
        self, selector: str, timeout: Optional[int] = None
    ) -> Any:
        """Wait for selector to appear in page.

        Args:
            selector: CSS selector
            timeout: Override default timeout

        Returns:
            ElementHandle if found

        Raises:
            ParseError: If selector not found
        """
        timeout = timeout or self.config.timeout

        try:
            return await self._page.wait_for_selector(
                selector,
                timeout=timeout,
            )
        except PlaywrightTimeoutError:
            raise ParseError(
                self.config.name,
                f"Selector not found: {selector}",
            )

    async def _extract_text(
        self, element: Any, selector: str, default: str = ""
    ) -> str:
        """Extract text content from element using selector.

        Args:
            element: Parent element
            selector: CSS selector for target element
            default: Default value if not found

        Returns:
            Extracted text or default
        """
        try:
            el = await element.query_selector(selector)
            if el:
                text = await el.text_content()
                return (text or "").strip()
        except Exception as e:
            self.logger.debug(f"Failed to extract text for {selector}: {e}")

        return default

    async def _extract_attribute(
        self, element: Any, selector: str, attribute: str, default: str = ""
    ) -> str:
        """Extract attribute value from element using selector.

        Args:
            element: Parent element
            selector: CSS selector for target element
            attribute: Attribute name to extract
            default: Default value if not found

        Returns:
            Extracted attribute value or default
        """
        try:
            el = await element.query_selector(selector)
            if el:
                value = await el.get_attribute(attribute)
                return value or default
        except Exception as e:
            self.logger.debug(f"Failed to extract {attribute} for {selector}: {e}")

        return default

    def _build_url(self, path: str) -> str:
        """Build absolute URL from relative path.

        Args:
            path: Relative or absolute URL path

        Returns:
            Absolute URL
        """
        return urljoin(self.config.base_url, path)

    @abstractmethod
    async def parse_product(self, element: Any) -> Optional[ProductData]:
        """Parse product data from a page element.

        Args:
            element: Playwright ElementHandle for product container

        Returns:
            ProductData if parsing successful, None otherwise

        Raises:
            ParseError: If critical parsing fails
        """
        pass

    @abstractmethod
    async def get_products(self, category: Optional[str] = None) -> list[ProductData]:
        """Scrape and return all products from the site.

        Args:
            category: Optional category filter

        Returns:
            List of ProductData objects
        """
        pass

    async def scrape(self, category: Optional[str] = None) -> list[ProductData]:
        """Main scraping entry point.

        Handles:
        - Browser initialization
        - Error recovery
        - Result validation

        Args:
            category: Optional category filter

        Returns:
            List of scraped ProductData objects

        Raises:
            ScrapingError: If fatal error occurs
        """
        self.logger.info(f"Starting scrape for {self.config.name}")

        try:
            products = await self.get_products(category)

            self.logger.info(
                f"Scrape complete: {len(products)} products from {self.config.name}"
            )

            return products

        except ScrapingError:
            raise

        except Exception as e:
            raise ScrapingError(
                self.config.name,
                f"Unexpected error during scrape: {e}",
            ) from e

    def validate_product(self, product: ProductData) -> bool:
        """Validate product data before storing.

        Args:
            product: ProductData to validate

        Returns:
            True if valid, False otherwise
        """
        if not product.name or not product.name.strip():
            self.logger.warning("Product validation failed: empty name")
            return False

        if product.price <= 0:
            self.logger.warning(
                f"Product validation failed: invalid price {product.price}"
            )
            return False

        return True
