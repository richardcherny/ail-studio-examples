"""Visible tutorial probe: compare failure before and after COMMIT."""
from pathlib import Path
from tempfile import TemporaryDirectory
from safe_retries import initialize, reserve, snapshot


def fail_before_commit():
    raise RuntimeError("injected before COMMIT")


with TemporaryDirectory() as folder:
    db = Path(folder) / "before.db"
    initialize(db)
    try:
        reserve(db, "A", 3, before_commit=fail_before_commit)
    except RuntimeError:
        print("before COMMIT:", snapshot(db))
    reserve(db, "A", 3)
    print("after retry:", snapshot(db))

    db = Path(folder) / "after.db"
    initialize(db)
    try:
        reserve(db, "A", 3)  # Returns only after SQL COMMIT.
        raise TimeoutError("pretend the caller lost this reply")
    except TimeoutError:
        print("after reply loss:", snapshot(db))
    print("replayed stock_after:", reserve(db, "A", 3)["stock_after"])
    print("after replay:", snapshot(db))
