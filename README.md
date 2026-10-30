# Inventory Management Agent (MCP + Claude)

Chat with your inventory in natural language. A custom **MCP server** (Python, SQLite) exposes inventory tools; an AI client (Claude Desktop **or** the included `client.py`) interprets requests and calls them.

```
User ─► Claude (client.py / Claude Desktop) ─► MCP server (server.py) ─► inventory_db.py ─► SQLite
                                                        └─► dashboard.py ─► dashboard.html
```

## Schema
`Categories 1─* Products 1─* ProductVariants 1─1 Inventory` (see `schema.sql`), plus an extra `StockMovements` audit table.
Stock rules: **out of stock** = qty 0 · **low stock** = 0 < qty ≤ reorder_level.

## Setup
```bash
pip install -r requirements.txt     # note: mcp is pinned to 1.x (2.x renamed FastMCP)
python init_db.py --reset           # creates inventory.db with sample data + sales history
python -m unittest -v               # 20 tests
python demo.py                      # the 5 required prompts' tool calls, no LLM needed
python dashboard.py                 # opens the visual dashboard
```

## Run
- **Custom client:** `export ANTHROPIC_API_KEY=...` then `python client.py`
- **Claude Desktop:** copy `claude_desktop_config.example.json` into your Claude config (use your real absolute paths), restart Claude.

## MCP tools
| Tool | Purpose | |
|---|---|---|
| `search_products` | Search by name / SKU / category | required |
| `get_low_stock_products` | Low-stock + out-of-stock | required |
| `get_stock_by_sku` | Price & quantity (typo-tolerant) | required |
| `update_stock` | Set absolute stock | required |
| `add_product` | Create product + variant + stock | required |
| `adjust_stock` | Relative change ("sold 3", "received 20"); blocks negative stock | extra |
| `get_stock_history` | Audit trail per SKU | extra |
| `get_inventory_summary` | Units, ₹ value, status & category breakdown | extra |
| `suggest_restock` | Prioritised reorder plan using sales velocity | extra |
| `open_dashboard` | Generates & opens the HTML dashboard | extra |

Also: an MCP **prompt** (`restock_report`) and an MCP **resource** (`inventory://summary`).

## Required sample prompts
1. Show all low-stock or out-of-stock products.
2. List available products in the Electronics category.
3. What is the price and stock quantity of SKU LAP-001?
4. Update the stock quantity of SKU LAP-001 to 25.
5. Add a Wireless Mouse under Electronics with SKU MOU-101, price ₹799, and stock quantity 50.

## Advanced prompts
- "We sold 2 units of LAP-002 today" · "Received 40 units of PEN-001 from the supplier"
- "Show the history of LAP-001"
- "Give me an inventory summary" · "What should I reorder first, and what will it cost?"
- "Open the inventory dashboard"
- "What's the stock of LAP-01?" (typo → suggests LAP-001)

## Design notes
- Parameterised SQL everywhere; inputs validated; tools return `{ok, data|error}` so the model can explain failures.
- Business logic lives in `inventory_db.py` (no MCP dependency), so it is testable and reusable.
- Every stock change is logged, so the system is auditable and sales velocity can drive restock advice.
- Restock cost uses list price as a proxy (the required schema has no cost-price column).
