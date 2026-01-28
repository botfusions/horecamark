"""
Analytics and change detection system for HorecaMark.

Provides functions for:
- Price change detection with action recommendations
- Stock status monitoring
- New product detection
- Competitor price comparison (pivot table)
- Daily summary generation
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Optional, NamedTuple

from sqlalchemy import and_, case, cast, func, select
from sqlalchemy.orm import Session

from scraper.database import Product, PriceSnapshot, PriceChange, StockChange, get_session
from scraper.utils.config import Config
from scraper.utils.logger import get_logger

logger = get_logger("analyzer")


class PriceChangeResult(NamedTuple):
    """Result of price change detection."""

    change_percent: Optional[Decimal]
    old_price: Optional[Decimal]
    action_suggestion: Optional[str]
    alert_level: str


class StockChangeResult(NamedTuple):
    """Result of stock status change detection."""

    previous_status: Optional[str]
    change_type: Optional[str]
    message: Optional[str]


class SitePrice(NamedTuple):
    """Price from a specific site."""

    site_name: str
    price: Optional[Decimal]
    currency: str
    stock_status: Optional[str]
    url: Optional[str]


@dataclass
class DailySummaryStats:
    """Statistics for daily summary."""

    date: date
    total_products_scraped: int
    products_with_changes: int
    price_decreases: int
    price_increases: int
    stock_changes: int
    new_products: int
    action_items: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "date": self.date.isoformat(),
            "total_products_scraped": self.total_products_scraped,
            "products_with_changes": self.products_with_changes,
            "price_decreases": self.price_decreases,
            "price_increases": self.price_increases,
            "stock_changes": self.stock_changes,
            "new_products": self.new_products,
            "action_items": self.action_items,
        }


# Action messages for different price change scenarios
_ACTION_MESSAGES = {
    "critical_decrease": (
        "[ACIL] Rakip fiyatti dusti! Sen de dustur veya farklilastir. "
        "Musteri kaybi riski yuksek."
    ),
    "warning_decrease": "[UYARI] Rakip hafif fiyat dusturdu. Izlemeye devam et.",
    "info_increase": "[BILGI] Rakip fiyat arttirdi. Marji koru, firsati degerlendir.",
    "minor_increase": "[NOT] Rakip hafif fiyat arttirdi. Marji takip et.",
}

# Alert levels
_ALERT_LEVELS = {
    "critical": "critical",
    "warning": "warning",
    "info": "info",
    "minor": "info",
}


def detect_price_change(
    session: Session,
    product_id: int,
    new_price: Decimal,
    site_name: str,
    threshold: Optional[float] = None,
) -> PriceChangeResult:
    """Compare new price with last price from database.

    Args:
        session: SQLAlchemy session
        product_id: Product ID to check
        new_price: New price to compare
        site_name: Site identifier
        threshold: Percentage threshold for alerts (default: from Config)

    Returns:
        PriceChangeResult with change data and action suggestion
    """
    if threshold is None:
        threshold = Config.PRICE_CHANGE_THRESHOLD

    # Get last price before today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    stmt = (
        select(PriceSnapshot)
        .where(
            and_(
                PriceSnapshot.product_id == product_id,
                PriceSnapshot.site_name == site_name,
                PriceSnapshot.scraped_at < today_start,
            )
        )
        .order_by(PriceSnapshot.scraped_at.desc())
        .limit(1)
    )

    last_snapshot = session.execute(stmt).scalar_one_or_none()

    if not last_snapshot or last_snapshot.price == 0:
        return PriceChangeResult(None, None, None, "none")

    old_price = last_snapshot.price
    change_percent = ((new_price - old_price) / old_price) * 100
    change_percent = change_percent.quantize(Decimal("0.01"))

    # Check if exceeds threshold
    if abs(change_percent) < threshold:
        return PriceChangeResult(None, None, None, "none")

    # Generate action suggestion
    action_suggestion, alert_level = _get_action_suggestion(change_percent)

    return PriceChangeResult(
        change_percent=change_percent,
        old_price=old_price,
        action_suggestion=action_suggestion,
        alert_level=alert_level,
    )


def _get_action_suggestion(change_percent: Decimal) -> tuple[str, str]:
    """Generate action recommendation based on price change magnitude.

    Args:
        change_percent: Percentage change (positive=increase, negative=decrease)

    Returns:
        Tuple of (action_message, alert_level)
    """
    change = float(change_percent)

    if change < -10:
        return _ACTION_MESSAGES["critical_decrease"], _ALERT_LEVELS["critical"]
    if change < -5:
        return _ACTION_MESSAGES["warning_decrease"], _ALERT_LEVELS["warning"]
    if change > 10:
        return _ACTION_MESSAGES["info_increase"], _ALERT_LEVELS["info"]
    if change > 5:
        return _ACTION_MESSAGES["minor_increase"], _ALERT_LEVELS["minor"]

    return None, "none"


def detect_stock_change(
    session: Session,
    product_id: int,
    new_status: str,
    site_name: str,
) -> StockChangeResult:
    """Detect stock status changes.

    Args:
        session: SQLAlchemy session
        product_id: Product ID to check
        new_status: New stock status
        site_name: Site identifier

    Returns:
        StockChangeResult with previous status and change message
    """
    # Get last stock status
    stmt = (
        select(PriceSnapshot)
        .where(
            and_(
                PriceSnapshot.product_id == product_id,
                PriceSnapshot.site_name == site_name,
            )
        )
        .order_by(PriceSnapshot.scraped_at.desc())
        .limit(1)
    )

    last_snapshot = session.execute(stmt).scalar_one_or_none()

    if not last_snapshot:
        return StockChangeResult(None, None, None)

    previous_status = last_snapshot.stock_status or "unknown"

    if previous_status == new_status:
        return StockChangeResult(previous_status, None, None)

    # Determine change type and message
    change_type, message = _get_stock_change_message(
        previous_status,
        new_status,
    )

    return StockChangeResult(
        previous_status=previous_status,
        change_type=change_type,
        message=message,
    )


def _get_stock_change_message(
    previous_status: str,
    new_status: str,
) -> tuple[str, str]:
    """Generate message for stock status change.

    Args:
        previous_status: Previous stock status
        new_status: New stock status

    Returns:
        Tuple of (change_type, message)
    """
    prev_lower = previous_status.lower()
    new_lower = new_status.lower()

    stock_in_keywords = {"stokta", "available", "in stock", "var"}
    stock_out_keywords = {"tukendi", "yok", "out of stock", "not available"}

    prev_in_stock = any(k in prev_lower for k in stock_in_keywords)
    new_in_stock = any(k in new_lower for k in stock_in_keywords)

    prev_out_stock = any(k in prev_lower for k in stock_out_keywords)
    new_out_stock = any(k in new_lower for k in stock_out_keywords)

    if prev_in_stock and new_out_stock:
        return "stock_out", "[ FIRSAT ] Rakip stoku tukendi! Satis firsati."
    if prev_out_stock and new_in_stock:
        return "stock_in", "[ DIKKAT ] Rakip stoku geldi. Rekabet basladi."
    if "limited" in new_lower or "son" in new_lower or "az" in new_lower:
        return "stock_low", "[ BILGI ] Rakip stoğu azaldi."

    return "status_change", f"[ DEGISIK ] Stok durumu: {previous_status} -> {new_status}"


def detect_new_products(
    session: Session,
    site_products: list,
    site_name: str,
    lookback_days: int = 7,
) -> list:
    """Find products that didn't exist in previous scrapes.

    Args:
        session: SQLAlchemy session
        site_products: List of ProductData or dicts with 'url' key
        site_name: Site identifier
        lookback_days: Days to look back for existing products

    Returns:
        List of new products (original input type)
    """
    if not site_products:
        return []

    # Get cutoff date
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    # Get all URLs scraped from this site in the lookback period
    stmt = (
        select(PriceSnapshot.url)
        .where(
            and_(
                PriceSnapshot.site_name == site_name,
                PriceSnapshot.scraped_at >= cutoff,
                PriceSnapshot.url.isnot(None),
            )
        )
        .distinct()
    )

    result = session.execute(stmt).scalars().all()
    existing_urls = set(result)

    # Filter new products
    new_products = []
    for product in site_products:
        # Handle both dict and object with url attribute
        product_url = getattr(product, "url", None) or product.get("url") if isinstance(product, dict) else None

        if product_url and product_url not in existing_urls:
            new_products.append(product)

    logger.info(f"Detected {len(new_products)} new products on {site_name}")
    return new_products


@lru_cache(maxsize=1000)
def get_price_comparison(
    session: Session,
    product_id: int,
    site_names: Optional[tuple[str, ...]] = None,
) -> dict[str, SitePrice]:
    """Get prices from all sites for a product (pivot table).

    Args:
        session: SQLAlchemy session
        product_id: Product ID to compare
        site_names: Tuple of site names to check (default: all sites)

    Returns:
        Dict with site names as keys, SitePrice as values
    """
    if site_names is None:
        site_names = tuple(Config.SITE_CONFIGS.keys())

    # Get latest price from each site
    result = {}

    for site_name in site_names:
        stmt = (
            select(PriceSnapshot)
            .where(
                and_(
                    PriceSnapshot.product_id == product_id,
                    PriceSnapshot.site_name == site_name,
                )
            )
            .order_by(PriceSnapshot.scraped_at.desc())
            .limit(1)
        )

        snapshot = session.execute(stmt).scalar_one_or_none()

        if snapshot:
            result[site_name] = SitePrice(
                site_name=snapshot.site_name,
                price=snapshot.price,
                currency=snapshot.currency,
                stock_status=snapshot.stock_status,
                url=snapshot.url,
            )
        else:
            result[site_name] = SitePrice(
                site_name=site_name,
                price=None,
                currency="TRY",
                stock_status=None,
                url=None,
            )

    return result


def get_price_comparison_pivot(
    session: Session,
    product_ids: Optional[list[int]] = None,
    site_names: Optional[tuple[str, ...]] = None,
) -> list[dict]:
    """Get pivot table of prices across all sites for multiple products.

    Args:
        session: SQLAlchemy session
        product_ids: List of product IDs (default: all products)
        site_names: Tuple of site names (default: all sites)

    Returns:
        List of dicts with product_id, product_name, and prices per site
    """
    if site_names is None:
        site_names = tuple(Config.SITE_CONFIGS.keys())

    # Get product IDs if not provided
    if product_ids is None:
        stmt = select(Product.id).order_by(Product.id)
        result = session.execute(stmt).scalars().all()
        product_ids = list(result)

    if not product_ids:
        return []

    # Build CASE expressions for each site
    price_cases = {}
    for site in site_names:
        price_cases[f"price_{site}"] = (
            select(PriceSnapshot.price)
            .where(
                and_(
                    PriceSnapshot.product_id == Product.id,
                    PriceSnapshot.site_name == site,
                )
            )
            .order_by(PriceSnapshot.scraped_at.desc())
            .limit(1)
            .scalar_subquery()
        )

    # Build query with subquery for latest prices per site
    result = []

    for product_id in product_ids:
        # Get product info
        product = session.get(Product, product_id)
        if not product:
            continue

        row = {
            "product_id": product.id,
            "product_name": product.normalized_name,
            "brand": product.brand,
            "category": product.category,
        }

        # Get price from each site
        for site in site_names:
            stmt = (
                select(PriceSnapshot)
                .where(
                    and_(
                        PriceSnapshot.product_id == product_id,
                        PriceSnapshot.site_name == site,
                    )
                )
                .order_by(PriceSnapshot.scraped_at.desc())
                .limit(1)
            )
            snapshot = session.execute(stmt).scalar_one_or_none()

            if snapshot:
                row[f"price_{site}"] = float(snapshot.price)
                row[f"currency_{site}"] = snapshot.currency
                row[f"stock_{site}"] = snapshot.stock_status
            else:
                row[f"price_{site}"] = None
                row[f"currency_{site}"] = None
                row[f"stock_{site}"] = None

        result.append(row)

    return result


def generate_daily_summary(
    session: Session,
    summary_date: Optional[date] = None,
) -> DailySummaryStats:
    """Generate summary of all changes for a day.

    Args:
        session: SQLAlchemy session
        summary_date: Date to generate summary for (default: today)

    Returns:
        DailySummaryStats with all changes and action items
    """
    if summary_date is None:
        summary_date = date.today()

    # Define date range
    day_start = datetime.combine(summary_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    # Count total products scraped
    total_count = (
        session.execute(
            select(func.count(func.distinct(PriceSnapshot.product_id))).where(
                and_(
                    PriceSnapshot.scraped_at >= day_start,
                    PriceSnapshot.scraped_at < day_end,
                )
            )
        ).scalar()
        or 0
    )

    # Count price changes by direction
    decreases = (
        session.execute(
            select(func.count(PriceChange.id))
            .where(
                and_(
                    PriceChange.detected_at >= day_start,
                    PriceChange.detected_at < day_end,
                    PriceChange.change_percent < 0,
                )
            )
        ).scalar()
        or 0
    )

    increases = (
        session.execute(
            select(func.count(PriceChange.id))
            .where(
                and_(
                    PriceChange.detected_at >= day_start,
                    PriceChange.detected_at < day_end,
                    PriceChange.change_percent > 0,
                )
            )
        ).scalar()
        or 0
    )

    products_with_changes = decreases + increases

    # Count stock changes (approximated by comparing snapshots)
    stock_changes = 0  # Would need additional tracking table

    # Count new products (first appearance)
    new_products = (
        session.execute(
            select(func.count(func.distinct(PriceSnapshot.product_id)))
            .where(
                and_(
                    PriceSnapshot.scraped_at >= day_start,
                    PriceSnapshot.scraped_at < day_end,
                )
            )
            .having(
                func.count(PriceSnapshot.id) == 1
            )
        ).scalar()
        or 0
    )

    # Get action items (significant price changes)
    action_items = _get_action_items(session, day_start, day_end)

    return DailySummaryStats(
        date=summary_date,
        total_products_scraped=total_count,
        products_with_changes=products_with_changes,
        price_decreases=decreases,
        price_increases=increases,
        stock_changes=stock_changes,
        new_products=new_products,
        action_items=action_items,
    )


def _get_action_items(
    session: Session,
    day_start: datetime,
    day_end: datetime,
) -> list[dict]:
    """Get actionable price changes for the day.

    Args:
        session: SQLAlchemy session
        day_start: Start of day
        day_end: End of day

    Returns:
        List of action item dicts
    """
    stmt = (
        select(PriceChange, Product)
        .join(Product, PriceChange.product_id == Product.id)
        .where(
            and_(
                PriceChange.detected_at >= day_start,
                PriceChange.detected_at < day_end,
            )
        )
        .order_by(PriceChange.change_percent.asc())
        .limit(50)
    )

    results = session.execute(stmt).all()

    action_items = []
    for change, product in results:
        action_suggestion, alert_level = _get_action_suggestion(change.change_percent)

        action_items.append(
            {
                "product_id": change.product_id,
                "product_name": product.normalized_name,
                "site_name": change.site_name,
                "old_price": float(change.old_price),
                "new_price": float(change.new_price),
                "change_percent": float(change.change_percent),
                "action": action_suggestion,
                "alert_level": alert_level,
                "detected_at": change.detected_at.isoformat(),
            }
        )

    return action_items


def get_price_leader(
    session: Session,
    product_id: int,
) -> Optional[dict]:
    """Find the site with the lowest price for a product.

    Args:
        session: SQLAlchemy session
        product_id: Product ID to check

    Returns:
        Dict with site_name, price, or None if no data
    """
    stmt = (
        select(PriceSnapshot)
        .where(PriceSnapshot.product_id == product_id)
        .order_by(PriceSnapshot.scraped_at.desc())
        .limit(20)  # Get recent for comparison
    )

    snapshots = session.execute(stmt).scalars().all()

    if not snapshots:
        return None

    # Group by site and get latest price
    site_prices = {}
    for snap in snapshots:
        if snap.site_name not in site_prices:
            site_prices[snap.site_name] = snap

    # Find minimum price
    min_price = min((s.price for s in site_prices.values() if s.price), default=None)

    if min_price is None:
        return None

    # Find sites with minimum price
    leaders = [
        {"site_name": site, "price": float(snap.price), "url": snap.url}
        for site, snap in site_prices.items()
        if snap.price == min_price
    ]

    return {
        "min_price": float(min_price),
        "leaders": leaders,
        "all_prices": {
            site: float(snap.price) for site, snap in site_prices.items()
        },
    }


def get_price_trend(
    session: Session,
    product_id: int,
    site_name: str,
    days: int = 30,
) -> list[dict]:
    """Get price trend for a product on a site.

    Args:
        session: SQLAlchemy session
        product_id: Product ID to check
        site_name: Site identifier
        days: Number of days to look back

    Returns:
        List of dicts with date, price
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    stmt = (
        select(PriceSnapshot)
        .where(
            and_(
                PriceSnapshot.product_id == product_id,
                PriceSnapshot.site_name == site_name,
                PriceSnapshot.scraped_at >= cutoff,
            )
        )
        .order_by(PriceSnapshot.scraped_at.asc())
    )

    snapshots = session.execute(stmt).scalars().all()

    return [
        {
            "date": snap.scraped_at.isoformat(),
            "price": float(snap.price),
            "stock_status": snap.stock_status,
        }
        for snap in snapshots
    ]


