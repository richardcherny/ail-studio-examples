import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import join_guard as j

ROOT = Path(__file__).resolve().parent


class JoinGuardTests(unittest.TestCase):
    def setUp(self):
        self.orders = j.load_orders(ROOT / "orders.csv")
        self.valid = self.customers("valid")

    def customers(self, name):
        return j.read_csv(ROOT / f"customers_{name}.csv", ["customer_id", "segment"])

    def test_valid_many_orders_to_one_customer_preserves_each_order(self):
        joined = j.safe_join(self.orders, self.valid)
        self.assertEqual(joined, [
            {"order_id": "O101", "customer_id": "C001", "amount_cents": 10000, "segment": "Retail"},
            {"order_id": "O102", "customer_id": "C001", "amount_cents": 5000, "segment": "Retail"},
            {"order_id": "O103", "customer_id": "C002", "amount_cents": 5000, "segment": "Business"},
        ])
        self.assertEqual(j.summary(joined), "rows=3 total_cents=20000")
        self.assertNotIn("segment", self.orders[0])

    def test_exact_duplicate_multiplies_orders_and_total(self):
        joined = j.unsafe_inner_join(self.orders, self.customers("exact"))
        self.assertEqual([r["order_id"] for r in joined], ["O101", "O101", "O102", "O102", "O103"])
        self.assertEqual(j.summary(joined), "rows=5 total_cents=35000")
        with self.assertRaisesRegex(ValueError, r"C001 \(exact, 2 rows\)"):
            j.safe_join(self.orders, self.customers("exact"))

    def test_conflicting_duplicates_refused_in_both_orders(self):
        rows = self.customers("conflict")
        for customers in (rows, rows[::-1]):
            with self.subTest(customers=customers):
                with self.assertRaisesRegex(ValueError, r"C001 \(conflicting, 2 rows\)"):
                    j.safe_join(self.orders, customers)

    def test_missing_match_refused_instead_of_dropping_order(self):
        customers = self.customers("missing")
        self.assertEqual(j.summary(j.unsafe_inner_join(self.orders, customers)), "rows=2 total_cents=15000")
        with self.assertRaisesRegex(ValueError, "missing customer_id: C002"):
            j.safe_join(self.orders, customers)

    def test_unchanged_count_and_total_can_hide_duplicate_plus_missing(self):
        orders = [{"order_id": "A", "customer_id": "C001", "amount_cents": 100},
                  {"order_id": "B", "customer_id": "C002", "amount_cents": 100}]
        customers = [{"customer_id": "C001", "segment": "Retail"}] * 2
        joined = j.unsafe_inner_join(orders, customers)
        self.assertEqual(j.summary(joined), j.summary(orders))
        self.assertEqual([r["order_id"] for r in joined], ["A", "A"])
        with self.assertRaises(ValueError):
            j.safe_join(orders, customers)

    def test_unused_duplicate_still_breaks_dimension_contract(self):
        extra = {"customer_id": "UNUSED", "segment": "Retail"}
        with self.assertRaisesRegex(ValueError, "UNUSED"):
            j.safe_join(self.orders, self.valid + [extra, extra])

    def test_unique_unused_customer_is_allowed(self):
        extra = {"customer_id": "UNUSED", "segment": "Retail"}
        self.assertEqual(j.safe_join(self.orders, self.valid + [extra]), j.safe_join(self.orders, self.valid))

    def test_three_row_mixed_duplicate_is_conflicting(self):
        rows = self.customers("exact") + [{"customer_id": "C001", "segment": "Business"}]
        with self.assertRaisesRegex(ValueError, r"C001 \(conflicting, 3 rows\)"):
            j.safe_join(self.orders, rows)

    def test_cli_refusal_emits_no_report(self):
        for name in ("exact", "conflict", "missing"):
            out, err = io.StringIO(), io.StringIO()
            with self.subTest(name=name), patch("sys.argv", ["join_guard.py", str(ROOT / f"customers_{name}.csv"), "--orders", str(ROOT / "orders.csv")]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(j.main(), 2)
            self.assertEqual(out.getvalue(), "")
            self.assertTrue(err.getvalue().startswith("REFUSED:"))

    def test_input_validation(self):
        bad = [
            "order_id,customer_id,amount_cents\nA,C001,1\nA,C001,2\n",
            "order_id,customer_id,amount_cents\nA,C001,1.5\n",
            "order_id,customer_id,amount_cents\nA,,100\n",
            "order_id,customer_id,amount_cents\nA,C001\n",
            "order_id,customer_id,amount_cents\nA,C001,100,extra\n",
            "order_id,customer_id,value\nA,C001,100\n",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orders.csv"
            for text in bad:
                with self.subTest(text=text):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        j.load_orders(path)

    def test_zero_and_negative_cents_preserved(self):
        orders = [dict(self.orders[0], amount_cents=0), dict(self.orders[1], amount_cents=-50)]
        self.assertEqual(j.summary(j.safe_join(orders, self.valid)), "rows=2 total_cents=-50")


if __name__ == "__main__":
    unittest.main()
