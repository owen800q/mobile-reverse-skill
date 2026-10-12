#!/usr/bin/env python3
"""Tests for scripts/js_rpc_inventory.py: GraphQL operations and tRPC procedures from text."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "js_rpc_inventory.py"
sys.path.insert(0, str(SCRIPT.parent))

import js_rpc_inventory as rpc  # noqa: E402

HASH = "ab" * 32
GRAPHQL_JS = """const Q = gql`
  query GetUser($id: ID!, $first: Int = 5) @cached {
    user(id: $id) { name }
  }
`;
const M = "mutation Save($input: SaveInput!){save(input:$input){ok}}";
const E = "\\n  query Escaped {\\n  me { id }\\n}";
fetch("/graphql", {body: JSON.stringify({operationName: "Persisted", extensions: {persistedQuery: {version: 1, sha256Hash: "%s"}}})});
const doc = {kind: "Document", definitions: [{kind: "OperationDefinition", operation: "subscription", name: {kind: "Name", value: "OnTick"}, variableDefinitions: []}]};
const prose = "query results are cached";
const broken = "query Open {
;
""" % HASH
TRPC_JS = """import {createTRPCClient, httpBatchLink} from "@trpc/client";
const client = createTRPCClient({links: [httpBatchLink({url: "https://api.example.test/trpc"})]});
client.user.byId.query({id: 1});
client.auth.login.mutate({});
apollo.query({query: Q});
const x = trpc.posts.list.useQuery();
trpc.posts.create.useMutation();
trpc.posts.list.useQuery();
this.db.users.query();
api.endpoints.getThing.query();
"""
PLAIN_JS = """import {useQuery} from "react-query";
db.items.query("select 1");
store.cache.mutate();
other.thing.subscribe(() => 1);
const r = useQuery(["k"], fn);
"""


class RpcInventoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "src"
        self.root.mkdir()
        (self.root / "gql.js").write_text(GRAPHQL_JS, encoding="utf-8")
        (self.root / "trpc.js").write_text(TRPC_JS, encoding="utf-8")
        (self.root / "plain.js").write_text(PLAIN_JS, encoding="utf-8")
        nm = self.root / "node_modules" / "dep"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text('const Q = "query Hidden { a }";', encoding="utf-8")
        self.result = rpc.scan(str(self.root))
        self.graphql = self.result["graphql"]
        self.procs = {(p["path"], p["kind"]): p for p in self.result["trpc"]["procedures"]}

    def tearDown(self):
        self._tmp.cleanup()

    def by_name(self, name, kind=None):
        return [g for g in self.graphql if g.get("name") == name and (kind is None or g["kind"] == kind)]

    def test_template_literal_operation_keeps_variables_and_location(self):
        (op,) = self.by_name("GetUser")
        self.assertEqual((op["kind"], op["mechanism"], op["file"], op["line"]),
                         ("query", "literal", "gql.js", 1))
        self.assertEqual([(v["name"], v["type"]) for v in op["variables"]],
                         [("id", "ID!"), ("first", "Int")])
        self.assertEqual(len(op["text_sha256"]), 64)
        self.assertIn("user(id: $id)", op["text"])

    def test_string_literal_mutation_is_found(self):
        (op,) = self.by_name("Save")
        self.assertEqual(op["kind"], "mutation")
        self.assertEqual(op["variables"], [{"name": "input", "type": "SaveInput!"}])

    def test_escaped_newline_header_is_found(self):
        (op,) = self.by_name("Escaped")
        self.assertEqual(op["kind"], "query")

    def test_precompiled_operation_definition_is_found(self):
        (op,) = self.by_name("OnTick")
        self.assertEqual((op["kind"], op["mechanism"]), ("subscription", "precompiled"))

    def test_operation_name_and_persisted_hash_are_separate_leads(self):
        (name,) = self.by_name("Persisted")
        self.assertEqual(name["kind"], "operation-name")
        hashes = [g for g in self.graphql if g["kind"] == "persisted-query"]
        self.assertEqual([h["sha256"] for h in hashes], [HASH])

    def test_prose_unterminated_and_dependency_text_are_not_operations(self):
        names = {g.get("name") for g in self.graphql}
        self.assertNotIn("results", names)
        self.assertNotIn("Open", names)
        self.assertNotIn("Hidden", names)

    def test_trpc_vanilla_calls_need_a_marker_and_a_bound_root_or_long_path(self):
        self.assertIn(("user.byId", "query"), self.procs)
        self.assertIn(("auth.login", "mutation"), self.procs)

    def test_trpc_hooks_are_grouped_by_path_with_use_counts(self):
        listing = self.procs[("posts.list", "query")]
        self.assertEqual(listing["use_count"], 2)
        self.assertEqual({u["method"] for u in listing["uses"]}, {"useQuery"})
        self.assertIn(("posts.create", "mutation"), self.procs)

    def test_lookalikes_are_not_procedures(self):
        paths = {p for p, _ in self.procs}
        self.assertNotIn("users", paths)
        self.assertFalse([p for p in paths if "endpoints" in p])
        self.assertFalse([p for p in paths if p.startswith(("db.", "store.", "other."))])
        self.assertEqual(self.result["counts"]["trpc_procedures"], 4)

    def test_plain_files_without_a_marker_only_allow_hook_shapes(self):
        # useQuery(["k"]) has no member path; db.items.query needs a tRPC marker.
        self.assertFalse([p for p in self.procs.values() if p["uses"][0]["file"] == "plain.js"])

    def test_link_url_is_recorded(self):
        (link,) = self.result["trpc"]["links"]
        self.assertEqual((link["link"], link["url"], link["file"]),
                         ("httpBatchLink", "https://api.example.test/trpc", "trpc.js"))

    def test_cli_writes_a_private_file_and_limitations(self):
        out = Path(self._tmp.name) / "o" / "rpc.json"
        done = subprocess.run([sys.executable, str(SCRIPT), str(self.root), "--out", str(out)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["counts"], self.result["counts"])
        self.assertTrue(data["limitations"])
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)

    def test_missing_directory_is_an_input_error(self):
        done = subprocess.run([sys.executable, str(SCRIPT), str(Path(self._tmp.name) / "nope"),
                               "--out", str(Path(self._tmp.name) / "x.json")],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("not found", done.stderr)

    def test_large_minified_line_finishes(self):
        (self.root / "big.js").write_text("a.b.c" * 200_000 + ";" + '"' * 50_000, encoding="utf-8")
        rpc.scan(str(self.root))


if __name__ == "__main__":
    unittest.main()
