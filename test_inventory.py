import os, tempfile, unittest
os.environ["INVENTORY_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
import init_db, inventory_db as db


class T(unittest.TestCase):
    def setUp(self): init_db.init(reset=True)

    def test_low_and_out(self):
        rows = db.get_low_stock_products()
        st = {r["sku"]: r["status"] for r in rows}
        self.assertEqual(st["HDP-001"], "OUT_OF_STOCK")
        self.assertEqual(st["LAP-001"], "LOW_STOCK")
        self.assertNotIn("LAP-002", st)

    def test_boundary_equal_reorder_is_low(self):
        db.update_stock("LAP-002", 5)  # reorder_level = 5
        self.assertEqual(db.get_stock_by_sku("LAP-002")["status"], "LOW_STOCK")

    def test_category_available(self):
        skus = {r["sku"] for r in db.search_products(category="electronics", only_available=True)}
        self.assertIn("LAP-001", skus); self.assertNotIn("HDP-001", skus)

    def test_price_stock(self):
        r = db.get_stock_by_sku("lap-001")
        self.assertEqual((r["price"], r["quantity"]), (45999, 3))

    def test_update(self):
        r = db.update_stock("LAP-001", 25)
        self.assertEqual((r["quantity"], r["previous_quantity"], r["status"]), (25, 3, "IN_STOCK"))
        with self.assertRaises(ValueError): db.update_stock("LAP-001", -1)
        with self.assertRaises(ValueError): db.update_stock("NOPE", 1)

    def test_add(self):
        r = db.add_product("Electronics", "Wireless Mouse", "MOU-101", "Default", 799, 50)
        self.assertEqual((r["quantity"], r["price"], r["category_name"]), (50, 799, "Electronics"))
        with self.assertRaises(ValueError): db.add_product("Electronics", "X", "MOU-101", "d", 1, 1)

    def test_sql_injection_safe(self):
        self.assertEqual(db.search_products(query="'; DROP TABLE Products;--"), [])
        self.assertTrue(db.search_products())


class Advanced(T):
    def test_adjust(self):
        r = db.adjust_stock("LAP-002", -2, "sale")
        self.assertEqual((r["quantity"], r["previous_quantity"]), (10, 12))
        with self.assertRaises(ValueError): db.adjust_stock("LAP-002", -100)
        with self.assertRaises(ValueError): db.adjust_stock("LAP-002", 0)

    def test_history(self):
        db.update_stock("LAP-001", 25, "restock")
        h = db.get_stock_history("LAP-001")
        self.assertEqual((h[0]["old_quantity"], h[0]["new_quantity"], h[0]["delta"], h[0]["reason"]), (3, 25, 22, "restock"))
        self.assertGreater(len(h), 1)  # seeded sales history is also present

    def test_summary(self):
        s = db.get_inventory_summary()
        self.assertEqual(s["total_skus"], 12)
        self.assertEqual(s["by_status"], {"IN_STOCK": 5, "LOW_STOCK": 4, "OUT_OF_STOCK": 3})

    def test_restock_plan(self):
        plan = db.suggest_restock()
        self.assertEqual(plan[0]["priority"], "CRITICAL")
        lap = next(p for p in plan if p["sku"] == "LAP-001")
        self.assertEqual(lap["suggested_order_qty"], 7)   # target 10 - 3
        self.assertEqual(lap["priority"], "HIGH")          # ~6 days of cover

    def test_fuzzy_sku(self):
        with self.assertRaises(ValueError) as cm: db.get_stock_by_sku("LAP-01")
        self.assertIn("LAP-001", str(cm.exception))

    def test_dashboard(self):
        import dashboard
        path = dashboard.generate(os.path.join(tempfile.mkdtemp(), "d.html"))
        with open(path, encoding="utf-8") as f:
            self.assertIn("Smart restock plan", f.read())


if __name__ == "__main__":
    unittest.main()
