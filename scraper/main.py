"""
HorecaMark main orchestration loop.

Coordinates the complete scraping workflow:
- Scrapes all configured sites
- Matches products against database
- Detects price and stock changes
- Generates reports
"""

import argparse
import asyncio
import signal
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from scraper.utils.config import Config
from scraper.utils.logger import (
    get_logger,
    ScrapeSummary,
    LogMessages,
    set_global_level,
)
from scraper.utils.notifier import EmailNotifier
from scraper.utils.reporter import ExcelReporter, generate_report
from scraper.utils.scheduler import run_once, run_scheduler

# Import orchestration components
from scraper.sites import list_scrapers, SCRAPER_FACTORIES
from scraper.database import get_session, init_db
from scraper.utils.db_helper import (
    find_or_create_product,
    save_price_snapshot,
    check_and_log_price_changes,
    get_site_summary,
)
from scraper.utils.matcher import ProductMatcher, ProductInfo
from scraper.utils.analyzer import (
    detect_price_change,
    detect_stock_change,
    detect_new_products,
)
from scraper.sites.base import ScrapingError, ProductData

logger = get_logger(__name__)

# Global flag for graceful shutdown
_shutdown_requested = False


def request_shutdown(signum=None, frame=None):
    """Request graceful shutdown."""
    global _shutdown_requested
    _shutdown_requested = True
    logger.warning(LogMessages.SYSTEM_INTERRUPT)


# Setup signal handlers
signal.signal(signal.SIGINT, request_shutdown)
signal.signal(signal.SIGTERM, request_shutdown)


