"""Data-access layer. Pure sqlite3, no MCP dependency, so it is unit-testable.
Stock rules: OUT_OF_STOCK (qty = 0), LOW_STOCK (0 < qty <= reorder_level), else IN_STOCK.
All queries are parameterised (no SQL injection). Every stock change is written to StockMovements."""
import difflib
import os
import sqlite3
from contextlib import contextmanager

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventory.db")


def db_path() -> str:
    return os.environ.get("INVENTORY_DB", DEFAULT_DB)


@contextmanager
def connect(path: str | None = None):
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_STATUS = ("CASE WHEN i.quantity = 0 THEN 'OUT_OF_STOCK' "
           "WHEN i.quantity <= i.reorder_level THEN 'LOW_STOCK' ELSE 'IN_STOCK' END")

_SELECT = f"""
SELECT p.product_id, p.product_name, p.description, c.category_name,
       v.variant_id, v.variant_name, v.sku, v.price,
       i.quantity, i.reorder_level, {_STATUS} AS status
FROM ProductVariants v
JOIN Products   p ON p.product_id  = v.product_id
JOIN Categories c ON c.category_id = p.category_id
JOIN Inventory  i ON i.variant_id  = v.variant_id
"""


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _find_variant(conn, sku: str):
    """Return (variant_id, quantity) or raise a helpful error with 'did you mean' suggestions."""
    row = conn.execute(
        "SELECT v.variant_id, i.quantity FROM ProductVariants v "
        "JOIN Inventory i ON i.variant_id = v.variant_id WHERE UPPER(v.sku) = UPPER(?)",
        (sku.strip(),)).fetchone()
    if row:
        return row
    all_skus = [r[0] for r in conn.execute("SELECT sku FROM ProductVariants")]
    close = difflib.get_close_matches(sku.strip().upper(), all_skus, n=3, cutoff=0.6)
    hint = f" Did you mean: {', '.join(close)}?" if close else ""
    raise ValueError(f"SKU '{sku}' not found.{hint}")


def _log_movement(conn, variant_id: int, old: int, new: int, reason: str):
    conn.execute("INSERT INTO StockMovements(variant_id, old_quantity, new_quantity, delta, reason) "
                 "VALUES (?,?,?,?,?)", (variant_id, old, new, new - old, reason))


# ---------------------------------------------------------------- core queries
def search_products(query: str = "", sku: str = "", category: str = "",
                    only_available: bool = False) -> list[dict]:
    where, args = [], []
    if query.strip():
        like = f"%{query.strip()}%"
        where.append("(p.product_name LIKE ? OR v.variant_name LIKE ? OR v.sku LIKE ?)")
        args += [like, like, like]
    if sku.strip():
        where.append("UPPER(v.sku) = UPPER(?)")
        args.append(sku.strip())
    if category.strip():
        where.append("UPPER(c.category_name) = UPPER(?)")
        args.append(category.strip())
    if only_available:
        where.append("i.quantity > 0")
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY c.category_name, p.product_name, v.sku"
    with connect() as conn:
        return _rows(conn.execute(sql, args))


def get_low_stock_products() -> list[dict]:
    """Low-stock AND out-of-stock items, out-of-stock first."""
    sql = _SELECT + " WHERE i.quantity <= i.reorder_level ORDER BY i.quantity ASC, v.sku"
    with connect() as conn:
        return _rows(conn.execute(sql))


def get_stock_by_sku(sku: str) -> dict:
    rows = search_products(sku=sku)
    if not rows:
        with connect() as conn:
            _find_variant(conn, sku)  # raises with 'did you mean' hint
        raise ValueError(f"SKU '{sku}' not found")
    return rows[0]


# ---------------------------------------------------------------- stock changes
def update_stock(sku: str, quantity: int, reason: str = "manual update") -> dict:
    """Set stock to an absolute quantity."""
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise ValueError("quantity must be an integer")
    if quantity < 0:
        raise ValueError("quantity cannot be negative")
    with connect() as conn:
        vid, old = _find_variant(conn, sku)
        conn.execute("UPDATE Inventory SET quantity = ? WHERE variant_id = ?", (quantity, vid))
        _log_movement(conn, vid, old, quantity, reason)
    result = get_stock_by_sku(sku)
    result["previous_quantity"] = old
    return result


def adjust_stock(sku: str, delta: int, reason: str = "adjustment") -> dict:
    """Add (+) or remove (-) units, e.g. delta=-3 for 'sold 3'. Never lets stock go below 0."""
    if isinstance(delta, bool) or not isinstance(delta, int) or delta == 0:
        raise ValueError("delta must be a non-zero integer")
    with connect() as conn:
        vid, old = _find_variant(conn, sku)
        new = old + delta
        if new < 0:
            raise ValueError(f"Insufficient stock for {sku.upper()}: only {old} available, cannot remove {-delta}")
        conn.execute("UPDATE Inventory SET quantity = ? WHERE variant_id = ?", (new, vid))
        _log_movement(conn, vid, old, new, reason)
    result = get_stock_by_sku(sku)
    result["previous_quantity"], result["change"] = old, delta
    return result


