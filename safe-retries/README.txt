Safe retries without duplicate reservations
==========================================

Synthetic, local-only tutorial. Requires Python 3.12 or later with sqlite3;
the code uses sqlite3.connect(..., autocommit=True). No third-party packages or
network access are needed. From this directory, use python3 (or your matching
Python command on Windows):

python3 safe_retries.py
python3 fault_injection.py
python3 -m unittest -v test_safe_retries

The demo reserves 3 of 10 BOLT units. Both the first result and replay contain
qty=3, status=reserved, stock_after=7. Reusing the key with qty=4 raises a
KeyConflict; the final database has stock=7 and receipts=1. Each demo runs in
a temporary directory that is cleaned up afterward.

The fault probe prints:

before COMMIT: (10, 0)
after retry: (7, 1)
after reply loss: (7, 1)
replayed stock_after: 7
after replay: (7, 1)

The pairs are (available stock, receipt count). A failure after writes but before
COMMIT rolls both back. If the caller loses a reply after COMMIT, a retry with the
same key and payload returns the saved response. The visible probe simulates
reply loss by raising an exception; the tests also use abrupt child-process exits
before commit and after a committed reservation.

What makes the retry safe here
------------------------------
safe_retries.py: reserve acquires a SQLite write transaction with BEGIN IMMEDIATE.
It checks the stored key/payload, updates stock if appropriate, and stores the
response in that same transaction before COMMIT. A different payload conflicts.
A stored rejection is replayed too, even if stock is subsequently replenished.
A replay is the historical response, not a fresh stock query; a new key requests
a new action. Callers must reuse the original key when retrying the same action.

The 10 tests cover rollback, both process-exit boundaries, changed payload,
two concurrent same-key calls, lock timeout followed by retry, historical replay,
rejected replay, key uniqueness, and invalid inputs. See the repository README
for the executed runtime.

Limits
------
The stock change and receipt must remain in the same local SQLite database and
transaction. This does not make external payments, messages, or HTTP calls atomic.
No network retry loop, backoff policy, authentication, key expiry, multi-tenant
key scoping, or production monitoring is implemented. Keys are nonempty strings;
quantities are integers 1 through 10 for one fixed SKU. Lock contention may raise
SQLITE_BUSY; callers must decide whether and when to retry. No power-loss or
filesystem-failure durability test is claimed. The concurrency test uses two
threads and is not a load test. Never use real customer data for fault injection.
