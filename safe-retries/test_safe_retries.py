"""Behavioral evidence; fresh temporary database per test."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest

from safe_retries import KeyConflict, connect, initialize, reserve, snapshot


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "warehouse.db"
        initialize(self.db)

    def test_rollback_after_writes_then_retry(self):
        def fail():
            raise RuntimeError("injected before COMMIT")
        with self.assertRaisesRegex(RuntimeError, "injected"):
            reserve(self.db, "A", 3, before_commit=fail)
        self.assertEqual(snapshot(self.db), (10, 0))
        self.assertEqual(reserve(self.db, "A", 3)["stock_after"], 7)
        self.assertEqual(snapshot(self.db), (7, 1))

    def test_lost_reply_replays_in_new_process(self):
        script = """
import os, sys
from safe_retries import reserve
reserve(sys.argv[1], 'A', 3)
os._exit(23)  # Commit completed; caller never receives the result.
"""
        run = subprocess.run([sys.executable, "-c", script, str(self.db)],
                             cwd=Path(__file__).parent, capture_output=True)
        self.assertEqual(run.returncode, 23, run.stderr)
        self.assertEqual(run.stdout, b"")
        reply = subprocess.run(
            [sys.executable, "-c", "import json,sys; from safe_retries import "
             "reserve; print(json.dumps(reserve(sys.argv[1], 'A', 3)))",
             str(self.db)], cwd=Path(__file__).parent,
            capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(reply.stdout),
                         {"status": "reserved", "qty": 3, "stock_after": 7})
        self.assertEqual(snapshot(self.db), (7, 1))

    def test_process_exit_before_commit_then_retry(self):
        script = """
import os, sys
from safe_retries import reserve
reserve(sys.argv[1], 'A', 3, before_commit=lambda: os._exit(24))
"""
        run = subprocess.run([sys.executable, "-c", script, str(self.db)],
                             cwd=Path(__file__).parent, capture_output=True)
        self.assertEqual(run.returncode, 24, run.stderr)
        self.assertEqual(snapshot(self.db), (10, 0))
        reserve(self.db, "A", 3)
        self.assertEqual(snapshot(self.db), (7, 1))

    def test_changed_payload_conflicts_and_preserves_original(self):
        original = reserve(self.db, "A", 3)
        with self.assertRaises(KeyConflict):
            reserve(self.db, "A", 4)
        self.assertEqual(reserve(self.db, "A", 3), original)
        self.assertEqual(snapshot(self.db), (7, 1))

    def test_two_concurrent_duplicates_share_one_receipt(self):
        barrier = Barrier(2)
        def request(_):
            barrier.wait(timeout=5)
            return reserve(self.db, "A", 3, timeout=5)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(request, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(snapshot(self.db), (7, 1))

    def test_lock_timeout_has_no_effect_then_retry_succeeds(self):
        blocker = connect(self.db)
        try:
            blocker.execute("BEGIN IMMEDIATE")
            with self.assertRaises(sqlite3.OperationalError) as caught:
                reserve(self.db, "A", 3, timeout=0.01)
            self.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_BUSY)
        finally:
            blocker.execute("ROLLBACK")
            blocker.close()
        self.assertEqual(snapshot(self.db), (10, 0))
        reserve(self.db, "A", 3)
        self.assertEqual(snapshot(self.db), (7, 1))

    def test_new_key_means_new_action_but_replay_is_historical(self):
        original = reserve(self.db, "A", 3)
        reserve(self.db, "B", 3)
        self.assertEqual(reserve(self.db, "A", 3), original)
        self.assertEqual(original["stock_after"], 7)
        self.assertEqual(snapshot(self.db), (4, 2))

    def test_rejection_is_also_replayed(self):
        reserve(self.db, "A", 8)
        rejected = reserve(self.db, "B", 3)
        self.assertEqual(rejected, {"status": "rejected",
                                    "reason": "insufficient_stock"})
        con = connect(self.db)
        try:
            con.execute("UPDATE stock SET available = 10")
        finally:
            con.close()
        self.assertEqual(reserve(self.db, "B", 3), rejected)
        self.assertEqual(snapshot(self.db), (10, 2))

    def test_receipt_key_is_unique_in_database(self):
        reserve(self.db, "A", 3)
        con = connect(self.db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("INSERT INTO receipts VALUES ('A', '{}', '{}')")
        finally:
            con.close()
        self.assertEqual(snapshot(self.db), (7, 1))

    def test_invalid_input_leaves_no_receipt_or_stock_change(self):
        for key, qty in [("", 3), ("A", True), ("A", 0), ("A", 11), ("A", 3.0)]:
            with self.subTest(key=key, qty=qty):
                with self.assertRaises(ValueError):
                    reserve(self.db, key, qty)
        self.assertEqual(snapshot(self.db), (10, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
