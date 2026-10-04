"""A bounded CSV join tutorial: validate before enriching or aggregating."""
import argparse
import csv
import re
import sys
from pathlib import Path


def read_csv(path, fields):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != fields:
            raise ValueError(f"{Path(path).name}: expected header {fields}")
        rows = list(reader)
    for number, row in enumerate(rows, start=2):
        if None in row or any(v is None or not v.strip() for v in row.values()):
            raise ValueError(f"{Path(path).name}: invalid CSV record {number}")
    return rows


def load_orders(path):
    rows = read_csv(path, ["order_id", "customer_id", "amount_cents"])
    seen = set()
    for row in rows:
        if row["order_id"] in seen:
            raise ValueError(f"duplicate order_id: {row['order_id']}")
        seen.add(row["order_id"])
        if not re.fullmatch(r"-?[0-9]+", row["amount_cents"]):
            raise ValueError(f"invalid integer cents: {row['amount_cents']}")
        row["amount_cents"] = int(row["amount_cents"])
    return rows


def unsafe_inner_join(orders, customers):
    # Intentionally reproduces all matching pairs, including duplicate matches.
    return [dict(order, segment=customer["segment"])
            for order in orders for customer in customers
            if order["customer_id"] == customer["customer_id"]]


def safe_join(orders, customers):
    groups = {}
    for customer in customers:
        groups.setdefault(customer["customer_id"], []).append(customer)
    problems = []
    for key, group in sorted(groups.items()):
        if len(group) > 1:
            kind = "exact" if all(r == group[0] for r in group) else "conflicting"
            problems.append(f"{key} ({kind}, {len(group)} rows)")
    if problems:
        raise ValueError("duplicate customer_id: " + "; ".join(problems))
    missing = sorted({r["customer_id"] for r in orders} - groups.keys())
    if missing:
        raise ValueError("missing customer_id: " + ", ".join(missing))
    # Only build a single-record lookup after uniqueness and coverage pass.
    index = {key: group[0] for key, group in groups.items()}
    return [dict(order, segment=index[order["customer_id"]]["segment"])
            for order in orders]


def summary(rows):
    return f"rows={len(rows)} total_cents={sum(r['amount_cents'] for r in rows)}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("customers", type=Path)
    parser.add_argument("--orders", type=Path, default=Path("orders.csv"))
    parser.add_argument("--unsafe-demo", action="store_true",
                        help="deliberately demonstrate an unchecked inner join")
    args = parser.parse_args()
    try:
        orders = load_orders(args.orders)
        customers = read_csv(args.customers, ["customer_id", "segment"])
        joined = (unsafe_inner_join if args.unsafe_demo else safe_join)(orders, customers)
    except (ValueError, OSError, csv.Error) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print("input: " + summary(orders))
    print("joined: " + summary(joined))
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["order_id", "customer_id", "amount_cents", "segment"])
    for row in joined:
        writer.writerow([row[k] for k in ["order_id", "customer_id", "amount_cents", "segment"]])
    totals = {}
    for row in joined:
        totals[row["segment"]] = totals.get(row["segment"], 0) + row["amount_cents"]
    print(f"segment_totals_cents: {dict(sorted(totals.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
