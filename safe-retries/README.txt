Safe retries without duplicate reservations
==========================================

A caller can lose confirmation after a reservation succeeds. Retrying as a new
reservation would reduce stock again. Here, the caller supplies a stable request
key, such as order-1042, and reuses it with the same quantity when retrying.
The program recognizes the key and returns the saved result without reducing
stock again. A new key means a new action; changing the quantity under
the old key is an error.

Synthetic, local-only tutorial. Requires Python 3.12 or later with sqlite3;
the code uses sqlite3.connect(..., autocommit=True). No third-party packages or
network access are needed to run the example. To obtain the tested code snapshot,
run these commands in a terminal with Git installed (cloning needs network access):

git clone https://github.com/richardcherny/ail-studio-examples.git
cd ail-studio-examples
git checkout 5cad58b665423141334ce18ae54db97911045c67
cd safe-retries

The checkout selects a fixed snapshot (Git may call this a detached HEAD).
Then use python3, or your matching Python 3.12+ command on Windows:

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
In safe_retries.py, reserve validates the key and quantity before opening the
transaction. A new request then follows this sequence:

1. BEGIN IMMEDIATE acquires the SQLite write transaction before any receipt
   lookup. SQLite permits only one write transaction at a time.
2. Look up the request key in receipts. If it exists, compare the saved payload:
   an identical payload selects the saved response; a different one raises
   KeyConflict. Neither path creates another reservation.
3. For a new key, reduce stock only if enough units remain. Build either the
   reserved response or an insufficient-stock rejection, then store that response
   with the key and payload in receipts.
4. COMMIT the stock change and receipt together, then return the response.
   An error before commit rolls the transaction back. A lost reply after commit
   leaves both the reservation and its receipt available for the retry.

For two callers using order-1042 with qty=3, starting from 10 units, the successful
interleaving is easy to follow:

- Caller A acquires the write transaction and finds no receipt.
- Caller B reaches BEGIN IMMEDIATE while A still holds the write transaction.
  B waits here, before reading receipts; if its lock wait times out, it receives
  SQLITE_BUSY and must retry later.
- A changes stock from 10 to 7, stores the response, and commits.
- B acquires the write transaction, finds A's receipt, checks the matching
  payload, and returns the saved stock_after=7 after committing its transaction.
  B does not subtract another three units. The database has one receipt.

If A rolls back instead, there is no committed receipt or stock change; B can
process the request as new. This ordering is why the receipt lookup belongs
inside the write transaction, not before it.

A stored rejection is replayed too, even if stock is subsequently replenished.
A replay is the historical response, not a fresh stock query; a new key requests
a new action. Callers must reuse the original key when retrying the same action.

Verification
------------
The demo, fault probe and all 10 tests were independently reproduced on Linux
with Python 3.12.14 and SQLite 3.53.1 on 2026-10-05. The tests cover rollback,
both process-exit boundaries, changed payload, two concurrent same-key calls,
lock timeout followed by retry, historical replay, rejected replay, key
uniqueness, and invalid inputs. This is the executed runtime, not a claim that
every Python 3.12+ and SQLite combination has been tested.

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

