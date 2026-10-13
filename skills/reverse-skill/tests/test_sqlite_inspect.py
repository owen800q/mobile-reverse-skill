#!/usr/bin/env python3
"""Tests for scripts/sqlite_inspect.py: inventory, schema, lossless samples, WAL pairs, journal refusal and output."""
import contextlib
import io
import json
import os
import shutil
import sqlite3
import stat
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import sqlite_inspect as si  # noqa: E402


def make_db(path):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE settings (key TEXT PRIMARY KEY, value BLOB, n INTEGER, r REAL);
        CREATE INDEX settings_n ON settings(n);
        CREATE TRIGGER settings_ai AFTER INSERT ON settings BEGIN SELECT 1; END;
        CREATE VIEW v_settings AS SELECT key FROM settings;
        CREATE TABLE gen (a INTEGER, b INTEGER GENERATED ALWAYS AS (a * 2) VIRTUAL);
    """)
    conn.execute("INSERT INTO settings VALUES ('token', X'DEADBEEF', ?, 1.5)", (2 ** 63 - 1,))
    conn.execute("INSERT INTO settings VALUES ('inf', NULL, -1, ?)", (float("inf"),))
    conn.execute("INSERT INTO settings VALUES ('negzero', X'', 0, -0.0)")
    conn.execute("INSERT INTO settings VALUES (CAST(X'FFFE41' AS TEXT), NULL, NULL, NULL)")
    conn.execute("INSERT INTO gen (a) VALUES (21)")
    conn.commit()
    conn.close()


def run_main(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = si.main(argv)
    return code, out.getvalue(), err.getvalue()


class SqliteCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sqlite-inspect-test-"))
        self.db = self.tmp / "app.sqlite"
        make_db(self.db)
        self.out = self.tmp / "out" / "sqlite.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def load(self):
        return json.loads(self.out.read_text(encoding="utf-8"))


class InventoryTests(SqliteCase):
    def test_inventory_lists_objects_and_row_counts_without_sql_by_default(self):
        code, out, _ = run_main([str(self.db), "--out", str(self.out)])
        self.assertEqual(code, 0)
        result = self.load()
        by_name = {o["name"]: o for o in result["objects"]}
        self.assertEqual(by_name["settings"]["type"], "table")
        self.assertEqual(by_name["settings"]["row_count"], 4)
        self.assertEqual(by_name["v_settings"]["type"], "view")
        self.assertNotIn("row_count", by_name["v_settings"])
        self.assertNotIn("sql", by_name["settings"])
        self.assertIsNone(result["selected_table"])
        self.assertEqual(result["coverage"], "complete")
        self.assertIn("objects", out.lower() + "objects")

    def test_sql_flag_keeps_the_stored_statement_verbatim(self):
        run_main([str(self.db), "--out", str(self.out), "--sql"])
        by_name = {o["name"]: o for o in self.load()["objects"]}
        self.assertIn("CREATE TABLE settings", by_name["settings"]["sql"])

    def test_virtual_table_is_listed_but_its_rows_are_refused(self):
        try:
            conn = sqlite3.connect(self.db)
            conn.execute("CREATE VIRTUAL TABLE docs USING fts5(body)")
            conn.commit()
            conn.close()
        except sqlite3.OperationalError:
            self.skipTest("this SQLite build has no FTS5")
        run_main([str(self.db), "--out", str(self.out)])
        by_name = {o["name"]: o for o in self.load()["objects"]}
        self.assertEqual(by_name["docs"]["type"], "virtual")
        code, _, err = run_main([str(self.db), "--out", str(self.out), "--table", "docs"])
        self.assertEqual(code, 2)
        self.assertIn("virtual table", err)


class SampleTests(SqliteCase):
    def test_selected_table_has_schema_indexes_triggers_and_lossless_cells(self):
        code, _, _ = run_main([str(self.db), "--out", str(self.out), "--table", "settings"])
        self.assertEqual(code, 0)
        selected = self.load()["selected_table"]
        self.assertEqual(selected["name"], "settings")
        self.assertEqual([i["name"] for i in selected["indexes"]], ["settings_n", "sqlite_autoindex_settings_1"])
        self.assertEqual([t["name"] for t in selected["triggers"]], ["settings_ai"])
        rows = selected["rows"]["rows"]
        token = rows[0]
        self.assertEqual(token[0], {"type": "text", "value": "token", "hex": b"token".hex(), "valid_utf8": True})
        self.assertEqual(token[1], {"type": "blob", "hex": "deadbeef", "length": 4})
        self.assertEqual(token[2], {"type": "integer", "value": str(2 ** 63 - 1)})
        self.assertEqual(token[3], {"type": "real", "value": 1.5})
        self.assertEqual(rows[1][3], {"type": "real", "value": "Infinity"})
        # SQLite stores -0.0 as 0.0, so the negative-zero spelling is checked on the cell decoder itself.
        self.assertEqual(si._cell(-0.0, "real"), {"type": "real", "value": "-0"})

    def test_malformed_utf8_text_keeps_its_bytes(self):
        run_main([str(self.db), "--out", str(self.out), "--table", "settings"])
        cell = self.load()["selected_table"]["rows"]["rows"][3][0]
        self.assertEqual(cell["type"], "text")
        self.assertFalse(cell["valid_utf8"])
        self.assertEqual(cell["hex"], "fffe41")
        self.assertIsNone(cell["value"])

    def test_column_selection_keeps_requested_order_and_generated_columns_are_selectable(self):
        code, _, _ = run_main([str(self.db), "--out", str(self.out), "--table", "gen",
                               "--column", "b", "--column", "a"])
        self.assertEqual(code, 0)
        selected = self.load()["selected_table"]
        self.assertEqual(selected["column_order"], ["b", "a"])
        self.assertEqual(selected["rows"]["rows"][0], [{"type": "integer", "value": "42"},
                                                       {"type": "integer", "value": "21"}])
        generated = {c["name"]: c for c in selected["columns"]}["b"]
        self.assertTrue(generated["visible"])
        self.assertIn(generated["hidden"], (2, 3))

    def test_row_limit_reports_more_rows_without_claiming_completeness(self):
        code, _, _ = run_main([str(self.db), "--out", str(self.out), "--table", "settings", "--row-limit", "2"])
        self.assertEqual(code, 0)
        rows = self.load()["selected_table"]["rows"]
        self.assertEqual(rows["returned"], 2)
        self.assertTrue(rows["more_rows_observed"])

    def test_unknown_table_and_column_are_refused(self):
        code, _, err = run_main([str(self.db), "--out", str(self.out), "--table", "missing"])
        self.assertEqual(code, 2)
        self.assertIn("no object named 'missing'", err)
        code, _, err = run_main([str(self.db), "--out", str(self.out), "--table", "settings", "--column", "nope"])
        self.assertEqual(code, 2)
        self.assertIn("no visible column named 'nope'", err)

    def test_view_and_sqlite_internal_tables_are_not_sampled(self):
        code, _, err = run_main([str(self.db), "--out", str(self.out), "--table", "v_settings"])
        self.assertEqual(code, 2)
        self.assertIn("not an ordinary selectable table", err)

    def test_column_without_table_is_refused_and_bad_row_limit_too(self):
        code, _, err = run_main([str(self.db), "--out", str(self.out), "--column", "key"])
        self.assertEqual(code, 2)
        self.assertIn("--column needs --table", err)
        code, _, err = run_main([str(self.db), "--out", str(self.out), "--table", "settings", "--row-limit", "0"])
        self.assertEqual(code, 2)
        self.assertIn("--row-limit must be between", err)


class SnapshotTests(SqliteCase):
    def test_wal_pair_is_read_and_the_original_is_not_modified(self):
        live = self.tmp / "live.sqlite"
        make_db(live)
        writer = sqlite3.connect(live)
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("INSERT INTO settings VALUES ('from-wal', X'00', 7, 2.0)")
        writer.commit()
        # Copy the pair while the writer is still open, as an acquisition would.
        pair = self.tmp / "pair.sqlite"
        shutil.copyfile(live, pair)
        shutil.copyfile(str(live) + "-wal", str(pair) + "-wal")
        writer.close()  # closing checkpoints the WAL into the live file
        before = live.read_bytes()
        code, _, _ = run_main([str(pair), "--out", str(self.out), "--table", "settings"])
        self.assertEqual(code, 0)
        result = self.load()
        self.assertTrue(result["source"]["wal_present"])
        self.assertIsNotNone(result["source"]["wal"])
        keys = [row[0]["value"] for row in result["selected_table"]["rows"]["rows"]]
        self.assertIn("from-wal", keys)
        self.assertEqual(before, live.read_bytes())

    def test_empty_journal_is_accepted_and_recorded(self):
        Path(str(self.db) + "-journal").write_bytes(b"")
        code, _, _ = run_main([str(self.db), "--out", str(self.out)])
        self.assertEqual(code, 0)
        self.assertEqual(self.load()["source"]["journal"], "empty")

    def test_non_empty_journal_is_refused(self):
        Path(str(self.db) + "-journal").write_bytes(b"\x00" * 512)
        code, _, err = run_main([str(self.db), "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("non-empty rollback journal", err)

    def test_non_sqlite_file_is_refused(self):
        plain = self.tmp / "plain.bin"
        plain.write_bytes(b"not a database at all, just bytes")
        code, _, err = run_main([str(plain), "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("not a SQLite 3 database", err)

    def test_symbolic_link_database_is_refused(self):
        link = self.tmp / "link.sqlite"
        os.symlink(self.db, link)
        code, _, err = run_main([str(link), "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("symbolic link", err)


class OutputTests(SqliteCase):
    def test_output_is_private_and_holds_no_absolute_paths(self):
        run_main([str(self.db), "--out", str(self.out), "--table", "settings"])
        self.assertEqual(stat.S_IMODE(os.stat(self.out).st_mode), 0o600)
        text = self.out.read_text(encoding="utf-8")
        self.assertNotIn(str(self.tmp), text)
        self.assertEqual(self.load()["source"]["database"]["name"], "app.sqlite")

    def test_symbolic_link_output_is_refused_and_its_target_is_untouched(self):
        victim = self.tmp / "victim.txt"
        victim.write_text("keep", encoding="utf-8")
        link = self.tmp / "link.json"
        os.symlink(victim, link)
        code, _, err = run_main([str(self.db), "--out", str(link)])
        self.assertEqual(code, 2)
        self.assertIn("symbolic link", err)
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep")

    def test_private_copies_are_removed_after_the_run(self):
        before = set(os.listdir(tempfile.gettempdir()))
        run_main([str(self.db), "--out", str(self.out), "--table", "settings"])
        leftover = [n for n in set(os.listdir(tempfile.gettempdir())) - before if n.startswith("sqlite-inspect-")]
        self.assertEqual(leftover, [])


if __name__ == "__main__":
    unittest.main()
