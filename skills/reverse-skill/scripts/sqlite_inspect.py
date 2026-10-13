#!/usr/bin/env python3
"""Inspect one SQLite database offline: an object inventory, one table's schema, and bounded row samples with lossless values.

Usage:
    sqlite_inspect.py DB --out FILE [--sql] [--table NAME [--column NAME ...] [--row-limit N]]

DB is a SQLite 3 database that is quiescent: stop the writer, or take the database and its -wal
file from the application's own backup. A copy of a live pair is not an atomic snapshot.

The database and an existing sibling DB-wal are copied into a private temporary directory before
SQLite opens them, so the originals are never opened, locked or checkpointed. SQLite runs with
query_only on and trusted_schema off. Views, triggers and arbitrary SQL are not executed. Virtual
tables are listed but not read. A non-empty rollback journal (DB-journal) is refused, because its
recovery is outside this inspection; an empty one is accepted.

Default output is the object inventory: type, name, table, root page, and a row count for each
ordinary table. --sql adds the stored CREATE statements verbatim. --table NAME selects one ordinary
table: its visible columns (hidden and generated columns are marked), its indexes and triggers, and
a row sample. --column repeats to choose exact column names in the given order. --row-limit (default
20) bounds the sample; row order is unspecified, so a sample says nothing about omitted rows.

Values are lossless. Integers are decimal strings, so every signed 64-bit value survives JSON. Reals
keep their number, with Infinity, -Infinity and -0 spelled out. Text carries its decoded string,
its bytes as hex, and whether the bytes are valid UTF-8. Blobs are hex. SQL NULL is a tagged value.

Output: JSON in FILE (mode 0600) and a summary on stdout. Exit codes: 0 done; 2 usage or input
error, including a missing or non-regular file, a file that is not a SQLite 3 database, a database
and WAL over 256 MiB together, a non-empty rollback journal, an unknown table, column or row limit,
or an output path that is a symbolic link. Standard library only; reuses jni_map.py's output writer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jni_map as jm  # noqa: E402  (InputError and the private output writer)

MAX_TOTAL_BYTES = 256 * 1024 * 1024
DEFAULT_ROW_LIMIT = 20
MAX_ROW_LIMIT = 100000
SQLITE_HEADER = b"SQLite format 3\x00"
VIRTUAL_RE = re.compile(r"^\s*CREATE\s+VIRTUAL\s+TABLE", re.IGNORECASE)
# hidden column flags from PRAGMA table_xinfo: 0 visible, 1 hidden (virtual), 2 and 3 generated.
VISIBLE_HIDDEN = (0, 2, 3)

LIMITATIONS = [
    "Only a quiescent database and its -wal are a consistent pair. A copy taken while the writer runs can mix states",
    "Encrypted databases, repair, and recovery of a non-empty rollback journal are outside this inspection and are refused or reported as errors",
    "Views, triggers and virtual tables are listed, not executed. Their rows are not read. Shadow tables of a virtual table are not separated from ordinary tables",
    "Row order is unspecified. A row sample of --row-limit rows does not prove anything about the rows it omits",
    "Row counts run COUNT(*) on each ordinary table, so large databases take proportionally longer",
    "Object names that are not valid UTF-8 are listed with their hex name and cannot be selected",
]


class SqliteInspectError(jm.InputError):
    """Input the tool refuses rather than reporting partial evidence for."""


def _quote(identifier):
    """A SQL identifier, quoted. Only names already read from the schema are quoted."""
    return '"' + identifier.replace('"', '""') + '"'


def _identity(path, copy_to=None):
    """SHA-256 and byte count of a file. With copy_to, the same single read also writes the private copy."""
    digest = hashlib.sha256()
    size = 0
    handle = os.open(copy_to, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600) if copy_to else None
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
                size += len(chunk)
                if handle is not None:
                    os.write(handle, chunk)
    finally:
        if handle is not None:
            os.close(handle)
    return {"name": os.path.basename(path), "sha256": digest.hexdigest(), "size": size}


def _regular(path, label):
    if os.path.islink(path):
        raise SqliteInspectError("%s is a symbolic link; refusing to read through it" % label)
    if not os.path.isfile(path):
        raise SqliteInspectError("%s is not a regular file" % label)


def check_inputs(db_path):
    """Refuse anything that is not a plain SQLite 3 database pair within the byte budget."""
    _regular(db_path, "database")
    with open(db_path, "rb") as fh:
        if fh.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
            raise SqliteInspectError("not a SQLite 3 database (no plain header; an encrypted file is not supported)")
    total = os.path.getsize(db_path)
    wal_path = db_path + "-wal"
    journal_path = db_path + "-journal"
    wal_present = os.path.lexists(wal_path)
    if wal_present:
        _regular(wal_path, "WAL file")
        total += os.path.getsize(wal_path)
    journal = "absent"
    if os.path.lexists(journal_path):
        _regular(journal_path, "rollback journal")
        if os.path.getsize(journal_path) > 0:
            raise SqliteInspectError("a non-empty rollback journal is present; its recovery is outside this inspection")
        journal = "empty"
    if total > MAX_TOTAL_BYTES:
        raise SqliteInspectError("database and WAL exceed %d bytes" % MAX_TOTAL_BYTES)
    return wal_present, journal


def _text(raw):
    """Decode a name or label as strict UTF-8; None when the bytes are not valid UTF-8."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _cell(value, kind):
    """One lossless cell from a value and its typeof() tag."""
    if kind == "null":
        return {"type": "null"}
    if kind == "integer":
        return {"type": "integer", "value": str(value)}
    if kind == "real":
        if math.isnan(value):
            return {"type": "real", "value": "NaN"}
        if math.isinf(value):
            return {"type": "real", "value": "Infinity" if value > 0 else "-Infinity"}
        if value == 0 and math.copysign(1.0, value) < 0:
            return {"type": "real", "value": "-0"}
        return {"type": "real", "value": value}
    if kind == "text":
        text = _text(value)
        return {"type": "text", "value": text, "hex": value.hex(), "valid_utf8": text is not None}
    return {"type": "blob", "hex": value.hex(), "length": len(value)}


