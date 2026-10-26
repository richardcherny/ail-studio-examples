"""Compare source and migrated Contact CSVs and flag parent Account changes."""

import argparse
import csv
import io
import sys
from pathlib import Path

FIELDS = ["contact_id", "last_name", "account_id", "account_name"]
REPORT_FIELDS = [
    "contact_id",
    "status",
    "source_account_id",
    "migrated_account_id",
]


def read_contacts(path):
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"{path.name}: expected header {FIELDS}")
        rows = []
        seen = set()
        for number, row in enumerate(reader, start=2):
            if None in row or any(row[field] is None for field in FIELDS):
                raise ValueError(f"{path.name}: invalid CSV record {number}")
            cleaned = {field: row[field].strip() for field in FIELDS}
            if not cleaned["contact_id"] or not cleaned["last_name"]:
                raise ValueError(f"{path.name}: invalid CSV record {number}")
            if cleaned["contact_id"] in seen:
                raise ValueError(
                    f"{path.name}: duplicate contact_id: {cleaned['contact_id']}"
                )
            seen.add(cleaned["contact_id"])
            rows.append(cleaned)
    return rows


def parent_flags(source_rows, migrated_rows):
    """Return source rows whose parent Account changed or went missing.

    Contacts are matched on contact_id. A blank migrated account_id, or a
    source contact absent from the migrated file, is missing when the source
    row had an account_id. Different non-blank account ids are changed,
    including a parent that was blank in the source and filled in later.
    account_name is not compared. Contacts that exist only in the migrated
    file are ignored.
    """
    migrated = {row["contact_id"]: row for row in migrated_rows}
    flags = []
    for row in source_rows:
        other = migrated.get(row["contact_id"])
        source_account = row["account_id"]
        migrated_account = "" if other is None else other["account_id"]
        if migrated_account == "":
            if source_account == "":
                continue
            status = "missing"
        elif migrated_account != source_account:
            status = "changed"
        else:
            continue
        flags.append(
            {
                "contact_id": row["contact_id"],
                "status": status,
                "source_account_id": source_account,
                "migrated_account_id": migrated_account,
            }
        )
    flags.sort(key=lambda item: item["contact_id"])
    return flags


def render_report(source_rows, flags):
    buffer = io.StringIO()
    buffer.write(f"checked: {len(source_rows)}\n")
    buffer.write(f"flagged: {len(flags)}\n")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(REPORT_FIELDS)
    for flag in flags:
        writer.writerow([flag[field] for field in REPORT_FIELDS])
    return buffer.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Contact CSV from the source system")
    parser.add_argument("migrated", type=Path, help="Contact CSV after migration")
    args = parser.parse_args(argv)
    try:
        source_rows = read_contacts(args.source)
        migrated_rows = read_contacts(args.migrated)
        flags = parent_flags(source_rows, migrated_rows)
    except (ValueError, OSError, csv.Error) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(render_report(source_rows, flags))
    return 0


if __name__ == "__main__":
    sys.exit(main())
