# AIL Studio examples

Small, runnable Python tutorials about data correctness. Each includes synthetic inputs and tests. No third-party packages are needed to run them.

- [Join validation](join-validation/README.txt): see how duplicate lookup rows turn a $200 total into $350, then reject ambiguous or missing customer keys before producing a report.
- [Safe retries](safe-retries/README.txt): store a reservation and its receipt in one SQLite transaction so retrying the same request can return the original result without reducing stock again.
- [Salesforce parent check](salesforce-parent-check/README.txt): compare a source Contact CSV with a migrated Contact CSV and flag rows whose parent Account changed or went missing.

## Tools by AIL Studio

- [RecordBridge](https://ailstudio.gumroad.com/l/ufgfjf?utm_source=github&utm_medium=repo&utm_campaign=ufgfjf), a $49 CSV migration reconciliation tool
- [Trader's Edge Journal](https://ailstudio.gumroad.com/l/qsnmk?utm_source=github&utm_medium=repo&utm_campaign=qsnmk)
- [Prop Firm Rules Cheat Sheet](https://ailstudio.gumroad.com/l/cbjdeq?utm_source=github&utm_medium=repo&utm_campaign=cbjdeq) (free)

## Run the examples

Use Python 3.12 or later with the standard-library `sqlite3` module to run every example. Join validation and the Salesforce parent check use only the `csv` module and support Python 3.9 or later. The commands below use `python3`; on Windows, substitute `py -3.12` (or your Python 3.12+ command).

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

```sh
cd salesforce-parent-check
python3 parent_check.py source_contacts.csv migrated_contacts.csv
python3 parent_check.py source_contacts.csv migrated_contacts_clean.csv
python3 -m unittest -v
cd ..
```

The migrated file flags three of five source contacts: C-1002 changed parent from A-200 to A-515, C-1003 has a blank parent, and C-1005 is absent so its parent is missing. Both commands exit 0. The clean file preserves every source parent and flags nothing.

## Scope and verification

These are local teaching examples with invented customer, order, contact, and account identifiers and a fictional stock item. They are not production services, client integrations, or evidence of production reliability. The folder READMEs explain their assumptions and important limits. The examples are self-contained; no companion article is required to run them.

On 2026-10-04, the join-validation and safe-retries commands and the refusal examples were executed on Linux with Python 3.12.14 and SQLite 3.53.1: 11 join-validation tests and 10 safe-retries tests passed. On 2026-10-26, the Salesforce parent-check commands and its 10 tests were executed on Linux with Python 3.12.3. These are the executed runtimes, not a compatibility matrix. Each suite uses only local data; retry tests create fresh temporary databases and exercise child processes and two concurrent threads.

## License

Copyright 2026 Richard Cherny (AIL Studio). Released under the [MIT License](LICENSE).