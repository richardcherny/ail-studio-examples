"""Synthetic, local-only reservation demo; Python 3.12+."""
import json
import sqlite3
from tempfile import TemporaryDirectory
from pathlib import Path


class KeyConflict(ValueError):
    pass


def connect(db, timeout=1.0):
    return sqlite3.connect(db, autocommit=True, timeout=timeout)


def initialize(db):
    con = connect(db)
    try:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS stock (
                sku TEXT PRIMARY KEY NOT NULL,
                available INTEGER NOT NULL CHECK (available >= 0)
            );
            CREATE TABLE IF NOT EXISTS receipts (
                key TEXT PRIMARY KEY NOT NULL,
                payload TEXT NOT NULL,
                response TEXT NOT NULL
            );
            INSERT OR IGNORE INTO stock VALUES ('BOLT', 10);
        """)
    finally:
        con.close()


def reserve(db, key, qty, *, before_commit=None, timeout=1.0):
    if not isinstance(key, str) or not key:
        raise ValueError("key must be a nonempty string")
    if type(qty) is not int or not 1 <= qty <= 10:
        raise ValueError("qty must be an integer from 1 to 10")
    payload = json.dumps({"sku": "BOLT", "qty": qty}, sort_keys=True)
    con = connect(db, timeout)
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT payload, response FROM receipts WHERE key = ?", (key,)
        ).fetchone()
        if row:
            if row[0] != payload:
                raise KeyConflict("key already used with a different payload")
            result = json.loads(row[1])
        else:
            changed = con.execute(
                "UPDATE stock SET available = available - ? "
                "WHERE sku = 'BOLT' AND available >= ?", (qty, qty)
            ).rowcount
            if changed:
                remaining = con.execute(
                    "SELECT available FROM stock WHERE sku = 'BOLT'"
                ).fetchone()[0]
                result = {"status": "reserved", "qty": qty,
                          "stock_after": remaining}
            else:
                result = {"status": "rejected", "reason": "insufficient_stock"}
            con.execute(
                "INSERT INTO receipts VALUES (?, ?, ?)",
                (key, payload, json.dumps(result, sort_keys=True))
            )
        if before_commit:
            before_commit()  # Test seam: after writes, before commit.
        con.execute("COMMIT")
        return result
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def snapshot(db):
    con = connect(db)
    try:
        return (con.execute("SELECT available FROM stock").fetchone()[0],
                con.execute("SELECT COUNT(*) FROM receipts").fetchone()[0])
    finally:
        con.close()


def demo():
    with TemporaryDirectory() as folder:
        db = Path(folder) / "warehouse.db"
        initialize(db)
        print("first:", json.dumps(reserve(db, "order-1042", 3), sort_keys=True))
        print("replay:", json.dumps(reserve(db, "order-1042", 3), sort_keys=True))
        try:
            reserve(db, "order-1042", 4)
        except KeyConflict as exc:
            print("conflict:", exc)
        stock, receipts = snapshot(db)
        print(f"database: stock={stock}, receipts={receipts}")


if __name__ == "__main__":
    demo()