def add_product(category_name: str, product_name: str, sku: str, variant_name: str,
                price: float, initial_stock: int, description: str = "",
                reorder_level: int = 10) -> dict:
    category_name, product_name = category_name.strip(), product_name.strip()
    sku, variant_name = sku.strip().upper(), (variant_name or "Default").strip()
    if not (category_name and product_name and sku):
        raise ValueError("category_name, product_name and sku are required")
    if price < 0 or initial_stock < 0 or reorder_level < 0:
        raise ValueError("price, initial_stock and reorder_level must be >= 0")
    with connect() as conn:
        if conn.execute("SELECT 1 FROM ProductVariants WHERE UPPER(sku)=?", (sku,)).fetchone():
            raise ValueError(f"SKU '{sku}' already exists")
        cat = conn.execute("SELECT category_id FROM Categories WHERE UPPER(category_name)=UPPER(?)",
                           (category_name,)).fetchone()
        cat_id = cat["category_id"] if cat else conn.execute(
            "INSERT INTO Categories(category_name) VALUES (?)", (category_name,)).lastrowid
        prod = conn.execute("SELECT product_id FROM Products WHERE category_id=? AND UPPER(product_name)=UPPER(?)",
                            (cat_id, product_name)).fetchone()
        prod_id = prod["product_id"] if prod else conn.execute(
            "INSERT INTO Products(category_id, product_name, description) VALUES (?,?,?)",
            (cat_id, product_name, description)).lastrowid
        var_id = conn.execute(
            "INSERT INTO ProductVariants(product_id, sku, variant_name, price) VALUES (?,?,?,?)",
            (prod_id, sku, variant_name, price)).lastrowid
        conn.execute("INSERT INTO Inventory(variant_id, quantity, reorder_level) VALUES (?,?,?)",
                     (var_id, initial_stock, reorder_level))
        _log_movement(conn, var_id, 0, initial_stock, "initial stock")
    return get_stock_by_sku(sku)


# ---------------------------------------------------------------- advanced features
def get_stock_history(sku: str, limit: int = 20) -> list[dict]:
    """Audit trail for a SKU, newest first."""
    with connect() as conn:
        vid, _ = _find_variant(conn, sku)
        cur = conn.execute(
            "SELECT created_at, old_quantity, new_quantity, delta, reason FROM StockMovements "
            "WHERE variant_id = ? ORDER BY movement_id DESC LIMIT ?", (vid, max(1, min(limit, 200))))
        return _rows(cur)


def get_inventory_summary() -> dict:
    """Headline numbers: SKU count, units, stock value, breakdown by status and category."""
    base = ("FROM ProductVariants v JOIN Products p ON p.product_id=v.product_id "
            "JOIN Categories c ON c.category_id=p.category_id JOIN Inventory i ON i.variant_id=v.variant_id")
    with connect() as conn:
        t = conn.execute(f"SELECT COUNT(*) skus, COALESCE(SUM(i.quantity),0) units, "
                         f"COALESCE(SUM(i.quantity*v.price),0) value {base}").fetchone()
        cats = _rows(conn.execute(
            f"SELECT c.category_name, COUNT(*) skus, SUM(i.quantity) units, SUM(i.quantity*v.price) value "
            f"{base} GROUP BY c.category_id ORDER BY value DESC"))
        status = {"IN_STOCK": 0, "LOW_STOCK": 0, "OUT_OF_STOCK": 0}
        for r in conn.execute(f"SELECT {_STATUS} s, COUNT(*) n {base} GROUP BY s"):
            status[r["s"]] = r["n"]
    return {"total_skus": t["skus"], "total_units": t["units"],
            "total_stock_value_inr": round(t["value"], 2), "by_status": status, "by_category": cats}


_PRIORITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}


def suggest_restock(target_multiplier: float = 2.0) -> list[dict]:
    """Smart reorder plan for low/out-of-stock items.
    Order quantity brings stock up to reorder_level * target_multiplier.
    Priority uses status + 30-day sales velocity (days of cover). Cost uses list price as a proxy
    because the schema has no cost-price column."""
    low = get_low_stock_products()
    with connect() as conn:
        sold = {r["variant_id"]: r["sold"] for r in conn.execute(
            "SELECT variant_id, -SUM(delta) AS sold FROM StockMovements "
            "WHERE delta < 0 AND created_at >= datetime('now','-30 days') GROUP BY variant_id")}
    plan = []
    for r in low:
        qty, lvl = r["quantity"], r["reorder_level"]
        order_qty = max(int(round(lvl * target_multiplier)) - qty, 1)
        units_30d = sold.get(r["variant_id"], 0)
        per_day = round(units_30d / 30, 2)
        cover = round(qty / per_day, 1) if per_day > 0 else None
        if qty == 0:
            prio = "CRITICAL"
        elif (cover is not None and cover <= 7) or qty <= lvl / 2:
            prio = "HIGH"
        else:
            prio = "MEDIUM"
        plan.append({"sku": r["sku"], "product_name": r["product_name"], "variant_name": r["variant_name"],
                     "category_name": r["category_name"], "quantity": qty, "reorder_level": lvl,
                     "status": r["status"], "priority": prio, "units_sold_30d": units_30d,
                     "avg_daily_sales": per_day, "days_of_cover": cover,
                     "suggested_order_qty": order_qty,
                     "estimated_cost_at_list_price": round(order_qty * r["price"], 2)})
    plan.sort(key=lambda x: (_PRIORITY_RANK[x["priority"]], x["quantity"]))
    return plan
