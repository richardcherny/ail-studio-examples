When a CSV join turns $200 into $350
==================================

Synthetic, local-only tutorial. Requires Python 3.9 or later. No third-party
packages are needed. From this directory, use python3 (or your matching
Python command on Windows):

python3 join_guard.py customers_exact.csv --unsafe-demo
python3 join_guard.py customers_valid.csv
python3 -m unittest -v

The first command deliberately runs an unchecked inner join: 3 orders totaling
20000 cents become 5 rows totaling 35000 cents. An exact duplicate customer
row matches two orders twice. The valid command preserves 3 rows and 20000
cents, with segment totals Business=5000 and Retail=15000. It prints a readable
report containing summaries and CSV rows; the complete output is not a CSV file.

Try these separately; each intentionally exits with code 2, writes REFUSED to
stderr, and leaves stdout empty:

python3 join_guard.py customers_exact.csv
python3 join_guard.py customers_conflict.csv
python3 join_guard.py customers_missing.csv

Expected diagnoses: C001 has an exact duplicate, C001 has conflicting duplicates,
and C002 is missing, respectively. The normal path validates customer-key
uniqueness and order coverage before constructing a lookup or printing a report.
Exact and conflicting duplicates are both rejected, including unused duplicate
customers. Unique unused customers are allowed. Multiple orders may legitimately
reference one customer.

What to inspect
---------------
join_guard.py: read_csv/load_orders validate the input shape; safe_join checks
uniqueness and coverage; unsafe_inner_join exposes multiplication and row loss.
test_join_guard.py: 11 tests cover those paths, malformed input, negative/zero
cents, and a case where duplicate-plus-missing errors leave count and total
unchanged. Matching totals alone cannot establish a correct join.

Limits
------
This is an in-memory, bounded CSV example, not a streaming or database engine.
Headers must match exactly. Keys are compared as raw strings: whitespace and
case are not normalized, and uniqueness does not prove a key names the intended
real-world customer. Amounts are integer cents; negative and zero values are
allowed. Validation does not establish business accuracy or authorization.
Duplicate problems are reported before missing-key problems. The unsafe flag is
only for demonstrating failure and deliberately bypasses the join contract.

The repository README records the current executed runtime. Python 3.9 is the
stated source requirement, not a claim of a fresh 3.9 compatibility test.
