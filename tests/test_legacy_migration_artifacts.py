from __future__ import annotations

import hashlib
import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "tasks" / "migration" / "legacy_migration_report.json"
SOURCE_PATH = ROOT / "data" / "migration" / "backend-novelos-aaadc9bedf499e.db"
TARGET_PATH = ROOT / "data" / "novelos-v2.db"
SOURCE_HASH = "aaadc9bedf499e9a10534422064d4d91862293529bccac160843e0ab846ae1ba"
EXPECTED_COUNTS = {
    "projects": 4,
    "books": 3,
    "volumes": 3,
    "chapters": 4,
    "characters": 2,
}


class LegacyMigrationArtifactsTest(unittest.TestCase):
    def test_report_records_frozen_source_and_reconciled_counts(self) -> None:
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

        self.assertEqual(f"sha256:{SOURCE_HASH}", report["source_hash"])
        self.assertEqual(EXPECTED_COUNTS, report["migrated_counts"])
        self.assertEqual({}, report["quarantined_counts"])
        for table, expected in EXPECTED_COUNTS.items():
            self.assertEqual(expected, report["source_counts"][table])
            self.assertEqual(expected, report["target_counts"][table])
            self.assertRegex(report["target_hashes"][table], r"^sha256:[0-9a-f]{64}$")

    @unittest.skipUnless(SOURCE_PATH.exists() and TARGET_PATH.exists(), "本地迁移数据库未保留")
    def test_local_migration_databases_match_report(self) -> None:
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        # 源库是不可变的迁移基线：其字节 hash 必须永远等于报告冻结值。
        self.assertEqual(SOURCE_HASH, hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest())

        with closing(sqlite3.connect(f"file:{TARGET_PATH}?mode=ro", uri=True)) as connection:
            self.assertEqual("ok", connection.execute("PRAGMA quick_check").fetchone()[0])
            versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")]
            # 目标库是活的生产数据库：迁移是不可撤销的追加基线，之后只增不减。
            # 因此校验下限为迁移冻结计数（>=），而非严格相等；删除迁移基线数据才会失败。
            self.assertEqual(list(range(1, 10)), versions[:9])
            for table, expected in EXPECTED_COUNTS.items():
                count = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                self.assertGreaterEqual(count, expected, table)
            # legacy_imports 表在 migration 016（NovelOS 轻量化）中被删除。
            # 迁移已完成且 legacy_imports 只用于迁移期跟踪，不再需要。
            has_legacy_imports = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='legacy_imports'"
            ).fetchone()
            if has_legacy_imports:
                import_row = connection.execute("SELECT source_hash FROM legacy_imports").fetchone()
                self.assertEqual(report["source_hash"], import_row[0])


if __name__ == "__main__":
    unittest.main()
