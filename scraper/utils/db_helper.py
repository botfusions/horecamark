"""
Database helper functions for HorecaMark scraper.

Provides high-level database operations for:
- Product storage and retrieval
- Price snapshot management
- Price change detection and logging
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from scraper.database import (
    Product,
    PriceSnapshot,
    PriceChange,
    StockChange,
    get_session,
)
from scraper.utils.logger import get_logger
from scraper.utils.normalizer import normalize

logger = get_logger("db_helper")


def save_product(
    session: Session,
    name: str,
    normalized_name: str,
    brand: Optional[str] = None,
    category: Optional[str] = None,
) -> Product:
    """Save or update product in database.

    Uses normalized_name for deduplication. If product exists,
    updates brand and category if provided.

    Args:
        session: SQLAlchemy session
        name: Original product name
        normalized_name: Normalized name for matching
        brand: Optional brand name
        category: Optional category

    Returns:
        Product instance (existing or newly created)
    """
    # Try to find existing product by normalized name
    stmt = select(Product).where(Product.normalized_name == normalized_name)
    result = session.execute(stmt).scalar_one_or_none()

    if result:
        # Update if new data provided
        if brand and not result.brand:
            result.brand = brand
        if category and not result.category:
            result.category = category

        logger.debug(f"Found existing product: {normalized_name}")
        return result

    # Create new product
    product = Product(
        normalized_name=normalized_name,
        brand=brand,
        category=category,
    )
    session.add(product)
    session.flush()  # Get ID without commit

    logger.info(f"Created new product: {normalized_name}")
    return product


def save_price_snapshot(
    session: Session,
    product_id: int,
    site_name: str,
    original_name: str,
    price: Decimal,
    currency: str = "TRY",
    stock_status: str = "unknown",
    url: Optional[str] = None,
    scraped_at: Optional[datetime] = None,
) -> PriceSnapshot:
    """Save price snapshot for a product.

    Enforces uniqueness: one snapshot per site per product per day.
    If snapshot exists for today, updates price and stock status.

    Args:
        session: SQLAlchemy session
        product_id: Product foreign key
        site_name: Site identifier
        original_name: Original product name from site
        price: Current price
        currency: Currency code (default: TRY)
        stock_status: Stock availability status
        url: Product URL
        scraped_at: Timestamp (default: now)

    Returns:
        PriceSnapshot instance
    """
    if scraped_at is None:
        scraped_at = datetime.utcnow()

    # Check for existing snapshot today
    today_start = scraped_at.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)

    stmt = select(PriceSnapshot).where(
        and_(
            PriceSnapshot.product_id == product_id,
            PriceSnapshot.site_name == site_name,
            PriceSnapshot.scraped_at >= today_start,
            PriceSnapshot.scraped_at < tomorrow_start,
        )
    )
    result = session.execute(stmt).scalar_one_or_none()

    if result:
        # Update existing snapshot
        result.price = price
        result.stock_status = stock_status
        result.original_name = original_name
        if url:
            result.url = url

        logger.debug(f"Updated snapshot for product {product_id} on {site_name}")
        return result

    # Create new snapshot
    snapshot = PriceSnapshot(
        site_name=site_name,
        product_id=product_id,
        original_name=original_name,
        price=price,
        currency=currency,
        stock_status=stock_status,
        url=url,
        scraped_at=scraped_at,
    )
    session.add(snapshot)

    logger.debug(f"Created snapshot for product {product_id} on {site_name}")
    return snapshot


def get_last_price(
    session: Session,
    product_id: int,
    site_name: str,
    before: Optional[datetime] = None,
) -> Optional[PriceSnapshot]:
    """Get last price snapshot for a product on a site.

    Args:
        session: SQLAlchemy session
        product_id: Product foreign key
        site_name: Site identifier
        before: Only consider snapshots before this time (default: now)

    Returns:
        Last PriceSnapshot or None if no history
    """
    if before is None:
        before = datetime.utcnow()

    stmt = (
        select(PriceSnapshot)
        .where(
            and_(
                PriceSnapshot.product_id == product_id,
                PriceSnapshot.site_name == site_name,
                PriceSnapshot.scraped_at < before,
            )
        )
        .order_by(PriceSnapshot.scraped_at.desc())
        .limit(1)
    )

    return session.execute(stmt).scalar_one_or_none()


def calculate_price_change(
    old_price: Decimal,
    new_price: Decimal,
) -> Optional[Decimal]:
    """Calculate percentage price change.

    Args:
        old_price: Previous price
        new_price: Current price

    Returns:
        Percentage change (positive for increase, negative for decrease)
        Returns None if old_price is zero
    """
    if old_price == 0:
        return None

    change = ((new_price - old_price) / old_price) * 100
    return change.quantize(Decimal("0.01"))


def save_price_change(
    session: Session,
    product_id: int,
    old_price: Decimal,
    new_price: Decimal,
    site_name: str,
    change_percent: Decimal,
    detected_at: Optional[datetime] = None,
) -> PriceChange:
    """Log significant price change.

    Args:
        session: SQLAlchemy session
        product_id: Product foreign key
        old_price: Previous price
        new_price: Current price
        site_name: Site where change detected
        change_percent: Calculated percentage change
        detected_at: Timestamp (default: now)

    Returns:
        PriceChange instance
    """
    if detected_at is None:
        detected_at = datetime.utcnow()

    change = PriceChange(
        product_id=product_id,
        old_price=old_price,
        new_price=new_price,
        change_percent=change_percent,
        site_name=site_name,
        detected_at=detected_at,
        is_notified=False,
    )
    session.add(change)

    logger.info(
        f"Price change logged: product {product_id} on {site_name}: "
        f"{old_price} -> {new_price} ({change_percent:+.1f}%)"
    )

    return change


def check_and_log_price_changes(
    session: Session,
    product_id: int,
    site_name: str,
    new_price: Decimal,
    threshold: float = 5.0,
) -> Optional[PriceChange]:
    """Check for price change and log if significant.

    Compares new price with last recorded price for the product
    on the same site. Creates PriceChange record if threshold exceeded.

    Args:
        session: SQLAlchemy session
        product_id: Product foreign key
        site_name: Site identifier
        new_price: Current price
        threshold: Minimum percentage change to log (default: 5%)

    Returns:
        PriceChange if significant change detected, None otherwise
    """
    # Get last price for this product on this site
    last_snapshot = get_last_price(session, product_id, site_name)

    if not last_snapshot:
        # No previous price, can't calculate change
        return None

    # Calculate change
    change_percent = calculate_price_change(
        last_snapshot.price,
        new_price,
    )

    if change_percent is None:
        return None

    # Check if exceeds threshold (use absolute value)
    if abs(change_percent) >= threshold:
        return save_price_change(
            session=session,
            product_id=product_id,
            old_price=last_snapshot.price,
            new_price=new_price,
            site_name=site_name,
            change_percent=change_percent,
        )

    return None


def find_or_create_product(
    session: Session,
    name: str,
    brand: Optional[str] = None,
    category: Optional[str] = None,
) -> Product:
    """Find existing product or create new one.

    First searches for exact normalized name match.
    If not found, creates new product with normalized name.

    Args:
        session: SQLAlchemy session
        name: Original product name
        brand: Optional brand name
        category: Optional category

    Returns:
        Product instance
    """
    normalized = normalize(name)
    return save_product(
        session=session,
        name=name,
        normalized_name=normalized,
        brand=brand,
        category=category,
    )


def get_unnotified_changes(
    session: Session,
    limit: int = 100,
) -> list[PriceChange]:
    """Get price changes that haven't been notified.

    Args:
        session: SQLAlchemy session
        limit: Maximum number of changes to return

    Returns:
        List of PriceChange objects with is_notified=False
    """
    stmt = (
        select(PriceChange)
        .where(PriceChange.is_notified == False)
        .order_by(PriceChange.detected_at.desc())
        .limit(limit)
    )

    result = session.execute(stmt).scalars().all()
    return list(result)


def mark_changes_notified(
    session: Session,
    change_ids: list[int],
) -> int:
    """Mark price changes as notified.

    Args:
        session: SQLAlchemy session
        change_ids: List of PriceChange IDs to mark

    Returns:
        Number of changes updated
    """
    if not change_ids:
        return 0

    count = (
        session.execute(
            select(PriceChange)
            .where(
                and_(
                    PriceChange.id.in_(change_ids),
                    PriceChange.is_notified == False,
                )
            )
        )
        .scalars()
        .all()
    )

    for change in count:
        change.is_notified = True

    logger.info(f"Marked {len(count)} price changes as notified")
    return len(count)


def get_site_summary(
    session: Session,
    site_name: str,
    days: int = 7,
) -> dict:
    """Get scraping summary for a site.

    Args:
        session: SQLAlchemy session
        site_name: Site identifier
        days: Number of days to include

    Returns:
        Dictionary with summary stats
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Count products scraped
    product_count = (
        session.execute(
            select(func.count(func.distinct(PriceSnapshot.product_id)))
            .where(
                and_(
                    PriceSnapshot.site_name == site_name,
                    PriceSnapshot.scraped_at >= cutoff,
                )
            )
        ).scalar()
        or 0
    )

    # Count snapshots
    snapshot_count = (
        session.execute(
            select(func.count(PriceSnapshot.id))
            .where(
                and_(
                    PriceSnapshot.site_name == site_name,
                    PriceSnapshot.scraped_at >= cutoff,
                )
            )
        ).scalar()
        or 0
    )

    # Count price changes
    change_count = (
        session.execute(
            select(func.count(PriceChange.id))
            .where(
                and_(
                    PriceChange.site_name == site_name,
                    PriceChange.detected_at >= cutoff,
                )
            )
        ).scalar()
        or 0
    )

    # Average price
    avg_price = (
        session.execute(
            select(func.avg(PriceSnapshot.price))
            .where(
                and_(
                    PriceSnapshot.site_name == site_name,
                    PriceSnapshot.scraped_at >= cutoff,
                )
            )
        ).scalar()
        or Decimal("0")
    )

    return {
        "site_name": site_name,
        "days": days,
        "products_tracked": product_count,
        "snapshots_taken": snapshot_count,
        "price_changes": change_count,
        "average_price": float(avg_price),
    }