def _open_copy(db_path, tmp):
    """Copy the database (and WAL) privately, then open the copy read-only in effect."""
    target = os.path.join(tmp, "snapshot.sqlite")
    db_id = _identity(db_path, copy_to=target)
    wal_path = db_path + "-wal"
    wal_id = None
    if os.path.lexists(wal_path):
        wal_id = _identity(wal_path, copy_to=target + "-wal")
    conn = sqlite3.connect(target)
    conn.text_factory = bytes
    conn.execute("PRAGMA trusted_schema = OFF")
    conn.execute("PRAGMA query_only = ON")
    return conn, db_id, wal_id


def _objects(conn, include_sql):
    rows = conn.execute("SELECT type, name, tbl_name, rootpage, sql FROM sqlite_master ORDER BY type, name").fetchall()
    objects = []
    for kind, name, tbl_name, rootpage, sql in rows:
        name_text = _text(name)
        tbl_text = _text(tbl_name)
        sql_text = _text(sql) if sql is not None else None
        entry_kind = kind.decode("ascii")
        if entry_kind == "table" and sql is not None and VIRTUAL_RE.match(sql_text or ""):
            entry_kind = "virtual"
        item = {
            "type": entry_kind,
            "name": name_text,
            "name_hex": None if name_text is not None else name.hex(),
            "table": tbl_text,
            "rootpage": rootpage,
            "selectable": name_text is not None and entry_kind == "table" and not name_text.startswith("sqlite_"),
        }
        if include_sql:
            item["sql"] = sql_text
        objects.append(item)
    for item in objects:
        if item["type"] == "table" and item["selectable"]:
            item["row_count"] = conn.execute("SELECT COUNT(*) FROM %s" % _quote(item["name"])).fetchone()[0]
    return objects


def _table_columns(conn, table):
    rows = conn.execute("PRAGMA table_xinfo(%s)" % _quote(table)).fetchall()
    columns = []
    for cid, name, ctype, notnull, dflt, pk, hidden in rows:
        name_text = _text(name)
        columns.append({
            "cid": cid,
            "name": name_text,
            "declared_type": _text(ctype) if ctype else "",
            "not_null": bool(notnull),
            "primary_key_position": pk,
            "hidden": hidden,
            "visible": hidden in VISIBLE_HIDDEN,
        })
    return columns


def _sample(conn, table, column_names, row_limit):
    select = ", ".join("%s, typeof(%s)" % (_quote(c), _quote(c)) for c in column_names)
    sql = "SELECT %s FROM %s LIMIT %d" % (select, _quote(table), row_limit + 1)
    fetched = conn.execute(sql).fetchall()
    more = len(fetched) > row_limit
    rows = []
    for raw in fetched[:row_limit]:
        cells = []
        for index in range(len(column_names)):
            value = raw[2 * index]
            kind = raw[2 * index + 1].decode("ascii")
            cells.append(_cell(value, kind))
        rows.append(cells)
    return {"row_limit": row_limit, "returned": len(rows), "more_rows_observed": more, "rows": rows}


