"""Generates a self-contained dashboard.html (no internet needed) from the live database.
Run: python dashboard.py   (or ask Claude: 'open the inventory dashboard')"""
import html, os
import inventory_db as db

HERE = os.path.dirname(os.path.abspath(__file__))
inr = lambda v: f"₹{v:,.0f}"
e = lambda v: html.escape(str(v))


def generate(path: str | None = None) -> str:
    s, plan = db.get_inventory_summary(), db.suggest_restock()
    with db.connect() as conn:
        moves = conn.execute("SELECT m.created_at, v.sku, m.delta, m.reason FROM StockMovements m "
                             "JOIN ProductVariants v USING(variant_id) ORDER BY m.movement_id DESC LIMIT 8").fetchall()
    st = s["by_status"]
    mx = max([c["value"] for c in s["by_category"]] or [1])
    cat_rows = "".join(
        f'<div class="bar"><span>{e(c["category_name"])}</span><div class="track"><i style="width:{c["value"]/mx*100:.0f}%"></i></div>'
        f'<b>{inr(c["value"])}</b></div>' for c in s["by_category"])
    plan_rows = "".join(
        f'<tr><td>{e(p["sku"])}</td><td>{e(p["product_name"])} <small>{e(p["variant_name"])}</small></td>'
        f'<td>{p["quantity"]}</td><td><span class="chip {p["priority"]}">{p["priority"]}</span></td>'
        f'<td>{"—" if p["days_of_cover"] is None else p["days_of_cover"]}</td>'
        f'<td>+{p["suggested_order_qty"]}</td><td>{inr(p["estimated_cost_at_list_price"])}</td></tr>' for p in plan)
    move_rows = "".join(
        f'<li><b>{e(m["sku"])}</b> <span class="{"neg" if m["delta"] < 0 else "pos"}">{m["delta"]:+d}</span> '
        f'<small>{e(m["reason"])} · {e(m["created_at"][:16])}</small></li>' for m in moves)
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Inventory Dashboard</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--text:#1c2330;--muted:#6b7585;--line:#e5e8ee;--accent:#3b6cf6;
--ok:#1f9d55;--warn:#d98a00;--bad:#d64545}}
@media (prefers-color-scheme:dark){{:root{{--bg:#12151b;--card:#1b1f27;--text:#e8ebf0;--muted:#97a1b1;--line:#2b313c;--accent:#7b9bff}}}}
*{{box-sizing:border-box}}body{{margin:0;padding:24px;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,Segoe UI,sans-serif}}
h1{{margin:0 0 4px;font-size:24px}}h2{{font-size:16px;margin:0 0 12px}}.sub{{color:var(--muted);margin-bottom:20px}}
.grid{{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));margin-bottom:16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}}
.kpi b{{display:block;font-size:26px}}.kpi span{{color:var(--muted);font-size:13px}}
.bar{{display:grid;grid-template-columns:110px 1fr 90px;gap:10px;align-items:center;margin:8px 0}}
.track{{background:var(--line);border-radius:6px;height:10px}}.track i{{display:block;height:100%;background:var(--accent);border-radius:6px}}
.wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:8px;border-bottom:1px solid var(--line);white-space:nowrap}}
th{{color:var(--muted);font-weight:600;font-size:13px}}small{{color:var(--muted)}}
.chip{{padding:2px 8px;border-radius:99px;font-size:12px;font-weight:600;color:#fff}}
.CRITICAL{{background:var(--bad)}}.HIGH{{background:var(--warn)}}.MEDIUM{{background:var(--accent)}}
ul{{list-style:none;margin:0;padding:0}}li{{padding:6px 0;border-bottom:1px solid var(--line)}}.neg{{color:var(--bad)}}.pos{{color:var(--ok)}}
.two{{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}}
</style></head><body>
<h1>Inventory Dashboard</h1><div class="sub">Live snapshot from inventory.db</div>
<div class="grid">
<div class="card kpi"><b>{s["total_skus"]}</b><span>SKUs tracked</span></div>
<div class="card kpi"><b>{s["total_units"]:,}</b><span>Units in stock</span></div>
<div class="card kpi"><b>{inr(s["total_stock_value_inr"])}</b><span>Stock value (list price)</span></div>
<div class="card kpi"><b style="color:var(--ok)">{st["IN_STOCK"]}</b><span>In stock</span></div>
<div class="card kpi"><b style="color:var(--warn)">{st["LOW_STOCK"]}</b><span>Low stock</span></div>
<div class="card kpi"><b style="color:var(--bad)">{st["OUT_OF_STOCK"]}</b><span>Out of stock</span></div></div>
<div class="two"><div class="card"><h2>Stock value by category</h2>{cat_rows}</div>
<div class="card"><h2>Recent stock movements</h2><ul>{move_rows}</ul></div></div>
<div class="card" style="margin-top:16px"><h2>Smart restock plan</h2><div class="wrap"><table>
<tr><th>SKU</th><th>Product</th><th>Qty</th><th>Priority</th><th>Days of cover</th><th>Order</th><th>Est. cost</th></tr>{plan_rows}</table></div></div>
</body></html>"""
    path = path or os.path.join(HERE, "dashboard.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path


if __name__ == "__main__":
    import webbrowser, pathlib
    p = generate()
    print("Dashboard written:", p)
    webbrowser.open(pathlib.Path(p).as_uri())
