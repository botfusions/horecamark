"""
Database models and connection management for HorecaMark.

Uses SQLAlchemy ORM with PostgreSQL backend.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)

# Type alias for backward compatibility
SQLDecimal = Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from scraper.utils.config import Config

Base = declarative_base()


class Product(Base):
    """Normalized product representation.

    Each unique product (identified by fuzzy matching) has one record.
    The normalized_name is the cleaned version used for matching.
    """

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    normalized_name = Column(String(500), nullable=False, index=True)
    category = Column(String(100), nullable=True)
    brand = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name='{self.normalized_name}')>"


class PriceSnapshot(Base):
    """Price data captured from a specific site at a point in time.

    One record per site per product per day.
    The original_name preserves the site's naming for reference.
    """

    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_name = Column(String(50), nullable=False, index=True)
    product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_name = Column(String(500), nullable=False)
    price = Column(SQLDecimal(10, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="TRY")
    stock_status = Column(String(50), nullable=True)
    url = Column(Text, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "site_name", "product_id", "scraped_at", name="uix_site_product_date"
        ),
        Index("ix_snapshots_site_date", "site_name", "scraped_at"),
    )

    def __repr__(self) -> str:
        return f"<PriceSnapshot(site='{self.site_name}', price={self.price})>"


class PriceChange(Base):
    """Recorded price changes for alerting.

    Created when a price change exceeds the threshold (default 5%).
    is_notified tracks whether this change was sent to the user.
    """

    __tablename__ = "price_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_price = Column(SQLDecimal(10, 2), nullable=False)
    new_price = Column(SQLDecimal(10, 2), nullable=False)
    change_percent = Column(SQLDecimal(5, 2), nullable=False)
    site_name = Column(String(50), nullable=False, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_notified = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_changes_product_date", "product_id", "detected_at"),
        Index("ix_changes_notified", "is_notified", "detected_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<PriceChange(product_id={self.product_id}, "
            f"change={self.change_percent}%)>"
        )


class StockChange(Base):
    """Recorded stock status changes for alerting.

    Created when stock status changes (in/out of stock, limited, etc).
    Tracks previous status for trend analysis.
    """

    __tablename__ = "stock_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    change_type = Column(String(50), nullable=False)  # stock_out, stock_in, stock_low
    site_name = Column(String(50), nullable=False, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_notified = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_stock_changes_product_date", "product_id", "detected_at"),
        Index("ix_stock_changes_type", "change_type", "detected_at"),
        Index("ix_stock_changes_notified", "is_notified", "detected_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<StockChange(product_id={self.product_id}, "
            f"type={self.change_type}, {self.previous_status}->{self.new_status})>"
        )


# Global engine and session factory
_engine: Optional[object] = None
_SessionLocal: Optional[object] = None


def get_engine():
    """Get or create the database engine."""
    global _engine, _SessionLocal

    if _engine is None:
        database_url = Config.database_url()
        _engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

    return _engine


def get_session() -> Session:
    """Get a new database session."""
    if _SessionLocal is None:
        get_engine()
    return _SessionLocal()


def init_db():
    """Create all database tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def drop_all():
    """Drop all database tables (use with caution)."""
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
