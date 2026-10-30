-- Inventory Management schema
-- Category 1──* Product 1──* ProductVariant 1──1 Inventory
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Categories (
    category_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS Products (
    product_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id  INTEGER NOT NULL REFERENCES Categories(category_id),
    product_name TEXT NOT NULL,
    description  TEXT
);

CREATE TABLE IF NOT EXISTS ProductVariants (
    variant_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id   INTEGER NOT NULL REFERENCES Products(product_id),
    sku          TEXT NOT NULL UNIQUE,
    variant_name TEXT NOT NULL,
    price        REAL NOT NULL CHECK (price >= 0)
);

CREATE TABLE IF NOT EXISTS Inventory (
    inventory_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id    INTEGER NOT NULL UNIQUE REFERENCES ProductVariants(variant_id),
    quantity      INTEGER NOT NULL CHECK (quantity >= 0),
    reorder_level INTEGER NOT NULL DEFAULT 10 CHECK (reorder_level >= 0)
);

CREATE INDEX IF NOT EXISTS idx_products_category ON Products(category_id);
CREATE INDEX IF NOT EXISTS idx_variants_product  ON ProductVariants(product_id);

-- Audit trail: every stock change is recorded (who/what/when/why)
CREATE TABLE IF NOT EXISTS StockMovements (
    movement_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id   INTEGER NOT NULL REFERENCES ProductVariants(variant_id),
    old_quantity INTEGER NOT NULL,
    new_quantity INTEGER NOT NULL,
    delta        INTEGER NOT NULL,
    reason       TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_moves_variant ON StockMovements(variant_id);
