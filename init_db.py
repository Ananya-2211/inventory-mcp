"""Create the schema and load sample data:  python init_db.py [--reset]"""
import os, sys, sqlite3
HERE = os.path.dirname(os.path.abspath(__file__))
from inventory_db import db_path

# (category, product, description, [(sku, variant, price, qty, reorder_level)])
SEED = [
    ("Electronics", "Laptop", "14-inch business laptop", [
        ("LAP-001", "8GB / 256GB", 45999, 3, 5),      # low stock
        ("LAP-002", "16GB / 512GB", 64999, 12, 5)]),  # available
    ("Electronics", "Bluetooth Headphones", "Over-ear, noise cancelling", [
        ("HDP-001", "Black", 2999, 0, 10),            # out of stock
        ("HDP-002", "White", 2999, 40, 10)]),
    ("Electronics", "USB-C Charger", "65W fast charger", [
        ("CHG-001", "65W", 1499, 8, 10)]),            # low stock
    ("Accessories", "Laptop Bag", "Water-resistant 15.6-inch bag", [
        ("BAG-001", "Grey", 1299, 25, 8),
        ("BAG-002", "Navy", 1299, 0, 8)]),           # out of stock
    ("Furniture", "Office Chair", "Ergonomic mesh chair", [
        ("CHR-001", "Standard", 7499, 6, 5)]),
    ("Furniture", "Standing Desk", "Height-adjustable desk", [
        ("DSK-001", "120cm", 18999, 2, 3)]),          # low stock
    ("Stationery", "Notebook", "A5 ruled, 200 pages", [
        ("NTB-001", "Blue", 149, 150, 30),
        ("NTB-002", "Red", 149, 20, 30)]),            # low stock
    ("Stationery", "Gel Pen", "Pack of 10", [
        ("PEN-001", "Black", 199, 0, 25)]),           # out of stock
]

# Illustrative sales history so restock suggestions have velocity data: (sku, delta, days_ago, reason)
HISTORY = [("LAP-001", -4, 25, "sale"), ("LAP-001", -5, 10, "sale"), ("LAP-001", -6, 4, "sale"),
           ("HDP-001", -30, 12, "sale"), ("CHG-001", -14, 9, "sale"),
           ("NTB-002", -60, 15, "sale"), ("DSK-001", -1, 6, "sale")]


def init(path=None, reset=False):
    path = path or db_path()
    if reset and os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    with open(os.path.join(HERE, "schema.sql")) as f:
        conn.executescript(f.read())
    if conn.execute("SELECT COUNT(*) FROM Categories").fetchone()[0] == 0:
        for cat, prod, desc, variants in SEED:
            conn.execute("INSERT OR IGNORE INTO Categories(category_name) VALUES (?)", (cat,))
            cid = conn.execute("SELECT category_id FROM Categories WHERE category_name=?", (cat,)).fetchone()[0]
            pid = conn.execute("INSERT INTO Products(category_id, product_name, description) VALUES (?,?,?)",
                               (cid, prod, desc)).lastrowid
            for sku, vname, price, qty, reorder in variants:
                vid = conn.execute("INSERT INTO ProductVariants(product_id, sku, variant_name, price) VALUES (?,?,?,?)",
                                   (pid, sku, vname, price)).lastrowid
                conn.execute("INSERT INTO Inventory(variant_id, quantity, reorder_level) VALUES (?,?,?)",
                             (vid, qty, reorder))
        for sku, delta, days, reason in HISTORY:
            vid, qty = conn.execute("SELECT v.variant_id, i.quantity FROM ProductVariants v "
                                    "JOIN Inventory i USING(variant_id) WHERE v.sku=?", (sku,)).fetchone()
            conn.execute("INSERT INTO StockMovements(variant_id, old_quantity, new_quantity, delta, reason, created_at) "
                         "VALUES (?,?,?,?,?, datetime('now', ?))",
                         (vid, qty - delta, qty, delta, reason, f"-{days} days"))
    conn.commit(); conn.close()
    return path


if __name__ == "__main__":
    print("Database ready:", init(reset="--reset" in sys.argv))
