"""
Enhanced logging configuration for HorecaMark.

Provides:
- File and console logging with daily rotation
- Colored console output when available
- Structured logging for analysis
- Turkish language support for user-facing messages
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import Config


# Color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BOLD = "\033[1m"

    # Check if colors are supported
    @staticmethod
    def supported() -> bool:
        """Check if terminal supports colors."""
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


class ColoredFormatter(logging.Formatter):
    """Formatter with color support for console output."""

    # Level colors
    LEVEL_COLORS = {
        logging.DEBUG: Colors.CYAN,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.RED + Colors.BOLD,
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        if Colors.supported():
            level_color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)
            record.levelname = f"{level_color}{record.levelname}{Colors.RESET}"
            record.name = f"{Colors.BLUE}{record.name}{Colors.RESET}"

        return super().format(record)


class DailyFileHandler(logging.FileHandler):
    """File handler with daily rotation support."""

    def __init__(self, base_dir: Path, prefix: str = "scraper"):
        """Initialize with daily filename."""
        self.base_dir = base_dir
        self.prefix = prefix
        self.current_date = None
        self._update_filename()
        super().__init__(self.filename, mode="a", encoding="utf-8")

    def _update_filename(self) -> None:
        """Update filename based on current date."""
        today = datetime.now().strftime("%Y%m%d")
        if today != self.current_date:
            self.current_date = today
            self.filename = self.base_dir / f"{self.prefix}_{today}.log"

            # Create directory if needed
            self.base_dir.mkdir(parents=True, exist_ok=True)

    def emit(self, record: logging.LogRecord) -> None:
        """Emit log record, checking for date change."""
        self._update_filename()

        # Stream might be closed after date change
        if self.stream is None or self.stream.closed:
            try:
                self.stream = open(self.filename, mode="a", encoding="utf-8")
            except Exception:
                self.handleError(record)
                return

        super().emit(record)


def get_logger(
    name: str,
    level: int = logging.INFO,
    use_colors: bool = True,
) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the module)
        level: Logging level (default: INFO)
        use_colors: Use colored console output (default: True)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if use_colors and Colors.supported():
        console_format = ColoredFormatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            datefmt="%H:%M:%S"
        )
    else:
        console_format = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            datefmt="%H:%M:%S"
        )

    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler with daily rotation
    Config.ensure_dirs()
    file_handler = DailyFileHandler(Config.LOGS_DIR, "horecemark")
    file_handler.setLevel(logging.DEBUG)  # Always log DEBUG to file
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def set_global_level(level: int) -> None:
    """
    Set logging level for all HorecaMark loggers.

    Args:
        level: New logging level
    """
    logging.getLogger("scraper").setLevel(level)

    # Update all handlers
    for logger_name in logging.Logger.manager.loggerDict:
        if logger_name.startswith("scraper"):
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)


class ProgressLogger:
    """Logger for tracking scraping progress with visual indicators."""

    def __init__(self, logger: logging.Logger, total: int, task: str = "Isleniyor"):
        """
        Initialize progress tracker.

        Args:
            logger: Logger instance to use
            total: Total number of items to process
            task: Task name in Turkish
        """
        self.logger = logger
        self.total = total
        self.task = task
        self.current = 0
        self.last_percent = -1

    def update(self, increment: int = 1, item: str = "") -> None:
        """
        Update progress.

        Args:
            increment: Number of items completed
            item: Optional item name to log
        """
        self.current += increment
        percent = int((self.current / self.total) * 100)

        # Log at specific milestones
        milestones = [1, 5, 10, 25, 50, 75, 90, 95, 99, 100]
        if percent in milestones and percent != self.last_percent:
            self.last_percent = percent
            self.logger.info(f"{self.task}: {self.current}/{self.total} (%{percent})")

        # Log individual items if verbose
        elif item:
            self.logger.debug(f"  -> {item}")

    def complete(self) -> None:
        """Mark progress as complete."""
        self.current = self.total
        self.logger.info(f"{self.task} tamamlandi: {self.total} urun")


class ScrapeSummary:
    """Summary logger for scrape operations."""

    def __init__(self, logger: logging.Logger):
        """
        Initialize summary tracker.

        Args:
            logger: Logger instance to use
        """
        self.logger = logger
        self.start_time = None
        self.site_results: dict[str, dict] = {}

    def start(self) -> None:
        """Start tracking scrape operation."""
        self.start_time = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info("HorecaMark Fiyat Izleme - Baslatiliyor")
        self.logger.info("=" * 60)

    def start_site(self, site_name: str, display_name: str) -> None:
        """
        Start tracking a site scrape.

        Args:
            site_name: Internal site identifier
            display_name: Display name for the site
        """
        self.site_results[site_name] = {
            "name": display_name,
            "success": False,
            "products": 0,
            "errors": [],
        }
        self.logger.info(f"")
        self.logger.info(f"[{display_name}] Scraping baslatiliyor...")

    def complete_site(
        self,
        site_name: str,
        products: int,
        errors: list[str] | None = None,
    ) -> None:
        """
        Mark site scrape as complete.

        Args:
            site_name: Internal site identifier
            products: Number of products scraped
            errors: Optional list of error messages
        """
        if site_name not in self.site_results:
            return

        self.site_results[site_name]["success"] = True
        self.site_results[site_name]["products"] = products
        self.site_results[site_name]["errors"] = errors or []

        status = "BASARILI" if not errors else "YAPILAN HATALARLA"
        self.logger.info(f"[{self.site_results[site_name]['name']}] {status}: {products} urun")

        if errors:
            for error in errors[:3]:  # Max 3 errors shown
                self.logger.warning(f"  - {error}")
            if len(errors) > 3:
                self.logger.warning(f"  ... ve {len(errors) - 3} hata daha")

    def fail_site(self, site_name: str, error: str) -> None:
        """
        Mark site scrape as failed.

        Args:
            site_name: Internal site identifier
            error: Error message
        """
        if site_name not in self.site_results:
            return

        self.site_results[site_name]["success"] = False
        self.site_results[site_name]["errors"].append(error)

        self.logger.error(f"[{self.site_results[site_name]['name']}] BASARISIZ: {error}")

    def finish(self) -> dict:
        """
        Finish tracking and return summary.

        Returns:
            Summary dict with results
        """
        if not self.start_time:
            return {}

        duration = datetime.now() - self.start_time

        # Calculate totals
        total_products = sum(r["products"] for r in self.site_results.values())
        successful_sites = sum(1 for r in self.site_results.values() if r["success"])
        total_sites = len(self.site_results)

        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("SCRAPING OZETI")
        self.logger.info("=" * 60)
        self.logger.info(f"Toplam Site:           {total_sites}/{len(self.site_results)}")
        self.logger.info(f"Basarili Site:         {successful_sites}")
        self.logger.info(f"Toplam Urun:          {total_products}")
        self.logger.info(f"Sure:                 {duration}")

        # Site breakdown
        self.logger.info("")
        self.logger.info("Site Detaylari:")
        for site, result in self.site_results.items():
            status = "[OK]" if result["success"] else "[FAIL]"
            self.logger.info(
                f"  {status} {result['name']:20s} - {result['products']:4d} urun"
            )

        self.logger.info("=" * 60)

        return {
            "duration_seconds": duration.total_seconds(),
            "total_sites": total_sites,
            "successful_sites": successful_sites,
            "total_products": total_products,
            "site_results": self.site_results,
        }


# Turkish log messages for common operations
class LogMessages:
    """Turkish log message templates."""

    # Scrape messages
    SCRAPE_START = "{site} icin scraping baslatiliyor..."
    SCRAPE_COMPLETE = "{site} scraping tamamlandi: {count} urun"
    SCRAPE_FAILED = "{site} scraping BASARISIZ: {error}"
    SCRAPE_SKIP = "{site} atlandi (kategoride urun yok)"

    # Product messages
    PRODUCT_FOUND = "Urun bulundu: {name}"
    PRODUCT_SAVED = "Urun kaydedildi: {name} (ID: {id})"
    PRODUCT_MATCHED = "Urun eslestirildi: {name} -> ID: {id} (%{conf})"
    PRODUCT_NEW = "Yeni urun: {name}"
    PRODUCT_UPDATED = "Urun guncellendi: {name}"

    # Price messages
    PRICE_CHANGED = "Fiyat degisti: {name} {site} -> {old} -> {new} (%{change})"
    PRICE_DECREASED = "[FIYAT DUSTU] {name}: {old} -> {new} (%{change})"
    PRICE_INCREASED = "[FIYAT ARTTI] {name}: {old} -> {new} (%{change})"

    # Stock messages
    STOCK_OUT = "[STOK TUKENDI] {name} - {site}"
    STOCK_IN = "[STOK GELDI] {name} - {site}"
    STOCK_LOW = "[STOK AZ] {name} - {site}"

    # Database messages
    DB_CONNECTING = "Veritabani baglaniliyor..."
    DB_CONNECTED = "Veritabani baglandi"
    DB_ERROR = "Veritabani hatasi: {error}"
    DB_SAVING = "Veritabani kaydediliyor..."

    # System messages
    SYSTEM_START = "HorecaMark baslatiliyor..."
    SYSTEM_SHUTDOWN = "HorecaMark kapatiliyor..."
    SYSTEM_INTERRUPT = "Kullanici tarafindan iptal edildi"
    SYSTEM_ERROR = "Sistem hatasi: {error}"


# Convenience function for quick summary logging
def log_scrape_result(
    logger: logging.Logger,
    site_name: str,
    display_name: str,
    product_count: int,
    error_count: int,
    duration: float,
) -> None:
    """
    Log scrape result in Turkish.

    Args:
        logger: Logger instance
        site_name: Site identifier
        display_name: Display name
        product_count: Number of products scraped
        error_count: Number of errors
        duration: Duration in seconds
    """
    if error_count == 0:
        logger.info(
            f"[{display_name}] Tamamlandi: {product_count} urun, {duration:.1f}s"
        )
    else:
        logger.warning(
            f"[{display_name}] Tamamlandi (hatalarla): "
            f"{product_count} urun, {error_count} hata, {duration:.1f}s"
        )