def save_stock_change(
    session: Session,
    product_id: int,
    previous_status: str,
    new_status: str,
    change_type: str,
    site_name: str,
    detected_at: Optional[datetime] = None,
) -> StockChange:
    """Log stock status change.

    Args:
        session: SQLAlchemy session
        product_id: Product foreign key
        previous_status: Previous stock status
        new_status: New stock status
        change_type: Type of change (stock_out, stock_in, stock_low, status_change)
        site_name: Site where change detected
        detected_at: Timestamp (default: now)

    Returns:
        StockChange instance
    """
    if detected_at is None:
        detected_at = datetime.utcnow()

    change = StockChange(
        product_id=product_id,
        previous_status=previous_status,
        new_status=new_status,
        change_type=change_type,
        site_name=site_name,
        detected_at=detected_at,
        is_notified=False,
    )
    session.add(change)

    logger.info(
        f"Stock change logged: product {product_id} on {site_name}: "
        f"{previous_status} -> {new_status} ({change_type})"
    )

    return change


def get_scraped_urls(
    session: Session,
    site_name: str,
    since: datetime,
) -> set[str]:
    """Get all URLs scraped from a site since a given date.

    Args:
        session: SQLAlchemy session
        site_name: Site identifier
        since: Start date to look back

    Returns:
        Set of URLs
    """
    stmt = select(PriceSnapshot.url).where(
        and_(
            PriceSnapshot.site_name == site_name,
            PriceSnapshot.scraped_at >= since,
            PriceSnapshot.url.isnot(None),
        )
    )

    result = session.execute(stmt).scalars().all()
    return set(result)
