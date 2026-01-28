"""
HorecaMark - Site Scrapers

This package contains individual scrapers for each e-commerce site.
"""

__version__ = "0.1.0"

# Import all scrapers for easy access
from scraper.sites.base import BaseScraper, ProductData, SiteConfig
from scraper.sites.cafemarkt import CafeMarktScraper, create_scraper as create_cafemarkt_scraper
from scraper.sites.arigastro import AriGastroScraper, create_scraper as create_arigastro_scraper
from scraper.sites.horecamarkt import HorecaMarktScraper, create_scraper as create_horecamarkt_scraper
from scraper.sites.kariyermutfak import KariyerMutfakScraper, create_scraper as create_kariyermutfak_scraper
from scraper.sites.mutbex import MutbexScraper, create_scraper as create_mutbex_scraper
from scraper.sites.horecamark import HorecaMarkScraper, create_scraper as create_horecamark_scraper

# Registry of all available scrapers
SCRAPER_REGISTRY = {
    "cafemarkt": CafeMarktScraper,
    "arigastro": AriGastroScraper,
    "horecamarkt": HorecaMarktScraper,
    "kariyermutfak": KariyerMutfakScraper,
    "mutbex": MutbexScraper,
    "horecamark": HorecaMarkScraper,
}

# Factory function registry
SCRAPER_FACTORIES = {
    "cafemarkt": create_cafemarkt_scraper,
    "arigastro": create_arigastro_scraper,
    "horecamarkt": create_horecamarkt_scraper,
    "kariyermutfak": create_kariyermutfak_scraper,
    "mutbex": create_mutbex_scraper,
    "horecamark": create_horecamark_scraper,
}


def get_scraper(site_name: str):
    """Get scraper instance by site name.

    Args:
        site_name: Name of the site (key from SCRAPER_REGISTRY)

    Returns:
        Scraper instance

    Raises:
        ValueError: If site_name not found in registry
    """
    factory = SCRAPER_FACTORIES.get(site_name)
    if not factory:
        raise ValueError(f"Unknown site: {site_name}. Available: {list(SCRAPER_FACTORIES.keys())}")
    return factory()


def list_scrapers():
    """Return list of available scraper names."""
    return list(SCRAPER_FACTORIES.keys())
