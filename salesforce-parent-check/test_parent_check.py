import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import parent_check as pc

ROOT = Path(__file__).resolve().parent
FIELDS = ["contact_id", "last_name", "account_id", "account_name"]


def write_csv(directory, name, body):
    path = Path(directory) / name
    path.write_text(body, encoding="utf-8")
    return path


class ParentCheckTests(unittest.TestCase):
    def setUp(self):
        self.source = pc.read_contacts(ROOT / "source_contacts.csv")
        self.migrated = pc.read_contacts(ROOT / "migrated_contacts.csv")
        self.clean = pc.read_contacts(ROOT / "migrated_contacts_clean.csv")

    def test_sample_flags_changed_blank_and_absent_parents(self):
        flags = pc.parent_flags(self.source, self.migrated)
        self.assertEqual(
            flags,
            [
                {
                    "contact_id": "C-1002",
                    "status": "changed",
                    "source_account_id": "A-200",
                    "migrated_account_id": "A-515",
                },
                {
                    "contact_id": "C-1003",
                    "status": "missing",
                    "source_account_id": "A-310",
                    "migrated_account_id": "",
                },
                {
                    "contact_id": "C-1005",
                    "status": "missing",
                    "source_account_id": "A-440",
                    "migrated_account_id": "",
                },
            ],
        )

    def test_same_parent_ignores_name_drift_order_and_extra_contacts(self):
        self.assertEqual(pc.parent_flags(self.source, self.clean), [])
        renamed = [dict(row) for row in self.clean if row["contact_id"] != "C-1006"]
        for row in renamed:
            if row["contact_id"] == "C-1004":
                row["account_name"] = "A different label"
        self.assertEqual(pc.parent_flags(self.source, renamed), [])

    def test_blank_source_parent_filled_in_is_changed(self):
        source = [{"contact_id": "C-9", "last_name": "Cho", "account_id": "", "account_name": ""}]
        migrated = [{"contact_id": "C-9", "last_name": "Cho", "account_id": "A-1", "account_name": "New Co"}]
        flags = pc.parent_flags(source, migrated)
        self.assertEqual(flags[0]["status"], "changed")
        self.assertEqual(flags[0]["migrated_account_id"], "A-1")

    def test_blank_parent_staying_blank_is_not_flagged(self):
        source = [{"contact_id": "C-9", "last_name": "Cho", "account_id": "", "account_name": ""}]
        self.assertEqual(pc.parent_flags(source, source), [])
        self.assertEqual(pc.parent_flags(source, []), [])

    def test_flags_are_sorted_by_contact_id(self):
        source = [
            {"contact_id": "C-2", "last_name": "B", "account_id": "A-1", "account_name": "One"},
            {"contact_id": "C-1", "last_name": "A", "account_id": "A-1", "account_name": "One"},
        ]
        migrated = [
            {"contact_id": "C-2", "last_name": "B", "account_id": "A-9", "account_name": "Nine"},
            {"contact_id": "C-1", "last_name": "A", "account_id": "", "account_name": ""},
        ]
        self.assertEqual(
            [row["contact_id"] for row in pc.parent_flags(source, migrated)],
            ["C-1", "C-2"],
        )

    def test_account_id_comparison_is_case_sensitive_after_strip(self):
        text = (
            "contact_id,last_name,account_id,account_name\n"
            "C-1,Cho, a-200 ,Northwind Labs\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_csv(directory, "contacts.csv", text)
            rows = pc.read_contacts(path)
        self.assertEqual(rows[0]["account_id"], "a-200")
        other = [dict(rows[0], account_id="A-200")]
        self.assertEqual(pc.parent_flags(rows, other)[0]["status"], "changed")
        padded = [dict(rows[0], account_id="a-200")]
        self.assertEqual(pc.parent_flags(rows, padded), [])

    def test_input_validation(self):
        bad = [
            "contact_id,last_name,account_id\nC-1,Cho,A-1\n",
            "contact_id,last_name,account_id,account_name\n,Cho,A-1,Northwind\n",
            "contact_id,last_name,account_id,account_name\nC-1,,A-1,Northwind\n",
            "contact_id,last_name,account_id,account_name\nC-1,Cho,A-1\n",
            "contact_id,last_name,account_id,account_name\nC-1,Cho,A-1,Northwind,extra\n",
            "contact_id,last_name,account_id,account_name\nC-1,Cho,A-1,Northwind\nC-1,Cho,A-2,Other\n",
            "id,last_name,account_id,account_name\nC-1,Cho,A-1,Northwind\n",
            "",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contacts.csv"
            for text in bad:
                with self.subTest(text=text):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        pc.read_contacts(path)

    def test_quoted_account_name_with_comma(self):
        text = (
            'contact_id,last_name,account_id,account_name\n'
            'C-1,Cho,A-1,"Northwind, Labs"\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            rows = pc.read_contacts(write_csv(directory, "contacts.csv", text))
        self.assertEqual(rows[0]["account_name"], "Northwind, Labs")

    def test_cli_sample_report_and_clean_file(self):
        code, out, err = self.run_cli(
            ROOT / "source_contacts.csv",
            ROOT / "migrated_contacts.csv",
        )
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(
            out,
            "\n".join(
                [
                    "checked: 5",
                    "flagged: 3",
                    "contact_id,status,source_account_id,migrated_account_id",
                    "C-1002,changed,A-200,A-515",
                    "C-1003,missing,A-310,",
                    "C-1005,missing,A-440,",
                    "",
                ]
            ),
        )
        code, out, err = self.run_cli(
            ROOT / "source_contacts.csv",
            ROOT / "migrated_contacts_clean.csv",
        )
        self.assertEqual((code, err), (0, ""))
        self.assertIn("checked: 5\nflagged: 0\n", out)
        self.assertNotIn("changed", out)
        self.assertNotIn("missing", out)

    def test_cli_refusal_emits_no_report(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = write_csv(
                directory,
                "bad.csv",
                "contact_id,last_name,account_id,account_name\nC-1,Cho,A-1,Northwind\nC-1,Cho,A-1,Northwind\n",
            )
            missing = Path(directory) / "missing.csv"
            for path in (bad, missing):
                with self.subTest(path=path.name):
                    code, out, err = self.run_cli(ROOT / "source_contacts.csv", path)
                    self.assertEqual(code, 2)
                    self.assertEqual(out, "")
                    self.assertTrue(err.startswith("REFUSED:"))

    def run_cli(self, source, migrated):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pc.main([str(source), str(migrated)])
        return code, out.getvalue(), err.getvalue()


if __name__ == "__main__":
    unittest.main()
