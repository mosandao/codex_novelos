from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "novelos_register_characters", REPO_ROOT / "scripts" / "novelos_register_characters.py")
reg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reg)


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE projects (id TEXT PRIMARY KEY);
        CREATE TABLE chapters (id TEXT PRIMARY KEY);
        CREATE TABLE characters (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL,
            role_class TEXT NOT NULL DEFAULT 'secondary'
                CHECK (role_class IN ('main', 'secondary', 'minor')),
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'peripheral', 'dormant', 'departed', 'transformed', 'dead')),
            description_resource_id TEXT, state_json TEXT NOT NULL DEFAULT '{}',
            first_chapter_id TEXT, exit_chapter_id TEXT,
            exit_type TEXT CHECK (exit_type IS NULL OR exit_type IN
                ('完成型', '迁移型', '转化型', '关系型', '功能转移型', '休眠型', '死亡型')),
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (project_id, name));
    """)
    conn.execute("INSERT INTO projects VALUES ('project:p1')")
    conn.commit()
    conn.close()


def _roster() -> list[dict]:
    return [
        {"name": "林昭", "role_class": "main", "arc_role": "主角：账房视角的复仇者",
         "登场卷": 1, "预期退场": "持续活跃"},
        {"name": "沈青梧", "role_class": "main", "arc_role": "主锚点：同门至交",
         "登场卷": 1, "预期退场": "死亡型"},
    ]


class RegisterCharacters(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        _make_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def _rows(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        rows = {r["name"]: dict(r) for r in conn.execute(
            "SELECT * FROM characters WHERE project_id='project:p1'")}
        conn.close()
        return rows

    def test_roster_upsert_and_idempotence(self):
        self.assertEqual(reg.run(self.db, "project:p1", _roster(), None, None), 0)
        rows = self._rows()
        self.assertEqual(set(rows), {"林昭", "沈青梧"})
        self.assertEqual(rows["林昭"]["role_class"], "main")
        self.assertEqual(rows["林昭"]["status"], "active")
        self.assertIn("账房视角", rows["林昭"]["state_json"])
        # 幂等重放：不报错不重复
        self.assertEqual(reg.run(self.db, "project:p1", _roster(), None, None), 0)
        self.assertEqual(len(self._rows()), 2)

    def test_roster_schema_rejected(self):
        bad = [{"name": "无分类", "role_class": "boss", "arc_role": "x", "登场卷": 1, "预期退场": "持续活跃"}]
        self.assertEqual(reg.run(self.db, "project:p1", bad, None, None), 1)

    def test_entry_dynamic_and_merge(self):
        entry = {"name": "账房老周", "role_class": "minor", "first_chapter_id": "chapter:c3",
                 "notes": "微档案：袖口磨亮的算盘"}
        self.assertEqual(reg.run(self.db, "project:p1", None, [entry], None), 0)
        rows = self._rows()
        self.assertEqual(rows["账房老周"]["role_class"], "minor")
        self.assertEqual(rows["账房老周"]["first_chapter_id"], "chapter:c3")
        # 契约 roster 后到：升级分类不改状态
        roster = [{"name": "账房老周", "role_class": "secondary", "arc_role": "卷级账目见证人",
                   "登场卷": 1, "预期退场": "休眠型"}]
        self.assertEqual(reg.run(self.db, "project:p1", roster, None, None), 0)
        rows = self._rows()
        self.assertEqual(rows["账房老周"]["role_class"], "secondary")
        self.assertEqual(rows["账房老周"]["status"], "active")  # 状态不被 roster 覆盖
        self.assertIn("袖口磨亮的算盘", rows["账房老周"]["state_json"])  # 微档案信息保留

    def test_status_update_dead_requires_exit_type(self):
        reg.run(self.db, "project:p1", _roster(), None, None)
        bad = {"name": "沈青梧", "status": "dead", "exit_type": "迁移型"}
        self.assertEqual(reg.run(self.db, "project:p1", None, None, bad), 1)
        good = {"name": "沈青梧", "status": "dead", "exit_type": "死亡型"}
        self.assertEqual(reg.run(self.db, "project:p1", None, None, good), 0)
        rows = self._rows()
        self.assertEqual(rows["沈青梧"]["status"], "dead")

    def test_status_update_unknown_character_backfills_minor(self):
        update = {"name": "路人甲", "status": "departed", "exit_type": "完成型"}
        self.assertEqual(reg.run(self.db, "project:p1", None, None, update), 0)
        rows = self._rows()
        self.assertEqual(rows["路人甲"]["role_class"], "minor")  # 补登
        self.assertEqual(rows["路人甲"]["status"], "departed")


class ContinuityCharacterStatusSchema(unittest.TestCase):
    """P3-3：character_status 第六类候选过 schema 校验。"""

    def test_valid_and_invalid(self):
        import jsonschema
        schema = json.loads(
            (REPO_ROOT / "catalog/skills/continuity/continuity-candidate-extraction/schema.json")
            .read_text(encoding="utf-8"))
        payload = {
            "owners": ["character"],
            "candidates": [
                {"type": "character_status", "name": "沈青梧", "status": "dead",
                 "exit_type": "死亡型", "description": "第 47 章正文确认死亡"},
                {"type": "character_status", "name": "老周", "status": "departed",
                 "description": "南迁接管分号"},
            ],
        }
        jsonschema.validate(payload, schema)
        bad = {"owners": ["character"], "candidates": [
            {"type": "character_status", "name": "x", "status": "zombie", "description": "y"}]}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)


if __name__ == "__main__":
    unittest.main()
