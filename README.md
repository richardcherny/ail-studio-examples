# AIL Studio examples

Two small, runnable Python tutorials about data correctness. Each includes synthetic inputs, an intentionally exposed failure mode, and tests for the boundary that prevents it. No third-party packages or network access are needed.

- [Join validation](join-validation/README.txt): see how duplicate lookup rows turn a $200 total into $350, then reject ambiguous or missing customer keys before producing a report.
- [Safe retries](safe-retries/README.txt): store a reservation and its receipt in one SQLite transaction so retrying the same request can return the original result without reducing stock again.

## Run the examples

Use Python 3.12 or later with the standard-library `sqlite3` module to run both examples. Join validation alone supports Python 3.9 or later. The commands below use `python3`; on Windows, substitute `py -3.12` (or your Python 3.12+ command).

Start in the repository root. Run each block separately:

```sh
cd join-validation
python3 join_guard.py customers_exact.csv --unsafe-demo
python3 join_guard.py customers_valid.csv
python3 -m unittest -v
cd ..
```

The unsafe demonstration produces 5 joined rows totaling 35000 cents from 3 orders totaling 20000 cents. The valid join preserves all 3 orders and the 20000-cent total. See the folder README for commands that deliberately refuse invalid data.

```sh
cd safe-retries
python3 safe_retries.py
python3 fault_injection.py
python3 -m unittest -v test_safe_retries
cd ..
```

The first reservation and its replay both report `stock_after: 7`; only one receipt is stored. The fault probe shows rollback before commit and replay after a simulated lost reply.

## Scope and verification

These are local teaching examples with invented customer/order identifiers and a fictional stock item. They are not production services, client integrations, or evidence of production reliability. The folder READMEs explain their assumptions and important limits. The examples are self-contained; no companion article is required to run them.

On 2026-10-04, the commands above and the refusal examples were executed on Linux with Python 3.12.14 and SQLite 3.53.1: 11 join-validation tests and 10 safe-retries tests passed. This is one verified runtime, not a compatibility matrix. Each suite uses only local data; retry tests create fresh temporary databases and exercise child processes and two concurrent threads.

## License

Copyright 2026 Richard Cherny (AIL Studio). Released under the [MIT License](LICENSE).