def get_competitor_analysis(
    session: Session,
    limit: int = 100,
) -> dict:
    """Get high-level competitor analysis.

    Args:
        session: SQLAlchemy session
        limit: Max products to analyze

    Returns:
        Dict with analysis metrics
    """
    site_names = tuple(Config.SITE_CONFIGS.keys())

    # Product count per site
    product_counts = {}
    avg_prices = {}

    for site in site_names:
        # Count products
        count = (
            session.execute(
                select(func.count(func.distinct(PriceSnapshot.product_id)))
                .where(PriceSnapshot.site_name == site)
            ).scalar()
            or 0
        )
        product_counts[site] = count

        # Average price
        avg = (
            session.execute(
                select(func.avg(PriceSnapshot.price))
                .where(
                    and_(
                        PriceSnapshot.site_name == site,
                        PriceSnapshot.scraped_at
                        >= datetime.utcnow() - timedelta(days=7),
                    )
                )
            ).scalar()
            or 0
        )
        avg_prices[site] = float(avg) if avg else 0

    # Recent price changes
    recent_changes = (
        session.execute(
            select(func.count(PriceChange.id)).where(
                PriceChange.detected_at
                >= datetime.utcnow() - timedelta(days=7)
            )
        ).scalar()
        or 0
    )

    return {
        "site_product_counts": product_counts,
        "site_average_prices": avg_prices,
        "recent_price_changes_7days": recent_changes,
        "sites_analyzed": list(site_names),
    }