def inspect_database(db_path, table=None, columns=None, row_limit=DEFAULT_ROW_LIMIT, include_sql=False):
    if row_limit < 1 or row_limit > MAX_ROW_LIMIT:
        raise SqliteInspectError("--row-limit must be between 1 and %d" % MAX_ROW_LIMIT)
    if columns and not table:
        raise SqliteInspectError("--column needs --table")
    wal_present, journal = check_inputs(db_path)
    with tempfile.TemporaryDirectory(prefix="sqlite-inspect-") as tmp:
        os.chmod(tmp, 0o700)
        conn, db_id, wal_id = _open_copy(db_path, tmp)
        try:
            objects = _objects(conn, include_sql)
            result = {
                "tool": "sqlite_inspect.py",
                "source": {"database": db_id, "wal": wal_id, "journal": journal},
                "sqlite_version": sqlite3.sqlite_version,
                "objects": objects,
                "selected_table": None,
                "coverage": "complete",
                "coverage_gaps": [],
                "limitations": LIMITATIONS,
            }
            if any(o["name"] is None for o in objects):
                result["coverage_gaps"].append("an object name is not valid UTF-8 and is listed by hex only")
                result["coverage"] = "partial"
            if table is not None:
                result["selected_table"] = _select_table(conn, objects, table, columns, row_limit)
        finally:
            conn.close()
    result["source"]["wal_present"] = wal_present
    return result


def _select_table(conn, objects, table, columns, row_limit):
    match = [o for o in objects if o["name"] == table]
    if not match:
        raise SqliteInspectError("no object named %r in the database" % table)
    entry = match[0]
    if entry["type"] == "virtual":
        raise SqliteInspectError("%r is a virtual table; its rows are not read" % table)
    if not entry["selectable"]:
        raise SqliteInspectError("%r is not an ordinary selectable table" % table)
    schema = _table_columns(conn, table)
    visible = [c["name"] for c in schema if c["visible"]]
    if columns:
        missing = [c for c in columns if c not in visible]
        if missing:
            raise SqliteInspectError("no visible column named %r in %r" % (missing[0], table))
        chosen = list(columns)
    else:
        chosen = visible
    indexes = conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? ORDER BY name",
                           (table,)).fetchall()
    triggers = conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name = ? ORDER BY name",
                            (table,)).fetchall()
    selected = {
        "name": table,
        "columns": schema,
        "indexes": [{"name": _text(n), "sql": _text(s) if s is not None else None} for n, s in indexes],
        "triggers": [{"name": _text(n), "sql": _text(s) if s is not None else None} for n, s in triggers],
        "column_order": chosen,
    }
    if not chosen:
        selected["rows"] = {"row_limit": row_limit, "returned": 0, "more_rows_observed": False, "rows": []}
        return selected
    selected["rows"] = _sample(conn, table, chosen, row_limit)
    return selected


def _summary(result):
    out = {
        "database": result["source"]["database"]["sha256"],
        "wal_present": result["source"]["wal_present"],
        "journal": result["source"]["journal"],
        "objects": len(result["objects"]),
        "coverage": result["coverage"],
    }
    selected = result["selected_table"]
    if selected:
        out["table"] = selected["name"]
        out["returned_rows"] = selected["rows"]["returned"]
        out["more_rows_observed"] = selected["rows"]["more_rows_observed"]
    return out


def run(db_path, out, table=None, columns=None, row_limit=DEFAULT_ROW_LIMIT, include_sql=False):
    result = inspect_database(db_path, table, columns, row_limit, include_sql)
    jm.write_output(out, result)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Inspect one SQLite database offline: inventory, a table's schema and bounded rows.")
    ap.add_argument("database", help="SQLite 3 database file; a sibling -wal file is read as part of the pair")
    ap.add_argument("--out", required=True, help="output JSON file (mode 0600)")
    ap.add_argument("--sql", action="store_true", help="include the stored CREATE statements in the inventory")
    ap.add_argument("--table", default=None, help="select one ordinary table: schema and a row sample")
    ap.add_argument("--column", action="append", default=None, help="visible column to sample (repeatable, in order)")
    ap.add_argument("--row-limit", type=int, default=DEFAULT_ROW_LIMIT,
                    help="rows to sample from --table (default %d)" % DEFAULT_ROW_LIMIT)
    args = ap.parse_args(argv)
    try:
        result = run(args.database, args.out, args.table, args.column, args.row_limit, args.sql)
    except (jm.InputError, OSError, ValueError, sqlite3.Error) as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2
    print(json.dumps(_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
