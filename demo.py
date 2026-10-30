"""Runs the 5 sample prompts' tool calls directly (no LLM) to demonstrate the data layer."""
import json, init_db, inventory_db as db
init_db.init(reset=True)
def show(title, data): print(f"\n### {title}\n{json.dumps(data, indent=1, default=str)[:900]}")
show('"Show all low-stock or out-of-stock products" -> get_low_stock_products',
     [(r["sku"], r["product_name"], r["quantity"], r["status"]) for r in db.get_low_stock_products()])
show('"List available products in Electronics" -> search_products(category, only_available)',
     [(r["sku"], r["product_name"], r["quantity"]) for r in db.search_products(category="Electronics", only_available=True)])
r = db.get_stock_by_sku("LAP-001"); show('"Price and stock of LAP-001" -> get_stock_by_sku', (r["price"], r["quantity"]))
r = db.update_stock("LAP-001", 25); show('"Update LAP-001 to 25" -> update_stock', (r["previous_quantity"], "->", r["quantity"], r["status"]))
r = db.add_product("Electronics", "Wireless Mouse", "MOU-101", "Default", 799, 50)
show('"Add Wireless Mouse MOU-101 ₹799 qty 50" -> add_product', (r["sku"], r["category_name"], r["price"], r["quantity"]))
