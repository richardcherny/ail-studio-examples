When a CSV join turns $200 into $350
==================================

Adding customer segments should not change which orders appear in a report or
how much they are worth. The relationship here is many orders to one customer:
every order must match exactly one customer row. A repeated lookup key breaks
that contract, even when both copies contain identical information.

The failure, row by row
----------------------
The synthetic orders.csv contains three orders totaling $200 (20000 cents):

order_id,customer_id,amount_cents
O101,C001,10000
O102,C001,5000
O103,C002,5000

In customers_exact.csv, C001 appears twice:

customer_id,segment
C001,Retail
C001,Retail
C002,Business

An unchecked inner join emits one row for every match. Both C001 orders match
twice, so their combined $150 is counted a second time. C002 still matches once.
The resulting $350 is not new revenue; it is duplicated rows. The demo prints:

input: rows=3 total_cents=20000
joined: rows=5 total_cents=35000
order_id,customer_id,amount_cents,segment
O101,C001,10000,Retail
O101,C001,10000,Retail
O102,C001,5000,Retail
O102,C001,5000,Retail
O103,C002,5000,Business
segment_totals_cents: {'Business': 5000, 'Retail': 30000}

Reproduce the failure, then enforce the contract
-----------------------------------------------
Synthetic, local-only tutorial. Requires Python 3.9 or later. No third-party
packages are needed. To get the complete example at the tested code revision,
run these commands in a terminal with Git installed:

git clone https://github.com/richardcherny/ail-studio-examples.git
cd ail-studio-examples
git checkout 5cad58b665423141334ce18ae54db97911045c67
cd join-validation

The checkout selects a fixed snapshot (Git may call this a detached HEAD), so
later repository changes cannot alter this reproduction. Then use python3
(or your matching Python command on Windows):

python3 join_guard.py customers_exact.csv --unsafe-demo
python3 join_guard.py customers_valid.csv
python3 -m unittest -v

The first command deliberately bypasses validation to reproduce the output
above. The second uses customers_valid.csv, which has one row per customer,
and preserves all three orders and 20000 cents. Its segment totals are
Business=5000 and Retail=15000. Both commands print a readable report containing
summaries and CSV rows; the complete output is not a CSV file.

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

Why totals can look right while the join is wrong
------------------------------------------------
Consider two orders: A belongs to C001 and is worth 100 cents; B belongs to
C002 and is also worth 100 cents. Now give the lookup two rows for C001 and
no row for C002. An unchecked inner join returns A twice and drops B.
The input and output both have two rows totaling 200 cents. Those matching
summaries hide the fact that one order disappeared and another was copied.

That is why this example checks two different requirements before joining:
there must be at most one lookup row for each customer key, and every order's
customer key must have a match. Several orders may share one customer; the
lookup must still supply exactly one segment for each of those orders.
The test named test_unchanged_count_and_total_can_hide_duplicate_plus_missing
makes this counterexample executable. The valid-join test checks the actual
output records, rather than trusting only a count or total.

These checks establish the relationship encoded by the keys. They cannot
detect a unique but incorrectly assigned customer ID or an inaccurate segment.
Those need an authoritative source or separate business checks.

Limits
------
This is an in-memory, bounded CSV example, not a streaming or database engine.
Headers must match exactly. Keys are compared as raw strings: whitespace and
case are not normalized, and uniqueness does not prove a key names the intended
real-world customer. Amounts are integer cents; negative and zero values are
allowed. Validation does not establish business accuracy or authorization.
Duplicate problems are reported before missing-key problems. The unsafe flag is
only for demonstrating failure and deliberately bypasses the join contract.

The demo commands, all three refusal cases and all 11 tests were independently
reproduced on Linux with Python 3.12.14 on 2026-10-05. Python 3.9 is the stated
source requirement, not a claim of a fresh 3.9 compatibility test.