def clear_analyzer_cache() -> None:
    """Clear the analyzer cache."""
    get_price_comparison.cache_clear()
    logger.debug("Analyzer cache cleared")


# Convenience function to run full analysis
def run_analysis(
    session: Optional[Session] = None,
    product_id: Optional[int] = None,
) -> dict:
    """Run complete analysis for a product or all products.

    Args:
        session: SQLAlchemy session (creates new if None)
        product_id: Specific product to analyze (None for all)

    Returns:
        Dict with analysis results
    """
    close_session = False
    if session is None:
        session = get_session()
        close_session = True

    try:
        if product_id:
            # Single product analysis
            comparison = get_price_comparison(session, product_id)
            leader = get_price_leader(session, product_id)
            product = session.get(Product, product_id)

            return {
                "product": {
                    "id": product.id,
                    "name": product.normalized_name,
                    "brand": product.brand,
                },
                "price_comparison": {
                    site: {"price": float(sp.price) if sp.price else None}
                    for site, sp in comparison.items()
                },
                "price_leader": leader,
            }
        else:
            # Overall analysis
            summary = generate_daily_summary(session)
            competitor = get_competitor_analysis(session)

            return {
                "daily_summary": summary.to_dict(),
                "competitor_analysis": competitor,
            }

    finally:
        if close_session:
            session.close()