class ScrapeOrchestrator:
    """Main orchestration class for scraping operations."""

    def __init__(
        self,
        sites: Optional[list[str]] = None,
        categories: Optional[list[str]] = None,
        dry_run: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize orchestrator.

        Args:
            sites: List of site names to scrape (default: all)
            categories: Categories to filter (default: all)
            dry_run: If True, don't save to database
            verbose: Enable verbose logging
        """
        self.sites = sites or list_scrapers()
        self.categories = categories
        self.dry_run = dry_run
        self.verbose = verbose

        if verbose:
            set_global_level(10)  # DEBUG level

        # Initialize components
        self.matcher = ProductMatcher()
        self.summary = ScrapeSummary(logger)

        # Results tracking
        self.results = {
            "sites_scraped": {},
            "total_products": 0,
            "new_products": 0,
            "price_changes": 0,
            "stock_changes": 0,
            "errors": [],
        }

    async def run_scrape(self) -> dict:
        """
        Main scraping orchestration.

        Returns:
            Summary dict with results
        """
        self.summary.start()
        logger.info(f"Siteler: {', '.join(self.sites)}")
        logger.info(f"Kategoriler: {', '.join(self.categories) if self.categories else 'Tümü'}")
        logger.info(f"Dry Run: {self.dry_run}")

        # Initialize database
        if not self.dry_run:
            logger.info(LogMessages.DB_CONNECTING)
            try:
                init_db()
                logger.info(LogMessages.DB_CONNECTED)
            except Exception as e:
                logger.error(f"{LogMessages.DB_ERROR.format(error=e)}")
                self.results["errors"].append(f"Database init: {e}")
                return self.results

        # Scrape each site
        for idx, site_name in enumerate(self.sites, 1):
            if _shutdown_requested:
                logger.warning("Iptal talebi alindi, durduruluyor...")
                break

            site_config = Config.SITE_CONFIGS.get(site_name)
            display_name = site_config["name"] if site_config else site_name

            self.summary.start_site(site_name, display_name)
            logger.info(f"Site {idx}/{len(self.sites)}: {display_name}")

            try:
                site_result = await self._scrape_site(site_name, display_name)
                self.summary.complete_site(
                    site_name,
                    site_result["products"],
                    site_result.get("errors"),
                )
                self.results["sites_scraped"][site_name] = site_result

            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                self.summary.fail_site(site_name, error_msg)
                self.results["errors"].append(f"{site_name}: {error_msg}")
                logger.exception(f"Site scraping failed: {site_name}")

        # Finish and return summary
        final_summary = self.summary.finish()
        self.results.update(final_summary)

        return self.results

    async def _scrape_site(self, site_name: str, display_name: str) -> dict:
        """
        Scrape a single site and process results.

        Args:
            site_name: Internal site identifier
            display_name: Display name

        Returns:
            Dict with scrape results
        """
        site_start = datetime.now()
        result = {
            "products": 0,
            "new": 0,
            "updated": 0,
            "price_changes": 0,
            "stock_changes": 0,
            "errors": [],
        }

        # Get scraper and run
        scraper_factory = SCRAPER_FACTORIES.get(site_name)
        if not scraper_factory:
            raise ValueError(f"Scraper not found: {site_name}")

        scraper = scraper_factory()

        try:
            async with scraper:
                products = await scraper.scrape(category=self._get_category())

                logger.info(f"{display_name}: {len(products)} urun bulundu")

                # Process products
                for product in products:
                    if _shutdown_requested:
                        break

                    if not scraper.validate_product(product):
                        continue

                    try:
                        await self._process_product(product, site_name)
                        result["products"] += 1

                    except Exception as e:
                        result["errors"].append(f"{product.name}: {e}")
                        logger.debug(f"Product processing error: {e}")

        except ScrapingError as e:
            result["errors"].append(str(e))
            logger.error(f"Scraping error: {e}")

        except Exception as e:
            result["errors"].append(f"Unexpected: {e}")
            logger.exception(f"Unexpected error scraping {site_name}")

        # Save to database if not dry run
        if not self.dry_run and result["products"] > 0:
            self._save_site_results(site_name, result)

        duration = (datetime.now() - site_start).total_seconds()
        logger.info(
            f"{display_name} tamamlandi: {result['products']} urun, {duration:.1f}s"
        )

        return result

    async def _process_product(self, product: ProductData, site_name: str) -> None:
        """
        Process a single product: match, save, detect changes.

        Args:
            product: ProductData from scraper
            site_name: Site identifier
        """
        if self.dry_run:
            logger.debug(f"[DRY RUN] {product.name} - {product.price} TL")
            return

        session = get_session()

        try:
            # Find or create product
            db_product = find_or_create_product(
                session=session,
                name=product.name,
                brand=product.brand,
                category=product.category,
            )

            # Save price snapshot
            snapshot = save_price_snapshot(
                session=session,
                product_id=db_product.id,
                site_name=site_name,
                original_name=product.name,
                price=Decimal(str(product.price)),
                currency=product.currency,
                stock_status=product.stock_status or "unknown",
                url=product.url,
            )

            # Check for price changes
            price_change = check_and_log_price_changes(
                session=session,
                product_id=db_product.id,
                site_name=site_name,
                new_price=Decimal(str(product.price)),
                threshold=Config.PRICE_CHANGE_THRESHOLD,
            )

            if price_change:
                self.results["price_changes"] += 1
                change = float(price_change.change_percent)
                if change < 0:
                    logger.info(
                        f"[FIYAT DUSTU] {product.name[:40]}: "
                        f"{price_change.old_price} -> {product.price} ({change:+.1f}%)"
                    )
                else:
                    logger.info(
                        f"[FIYAT ARTTI] {product.name[:40]}: "
                        f"{price_change.old_price} -> {product.price} ({change:+.1f}%)"
                    )

            session.commit()

        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def _save_site_results(self, site_name: str, result: dict) -> None:
        """Save site results to tracking."""
        self.results["total_products"] += result["products"]
        self.results["new_products"] += result.get("new", 0)
        self.results["price_changes"] += result.get("price_changes", 0)
        self.results["stock_changes"] += result.get("stock_changes", 0)

    def _get_category(self) -> Optional[str]:
        """Get category filter if specified."""
        if self.categories:
            return self.categories[0]  # Use first category for now
        return None


def health_check() -> dict:
    """
    Check system health.

    Returns:
        dict with status for each component
    """
    status = {
        "database": "unknown",
        "sites": {},
        "last_scrape": None,
        "timestamp": datetime.now().isoformat(),
    }

    # Check database
    try:
        from sqlalchemy import select, func

        session = get_session()
        from scraper.database import Product, PriceSnapshot

        # Count products
        product_count = session.execute(
            select(func.count(Product.id))
        ).scalar() or 0

        # Get last scrape
        last = session.execute(
            select(PriceSnapshot)
            .order_by(PriceSnapshot.scraped_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        session.close()

        status["database"] = "ok"
        status["product_count"] = product_count
        status["last_scrape"] = last.scraped_at.isoformat() if last else None

    except Exception as e:
        status["database"] = f"error: {e}"

    # Check sites
    for site_name in list_scrapers():
        site_config = Config.SITE_CONFIGS.get(site_name)
        status["sites"][site_name] = {
            "name": site_config["name"] if site_config else site_name,
            "status": "configured",
        }

    return status


async def run_scrape(
    sites: Optional[list[str]] = None,
    categories: Optional[list[str]] = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Main scraping orchestration.

    Args:
        sites: List of sites to scrape (default: all)
        categories: Categories to scrape (default: all)
        dry_run: If True, don't save to database
        verbose: Enable verbose output

    Returns:
        Summary dict with results
    """
    orchestrator = ScrapeOrchestrator(
        sites=sites,
        categories=categories,
        dry_run=dry_run,
        verbose=verbose,
    )

    return await orchestrator.run_scrape()


async def run_full_workflow(email_report: bool = False) -> dict:
    """
    Run complete workflow: scrape + analyze + report.

    Args:
        email_report: If True, send email report

    Returns:
        Summary dict with all results
    """
    logger.info("Tam is akisi baslatiliyor...")

    # Step 1: Scrape
    scrape_result = await run_scrape()

    if _shutdown_requested:
        logger.warning("Is akisi iptal edildi")
        return scrape_result

    # Step 2: Analyze (if not dry run)
    if not scrape_result.get("dry_run", False):
        logger.info("Analiz yapiliyor...")
        try:
            session = get_session()
            from scraper.utils.analyzer import generate_daily_summary

            summary = generate_daily_summary(session)
            session.close()

            logger.info(
                f"Analiz tamamlandi: {summary.products_with_changes} "
                f"urun degisikligi tespit edildi"
            )
            scrape_result["analysis"] = summary.to_dict()

        except Exception as e:
            logger.error(f"Analiz hatasi: {e}")
            scrape_result["analysis_error"] = str(e)

    # Step 3: Generate report
    if not scrape_result.get("dry_run", False):
        logger.info("Rapor olusturuluyor...")
        try:
            reporter = ExcelReporter()
            report_path = reporter.generate_daily_report()
            scrape_result["report_path"] = str(report_path)
            logger.info(f"Rapor kaydedildi: {report_path}")

        except Exception as e:
            logger.error(f"Rapor olusturma hatasi: {e}")
            scrape_result["report_error"] = str(e)

    # Step 4: Email report (if requested)
    if email_report:
        logger.info("E-posta gonderiliyor...")
        try:
            from scraper.utils.notifier import send_simple_report

            success = send_simple_report()
            if success:
                logger.info("E-posta basariyla gonderildi")
            else:
                logger.warning("E-posta gonderilemedi")
            scrape_result["email_sent"] = success

        except Exception as e:
            logger.error(f"E-posta hatasi: {e}")
            scrape_result["email_error"] = str(e)

    logger.info("Tam is akisi tamamlandi")
    return scrape_result


# CLI Commands


def cmd_scrape(args):
    """Scrape command handler.

    Args:
        args: Parsed command line arguments
    """
    Config.ensure_dirs()

    sites = args.site if args.site else None
    categories = [args.category] if args.category else None

    return asyncio.run(run_scrape(
        sites=sites,
        categories=categories,
        dry_run=args.dry_run,
        verbose=args.verbose,
    ))


def cmd_run(args):
    """Run full workflow command.

    Args:
        args: Parsed command line arguments
    """
    Config.ensure_dirs()
    return asyncio.run(run_full_workflow(email_report=args.email))


def cmd_report(args):
    """Generate daily report command.

    Args:
        args: Parsed command line arguments
    """
    Config.ensure_dirs()
    logger.info("Gunluk rapor olusturuluyor...")

    report_date = None
    if args.date:
        report_date = date.fromisoformat(args.date)

    reporter = ExcelReporter()
    filepath = reporter.generate_daily_report(report_date)

    logger.info(f"Rapor kaydedildi: {filepath}")

    # Send email if requested
    if args.email:
        logger.info("E-posta raporu gonderiliyor...")
        from scraper.utils.notifier import send_simple_report

        success = send_simple_report(report_date)
        if success:
            logger.info("E-posta basariyla gonderildi")
        else:
            logger.error("E-posta gonderilemedi")

    return filepath


def cmd_health(args):
    """Health check command.

    Args:
        args: Parsed command line arguments
    """
    status = health_check()

    print("\n=== HorecaMark Sistem Durumu ===\n")
    print(f"Zaman damgasi:  {status['timestamp']}")
    print(f"Veritabani:     {status['database']}")
    print(f"Son scraping:   {status.get('last_scrape', 'Hiç')}")

    if "product_count" in status:
        print(f"Toplam urun:    {status['product_count']}")

    print("\nSiteler:")
    for site_id, site_info in status["sites"].items():
        print(f"  - {site_info['name']}: {site_info['status']}")

    print()

    return 0 if status["database"] == "ok" else 1


def cmd_schedule(args):
    """Run scheduler command.

    Args:
        args: Parsed command line arguments
    """
    Config.ensure_dirs()

    if args.once:
        logger.info("Bir kere calistiriliyor...")
        run_once()
    else:
        logger.info("Zamanlayici baslatiliyor...")
        run_scheduler()


def cmd_test_email(args):
    """Test email configuration.

    Args:
        args: Parsed command line arguments
    """
    logger.info("E-posta yapilandirmasi test ediliyor...")

    notifier = EmailNotifier()

    if not notifier.is_configured():
        logger.error("E-posta yapilandirilmamis. Asagidaki ortam degiskenlerini ayarlayin:")
        logger.error("  SMTP_HOST (varsayilan: smtp.gmail.com)")
        logger.error("  SMTP_PORT (varsayilan: 587)")
        logger.error("  SMTP_USER (e-posta adresiniz)")
        logger.error("  SMTP_PASSWORD (uygulama sifresi)")
        logger.error("  EMAIL_FROM (gonderen e-posta)")
        logger.error("  EMAIL_TO (alici e-postalar, virgulle ayrilmis)")
        return 1

    success = notifier.send_test_email()

    if success:
        logger.info("Test e-postasi basariyla gonderildi!")
        return 0
    else:
        logger.error("Test e-postasi gonderilemedi. Yapilandirmayi kontrol edin.")
        return 1


def cmd_cleanup(args):
    """Clean up old reports.

    Args:
        args: Parsed command line arguments
    """
    Config.ensure_dirs()
    logger.info(f"{args.days} gunden eski raporlar temizleniyor...")

    reporter = ExcelReporter()
    removed = reporter.cleanup_old_reports(keep_days=args.days)

    if removed:
        logger.info(f"{len(removed)} eski rapor silindi")
        for path in removed:
            logger.info(f"  - {path.name}")
    else:
        logger.info("Temizlenecek eski rapor yok")

    return len(removed)


def parse_args():
    """Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="HorecaMark Fiyat Izleme - Scraper ve Raporlama Araci",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ornekler:
  python -m scraper.main scrape              Tum siteleri scrape et
  python -m scraper.main scrape --site cafemarkt  Sadece CafeMarkt
  python -m scraper.main scrape --dry-run    Veritabanina kaydetmeden test et
  python -m scraper.main scrape --verbose    Detayli cikti
  python -m scraper.main run                 Tam is akisi (scrape + analiz + rapor)
  python -m scraper.main run --email         Raporu e-posta ile gonder
  python -m scraper.main report              Gunluk rapor olustur
  python -m scraper.main health              Sistem sagligini kontrol et
  python -m scraper.main schedule            Zamanlayiciyi baslat
  python -m scraper.main schedule --once     Bir kere calistir ve cik
  python -m scraper.main test-email          E-posta yapilandirmasini test et
  python -m scraper.main cleanup             Eski raporlari temizle
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Calistirilacak komut")

    # Scrape command (main)
    scrape_parser = subparsers.add_parser("scrape", help="Siteleri scrape et")
    scrape_parser.add_argument(
        "--site",
        "-s",
        action="append",
        help="Scrape edilecek site (varsayilan: tumu)",
    )
    scrape_parser.add_argument(
        "--category",
        "-c",
        type=str,
        help="Kategori filtrele (varsayilan: tumu)",
    )
    scrape_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Veritabanina kaydetmeden test et",
    )
    scrape_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Detayli cikti (DEBUG seviyesi)",
    )
    scrape_parser.set_defaults(func=cmd_scrape)

    # Run command (full workflow)
    run_parser = subparsers.add_parser("run", help="Tam is akisini calistir")
    run_parser.add_argument(
        "--email",
        "-e",
        action="store_true",
        help="Raporu e-posta ile gonder",
    )
    run_parser.set_defaults(func=cmd_run)

    # Report command
    report_parser = subparsers.add_parser("report", help="Gunluk rapor olustur")
    report_parser.add_argument(
        "--date",
        "-d",
        type=str,
        help="Rapor tarihi (YYYY-MM-DD formati, varsayilan: bugun)",
    )
    report_parser.add_argument(
        "--email",
        "-e",
        action="store_true",
        help="Raporu e-posta ile gonder",
    )
    report_parser.set_defaults(func=cmd_report)

    # Health check command
    health_parser = subparsers.add_parser("health", help="Sistem durumunu kontrol et")
    health_parser.set_defaults(func=cmd_health)

    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Zamanlayiciyi calistir")
    schedule_parser.add_argument(
        "--once",
        action="store_true",
        help="Bir kere calistir ve cik (daemon modu yerine)",
    )
    schedule_parser.set_defaults(func=cmd_schedule)

    # Test email command
    test_parser = subparsers.add_parser("test-email", help="E-posta yapilandirmasini test et")
    test_parser.set_defaults(func=cmd_test_email)

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Eski raporlari temizle")
    cleanup_parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=30,
        help="Bu kadar gundenden yeni raporlari tut (varsayilan: 30)",
    )
    cleanup_parser.set_defaults(func=cmd_cleanup)

    return parser.parse_args()


def main():
    """Main entry point for the scraper."""
    args = parse_args()

    # If no command specified, show help
    if not args.command:
        parse_args().print_help()
        return 0

    # Run command
    try:
        exit_code = args.func(args)
        return exit_code if exit_code is not None else 0

    except KeyboardInterrupt:
        logger.warning("\nIptal edildi")
        return 130

    except Exception as e:
        logger.exception(f"Kritik hata: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
