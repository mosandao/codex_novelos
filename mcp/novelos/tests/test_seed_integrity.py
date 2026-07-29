from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from novelos_mcp.errors import NovelOSError
from novelos_mcp.knowledge import KnowledgeStore
from novelos_mcp.seed_inventory import build_seed_inventory, hash_file


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class SeedIntegrityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.seed = self.root / "seed.db"
        with closing(sqlite3.connect(self.seed)) as connection:
            connection.execute(
                "CREATE TABLE kb_methods(id INTEGER PRIMARY KEY, title TEXT, body TEXT)"
            )
            connection.execute("INSERT INTO kb_methods VALUES (1, '递进冲突', '逐步提高阻碍强度')")
            connection.commit()
        self.inventory = self.root / "seed-inventory.json"
        self._write_inventory(build_seed_inventory(self.seed, "synthetic-test"))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_inventory(self, payload: dict[str, object]) -> None:
        self.inventory.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_valid_inventory_allows_read_only_queries(self) -> None:
        store = KnowledgeStore(self.seed, self.inventory)
        self.assertEqual("递进冲突", store.search("阻碍")[0]["title"])
        with self.assertRaises(sqlite3.OperationalError):
            with closing(store._connect()) as connection:
                connection.execute("DELETE FROM kb_methods")

    def test_seed_and_inventory_must_be_configured_together(self) -> None:
        with self.assertRaisesRegex(NovelOSError, "knowledge_unavailable"):
            KnowledgeStore(self.seed)
        with self.assertRaisesRegex(NovelOSError, "knowledge_unavailable"):
            KnowledgeStore(None, self.inventory)

    def test_inventory_schema_and_aggregate_counts_fail_closed(self) -> None:
        payload = build_seed_inventory(self.seed, "synthetic-test")
        payload["row_count"] = 2
        self._write_inventory(payload)
        with self.assertRaisesRegex(NovelOSError, "knowledge_inventory_invalid"):
            KnowledgeStore(self.seed, self.inventory)

    def test_exact_table_schema_and_content_hashes_are_required(self) -> None:
        expected = build_seed_inventory(self.seed, "synthetic-test")
        with closing(sqlite3.connect(self.seed)) as connection:
            connection.execute("CREATE TABLE kb_unexpected(id INTEGER PRIMARY KEY, body TEXT)")
            connection.commit()
        expected["source_hash"] = hash_file(self.seed)
        self._write_inventory(expected)
        with self.assertRaisesRegex(NovelOSError, "knowledge_integrity_error") as caught:
            KnowledgeStore(self.seed, self.inventory)
        self.assertIn("tables", caught.exception.details["mismatches"])

    def test_file_change_after_validation_blocks_future_reads(self) -> None:
        store = KnowledgeStore(self.seed, self.inventory)
        with closing(sqlite3.connect(self.seed)) as connection:
            connection.execute("INSERT INTO kb_methods VALUES (2, '反转', '改变目标')")
            connection.commit()
        with self.assertRaisesRegex(NovelOSError, "knowledge_integrity_error"):
            store.search("反转")

    def test_active_sqlite_sidecar_is_rejected(self) -> None:
        Path(f"{self.seed}-wal").write_bytes(b"active")
        with self.assertRaisesRegex(NovelOSError, "knowledge_integrity_error"):
            KnowledgeStore(self.seed, self.inventory)

    def test_sidecar_created_after_validation_blocks_future_reads(self) -> None:
        store = KnowledgeStore(self.seed, self.inventory)
        Path(f"{self.seed}-wal").write_bytes(b"active")
        with self.assertRaisesRegex(NovelOSError, "knowledge_integrity_error"):
            store.search("阻碍")

    def test_similar_non_knowledge_prefix_is_not_exposed(self) -> None:
        with closing(sqlite3.connect(self.seed)) as connection:
            connection.execute("CREATE TABLE kbx_hidden(id INTEGER PRIMARY KEY, body TEXT)")
            connection.commit()
        self._write_inventory(build_seed_inventory(self.seed, "synthetic-test"))
        store = KnowledgeStore(self.seed, self.inventory)
        with self.assertRaisesRegex(NovelOSError, "invalid_argument"):
            store.search("内容", tables=["kbx_hidden"])


class ProductionSeedIntegrityTest(unittest.TestCase):
    def test_authorized_seed_matches_frozen_inventory_and_is_query_only(self) -> None:
        seed = PROJECT_ROOT / "mcp" / "novelos" / "resources" / "seed.db"
        inventory = PROJECT_ROOT / "mcp" / "novelos" / "resources" / "seed-inventory.json"
        payload = json.loads(inventory.read_text(encoding="utf-8"))
        self.assertEqual(23, payload["table_count"])
        self.assertEqual(8108, payload["row_count"])
        self.assertEqual("sha256:59c7af0bca916824e3b4ff272da918cda1e4deb485b9ff46ed4faadba2a7c53a", payload["source_hash"])
        store = KnowledgeStore(seed, inventory)
        self.assertIsInstance(store.search("冲突", limit=1), list)
        with self.assertRaises(sqlite3.OperationalError):
            with closing(store._connect()) as connection:
                connection.execute("DELETE FROM kb_writing_techniques")


if __name__ == "__main__":
    unittest.main()
