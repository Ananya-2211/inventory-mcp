"""Inventory MCP server (stdio).  Run: python server.py"""
import json
import pathlib
import webbrowser
from mcp.server.fastmcp import FastMCP
import inventory_db as db
import dashboard

mcp = FastMCP("inventory")


def _ok(data):  return json.dumps({"ok": True, "data": data}, indent=2)
def _err(e):    return json.dumps({"ok": False, "error": str(e)})


# ----- required tools -----
@mcp.tool()
def search_products(query: str = "", sku: str = "", category: str = "", only_available: bool = False) -> str:
    """Search products by name (partial), exact SKU, and/or category. Filters combine with AND.
    Set only_available=true to hide out-of-stock items (e.g. 'list available products in Electronics')."""
    try:   return _ok(db.search_products(query, sku, category, only_available))
    except Exception as e: return _err(e)


@mcp.tool()
def get_low_stock_products() -> str:
    """Return every variant that is out of stock (quantity = 0) or low stock (0 < quantity <= reorder_level).
    Each row has a 'status' of OUT_OF_STOCK or LOW_STOCK."""
    try:   return _ok(db.get_low_stock_products())
    except Exception as e: return _err(e)


@mcp.tool()
def get_stock_by_sku(sku: str) -> str:
    """Get price, stock quantity, reorder level and status for one SKU, e.g. 'LAP-001'.
    On a typo the error suggests the closest SKUs."""
    try:   return _ok(db.get_stock_by_sku(sku))
    except Exception as e: return _err(e)


@mcp.tool()
def update_stock(sku: str, quantity: int, reason: str = "manual update") -> str:
    """Set the stock quantity of a SKU to an absolute value (>= 0). Returns previous and new quantity.
    Use adjust_stock instead for relative changes like 'sold 3' or 'received 20'."""
    try:   return _ok(db.update_stock(sku, quantity, reason))
    except Exception as e: return _err(e)


@mcp.tool()
def add_product(category_name: str, product_name: str, sku: str, variant_name: str,
                price: float, initial_stock: int, description: str = "", reorder_level: int = 10) -> str:
    """Add a new product variant with initial stock. Creates the category/product if missing; reuses them
    if they exist (so you can add a new variant). SKU must be unique."""
    try:   return _ok(db.add_product(category_name, product_name, sku, variant_name, price,
                                     initial_stock, description, reorder_level))
    except Exception as e: return _err(e)


# ----- advanced tools -----
@mcp.tool()
def adjust_stock(sku: str, delta: int, reason: str = "adjustment") -> str:
    """Add or remove units relative to current stock: delta=-3 means 'sold 3', delta=+20 means 'received 20'.
    Refuses to take stock below zero. Always pass a short reason (e.g. 'sale', 'supplier delivery', 'damaged')."""
    try:   return _ok(db.adjust_stock(sku, delta, reason))
    except Exception as e: return _err(e)


@mcp.tool()
def get_stock_history(sku: str, limit: int = 20) -> str:
    """Audit trail for a SKU: every change with old/new quantity, reason and timestamp, newest first."""
    try:   return _ok(db.get_stock_history(sku, limit))
    except Exception as e: return _err(e)


@mcp.tool()
def get_inventory_summary() -> str:
    """Business overview: number of SKUs, total units, total stock value (INR),
    counts by status (in/low/out of stock) and value by category."""
    try:   return _ok(db.get_inventory_summary())
    except Exception as e: return _err(e)


@mcp.tool()
def suggest_restock() -> str:
    """Smart reorder plan for low/out-of-stock items: priority (CRITICAL/HIGH/MEDIUM) based on stock and recent
    sales speed, days of cover, suggested order quantity and estimated cost. Most urgent first."""
    try:   return _ok(db.suggest_restock())
    except Exception as e: return _err(e)


@mcp.tool()
def open_dashboard() -> str:
    """Generate the visual inventory dashboard (HTML) and open it in the user's browser."""
    try:
        path = dashboard.generate()
        webbrowser.open(pathlib.Path(path).as_uri())
        return _ok({"dashboard_file": path, "note": "Opened in the default browser."})
    except Exception as e: return _err(e)


# ----- MCP prompt + resource -----
@mcp.prompt()
def restock_report() -> str:
    """Ready-made prompt: manager-ready restock report."""
    return ("Call get_inventory_summary and suggest_restock, then write a short report for a store manager: "
            "headline numbers, what to reorder first and why, and the estimated total spend.")


@mcp.resource("inventory://summary")
def summary_resource() -> str:
    """Live inventory summary."""
    return _ok(db.get_inventory_summary())


if __name__ == "__main__":
    mcp.run(transport="stdio")
