When a Contact's parent Account changes in a CSV migration
==========================================================

A Salesforce Contact belongs to at most one Account. A CSV migration can keep
the contact row and still point it at a different Account, leave AccountId
blank, or drop the contact. Row counts can still look fine. This example
compares a source Contact CSV with a migrated Contact CSV and lists the source
rows whose parent Account changed or went missing.

Synthetic, local-only example. Requires Python 3.9 or later. No third-party
packages or network access are needed to run it. From a clone of this
repository:

git clone https://github.com/richardcherny/ail-studio-examples.git
cd ail-studio-examples/salesforce-parent-check

Then use python3 (on Windows, py -3 or your Python 3.9+ command):

python3 parent_check.py source_contacts.csv migrated_contacts.csv
python3 parent_check.py source_contacts.csv migrated_contacts_clean.csv
python3 -m unittest -v

The first command checks five source contacts and prints three flags. It exits
0 because the files were readable; the flags are the result.

checked: 5
flagged: 3
contact_id,status,source_account_id,migrated_account_id
C-1002,changed,A-200,A-515
C-1003,missing,A-310,
C-1005,missing,A-440,

C-1002 still exists, but its parent moved from A-200 to A-515. C-1003 is
present with a blank account_id. C-1005 is absent from the migrated file, so
its parent A-440 is missing. C-1001 is unchanged. C-1004 keeps account A-440;
only the account name text differs, and names are not compared. C-1006 exists
only after migration and is not a source parent to check.

The second command uses migrated_contacts_clean.csv. Every source parent is
unchanged, the rows are in a different order, and C-1006 is an extra migrated
contact. The report is checked: 5, flagged: 0, with a header and no flag rows.

Invalid files exit 2, write REFUSED to stderr, and leave stdout empty. Try a
duplicate contact id or a renamed header to see that.

What is compared
----------------
parent_check.py matches rows on contact_id. Surrounding whitespace is removed
first. The remaining account_id text is compared exactly, including case.

status is changed when both sides have a contact and the account ids differ,
including a source row with no parent that gains one. status is missing when
the source parent was non-blank and the migrated account_id is blank or the
contact row is gone. A source contact that had no parent is not flagged when
the migrated parent is still blank or the contact row is absent. Contacts that
appear only in the migrated file are ignored. last_name and account_name are
carried for reading and are not part of the parent check.

Headers must be exactly:

contact_id,last_name,account_id,account_name

contact_id and last_name are required. account_id and account_name may be
blank. contact_id must be unique in each file. These are invented ids and
names, not a Salesforce export.

Limits
------
This is an in-memory check of two Contact files. It does not call Salesforce,
resolve Account names, follow other lookups, or compare fields besides the
parent account id. Equal ids do not prove the Account record itself migrated
correctly. A unique but wrong contact_id will not match the intended person.
Duplicate ids are refused rather than merged. The sample files are synthetic.

The commands above and all 10 tests were run on Linux with Python 3.12.3 on
2026-10-26.

Full tool
---------
RecordBridge is the CSV migration reconciliation tool from AIL Studio ($49):

https://ailstudio.gumroad.com/l/ufgfjf?utm_source=github
