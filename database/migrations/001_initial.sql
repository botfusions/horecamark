-- HorecaMark Database Schema
-- Initial migration for price intelligence system
-- Run this manually or via Docker entrypoint

-- Enable UUID extension (useful for future features)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Products table: normalized product catalog
-- Each unique product identified through fuzzy matching
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    normalized_name VARCHAR(500) NOT NULL,
    category VARCHAR(100),
    brand VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Price snapshots: historical price data per site
-- One record per site per product per scrape
CREATE TABLE IF NOT EXISTS price_snapshots (
    id SERIAL PRIMARY KEY,
    site_name VARCHAR(50) NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    original_name VARCHAR(500) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'TRY',
    stock_status VARCHAR(50),
    url TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Price changes: detected significant price variations
-- Created when change exceeds threshold (default 5%)
CREATE TABLE IF NOT EXISTS price_changes (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    old_price DECIMAL(10,2) NOT NULL,
    new_price DECIMAL(10,2) NOT NULL,
    change_percent DECIMAL(5,2) NOT NULL,
    site_name VARCHAR(50) NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_notified BOOLEAN DEFAULT FALSE NOT NULL
);

-- Stock changes: detected stock status variations
-- Tracks in/out of stock, limited availability changes
CREATE TABLE IF NOT EXISTS stock_changes (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    previous_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    change_type VARCHAR(50) NOT NULL,  -- stock_out, stock_in, stock_low, status_change
    site_name VARCHAR(50) NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_notified BOOLEAN DEFAULT FALSE NOT NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS ix_products_normalized_name ON products(normalized_name);
CREATE INDEX IF NOT EXISTS ix_products_brand ON products(brand);
CREATE INDEX IF NOT EXISTS ix_snapshots_site_name ON price_snapshots(site_name);
CREATE INDEX IF NOT EXISTS ix_snapshots_product_id ON price_snapshots(product_id);
CREATE INDEX IF NOT EXISTS ix_snapshots_site_date ON price_snapshots(site_name, scraped_at);
CREATE INDEX IF NOT EXISTS ix_snapshots_scraped_at ON price_snapshots(scraped_at);
CREATE INDEX IF NOT EXISTS ix_changes_product_id ON price_changes(product_id);
CREATE INDEX IF NOT EXISTS ix_changes_site_name ON price_changes(site_name);
CREATE INDEX IF NOT EXISTS ix_changes_product_date ON price_changes(product_id, detected_at);
CREATE INDEX IF NOT EXISTS ix_changes_notified ON price_changes(is_notified, detected_at);
CREATE INDEX IF NOT EXISTS ix_stock_changes_product_id ON stock_changes(product_id);
CREATE INDEX IF NOT EXISTS ix_stock_changes_site_name ON stock_changes(site_name);
CREATE INDEX IF NOT EXISTS ix_stock_changes_product_date ON stock_changes(product_id, detected_at);
CREATE INDEX IF NOT EXISTS ix_stock_changes_type ON stock_changes(change_type, detected_at);
CREATE INDEX IF NOT EXISTS ix_stock_changes_notified ON stock_changes(is_notified, detected_at);

-- Function to update updated_at timestamp (for future use)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
