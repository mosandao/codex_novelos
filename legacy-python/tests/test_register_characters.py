from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "novelos_register_characters", REPO_ROOT / "legacy-python" / "scripts" / "novelos_register_characters.py")
reg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reg)


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE projects (id TEXT PRIMARY KEY);
        CREATE TABLE chapters (id TEXT PRIMARY KEY);
        CREATE TABLE resources (id TEXT PRIMARY KEY, media_type TEXT, content BLOB, content_hash TEXT);
        CREATE TABLE continuity_candidate_sets (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, chapter_id TEXT NOT NULL,
            source_content_hash TEXT NOT NULL, authority_snapshot_json TEXT NOT NULL,
            candidate_resource_id TEXT NOT NULL, subject_hash TEXT NOT NULL,
            owners_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'working',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
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
        CREATE TABLE planning_assets (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, asset_type TEXT NOT NULL,
            scope_ref TEXT, revision INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL,
            content_resource_id TEXT, metadata_json TEXT);
    """)
    conn.execute("INSERT INTO projects VALUES ('project:p1')")
    conn.commit()
    conn.close()


def _locked_volume(db: Path, scope: str, meta: dict) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO planning_assets VALUES (?, 'project:p1', 'volume_outline', ?, 1, "
        "'locked', NULL, ?)", (f"pa:{scope}", scope, json.dumps(meta, ensure_ascii=False)))
    conn.commit()
    conn.close()


def _promoted_set(db: Path, set_id: str, candidates: list[dict],
                  created_at: str = "2026-01-01 00:00:00") -> None:
    conn = sqlite3.connect(db)
    res_id = f"resource:{set_id}"
    cand_json = json.dumps({"owners": ["character"], "candidates": candidates},
                           ensure_ascii=False)
    conn.execute(
        "INSERT INTO resources VALUES (?, 'application/json', CAST(? AS BLOB), 'sha256:x')",
        (res_id, cand_json))
    conn.execute(
        "INSERT INTO continuity_candidate_sets (id, project_id, chapter_id, "
        " source_content_hash, authority_snapshot_json, candidate_resource_id, "
        " subject_hash, owners_json, status, created_at, updated_at) "
        "VALUES (?, 'project:p1', 'chapter:c1', 'sha256:y', '{}', ?, 'sha256:z', "
        " '[\"character\"]', 'promoted', ?, ?)",
        (set_id, res_id, created_at, created_at))
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

    def test_entry_volume_characters_fields(self):
        # 卷纲班底走 --entry：arc_role/预期退场/来源卷/source 落 state_json
        entry = {"name": "悬赏猎人·隼", "role_class": "secondary",
                 "arc_role": "本卷第二支线压力源", "预期退场": "完成型",
                 "来源卷": 2, "微档案": "左手总戴着断指手套；从不喝别人倒的酒",
                 "source": "volume_outline"}
        self.assertEqual(reg.run(self.db, "project:p1", None, [entry], None), 0)
        rows = self._rows()
        state = json.loads(rows["悬赏猎人·隼"]["state_json"])
        self.assertEqual(rows["悬赏猎人·隼"]["role_class"], "secondary")
        self.assertEqual(state["arc_role"], "本卷第二支线压力源")
        self.assertEqual(state["预期退场"], "完成型")
        self.assertEqual(state["来源卷"], 2)
        self.assertEqual(state["source"], "volume_outline")

    def test_entry_volume_characters_validation(self):
        bad_exit = {"name": "甲", "role_class": "minor", "预期退场": "半路消失"}
        self.assertEqual(reg.run(self.db, "project:p1", None, [bad_exit], None), 1)
        bad_vol = {"name": "乙", "role_class": "minor", "来源卷": "第二卷"}
        self.assertEqual(reg.run(self.db, "project:p1", None, [bad_vol], None), 1)

    def test_entry_volume_characters_schema(self):
        # planning-candidate $defs/volume_characters：合法班底通过，main 被拒
        import jsonschema
        schema = json.loads(reg.SCHEMA_PATH.read_text(encoding="utf-8"))
        sub = dict(schema["$defs"]["volume_characters"])
        sub["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        good = [{"name": "隼", "role_class": "secondary", "arc_role": "支线压力源",
                 "预期退场": "完成型", "微档案": "断指手套"}]
        jsonschema.validate(good, sub)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(
                [{"name": "假主角", "role_class": "main", "arc_role": "主角",
                  "预期退场": "持续活跃"}], sub)

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


class StatusArrayHistoryRevival(unittest.TestCase):
    """T31-2：status-update 数组化 / 状态史审计 / 复活清退场痕迹。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        _make_db(self.db)
        reg.run(self.db, "project:p1", _roster(), None, None)

    def tearDown(self):
        self.tmp.cleanup()

    def _rows(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        rows = {r["name"]: dict(r) for r in conn.execute(
            "SELECT * FROM characters WHERE project_id='project:p1'")}
        conn.close()
        return rows

    def test_array_updates_single_transaction(self):
        updates = [
            {"name": "沈青梧", "status": "dead", "exit_type": "死亡型",
             "exit_chapter_id": "chapter:c47"},
            {"name": "林昭", "status": "peripheral"},
        ]
        self.assertEqual(reg.run(self.db, "project:p1", None, None, updates), 0)
        rows = self._rows()
        self.assertEqual(rows["沈青梧"]["status"], "dead")
        self.assertEqual(rows["沈青梧"]["exit_chapter_id"], "chapter:c47")
        self.assertEqual(rows["林昭"]["status"], "peripheral")

    def test_status_history_appended(self):
        updates = [
            {"name": "沈青梧", "status": "dead", "exit_type": "死亡型",
             "exit_chapter_id": "chapter:c47"},
            {"name": "沈青梧", "status": "active"},  # 假死复活
        ]
        self.assertEqual(reg.run(self.db, "project:p1", None, None, updates), 0)
        state = json.loads(self._rows()["沈青梧"]["state_json"])
        history = state["状态史"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0], {"from": "active", "to": "dead",
                                      "exit_type": "死亡型",
                                      "chapter_id": "chapter:c47",
                                      "at": history[0]["at"]})
        self.assertEqual(history[1]["from"], "dead")
        self.assertEqual(history[1]["to"], "active")

    def test_revival_clears_exit_traces(self):
        reg.run(self.db, "project:p1", None, None,
                {"name": "沈青梧", "status": "dead", "exit_type": "死亡型",
                 "exit_chapter_id": "chapter:c47"})
        self.assertEqual(
            reg.run(self.db, "project:p1", None, None, {"name": "沈青梧", "status": "active"}), 0)
        row = self._rows()["沈青梧"]
        self.assertEqual(row["status"], "active")
        self.assertIsNone(row["exit_type"])       # 退场类型清空
        self.assertIsNone(row["exit_chapter_id"])  # 且不留半截退场章节

    def test_nonexit_with_exit_type_rejected(self):
        bad = {"name": "林昭", "status": "peripheral", "exit_type": "完成型"}
        self.assertEqual(reg.run(self.db, "project:p1", None, None, bad), 1)


class RosterRelockWarning(unittest.TestCase):
    """T31-2：roster 重锁对账——契约删掉的人物 WARN 而不静默残留。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        _make_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dropped_character_warns_but_not_auto_retired(self):
        import contextlib
        import io
        reg.run(self.db, "project:p1", _roster(), None, None)
        new_roster = [r for r in _roster() if r["name"] == "林昭"]  # 沈青梧被契约删除
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = reg.run(self.db, "project:p1", new_roster, None, None)
        self.assertEqual(code, 0)
        self.assertIn("沈青梧", out.getvalue())
        self.assertIn("WARN", out.getvalue())
        conn = sqlite3.connect(self.db)
        status = conn.execute(
            "SELECT status FROM characters WHERE project_id='project:p1' AND name='沈青梧'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(status, "active")  # 不自动改状态，交人裁决


class PendingStatusReconciliation(unittest.TestCase):
    """T31-2：--pending-status 账本↔注册表对账。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        _make_db(self.db)
        reg.run(self.db, "project:p1", _roster(), None, None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_candidates_passes(self):
        self.assertEqual(reg.check_pending_status(self.db, "project:p1"), 0)

    def test_status_mismatch_drifts_then_resolves(self):
        _promoted_set(self.db, "set:1", [
            {"type": "character_status", "name": "沈青梧", "status": "dead",
             "exit_type": "死亡型", "description": "第 47 章确认"}])
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = reg.check_pending_status(self.db, "project:p1")
        self.assertEqual(code, 1)
        self.assertIn("DRIFT 沈青梧", out.getvalue())
        # 补跑迁移后对账通过
        self.assertEqual(reg.run(self.db, "project:p1", None, None,
                                 {"name": "沈青梧", "status": "dead",
                                  "exit_type": "死亡型"}), 0)
        self.assertEqual(reg.check_pending_status(self.db, "project:p1"), 0)

    def test_unregistered_candidate_drifts(self):
        _promoted_set(self.db, "set:1", [
            {"type": "character_status", "name": "神秘人", "status": "departed",
             "description": "雨夜离城"}])
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = reg.check_pending_status(self.db, "project:p1")
        self.assertEqual(code, 1)
        self.assertIn("未登记", out.getvalue())

    def test_latest_candidate_wins_no_false_positive(self):
        # ch1 候选 departed、ch2 候选 active（复活），注册表 active = 一致
        _promoted_set(self.db, "set:1", [
            {"type": "character_status", "name": "沈青梧", "status": "departed",
             "exit_type": "迁移型", "description": "南迁"}],
            created_at="2026-01-01 00:00:00")
        _promoted_set(self.db, "set:2", [
            {"type": "character_status", "name": "沈青梧", "status": "active",
             "description": "归来"}],
            created_at="2026-01-02 00:00:00")
        self.assertEqual(reg.check_pending_status(self.db, "project:p1"), 0)


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


        bad = {"owners": ["character"], "candidates": [
            {"type": "character_status", "name": "x", "status": "zombie", "description": "y"}]}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)


def _world_meta() -> dict:
    return {"seats": [
        {"name": "掌门", "org": "玄阳宗", "disposition": "待契约认领"},
        {"name": "客卿", "org": "玄阳宗", "disposition": "待卷级班底"},
    ]}


class RegisterSeatsEssenceT37(unittest.TestCase):
    """T37：roster 落库带 seat_ref/essence；--world 席位对账；近重名 WARN。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        _make_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_roster_persists_seat_and_essence(self):
        roster = [
            {"name": "林昭", "role_class": "main", "arc_role": "主角", "登场卷": 1,
             "预期退场": "持续活跃", "seat_ref": "掌门",
             "essence": "对除名牌位执念（谈宗族失措三秒）｜市井口癖藏锋"},
            {"name": "沈青梧", "role_class": "main", "arc_role": "主锚点", "登场卷": 1,
             "预期退场": "死亡型"},
        ]
        self.assertEqual(reg.run(self.db, "project:p1", roster, None, None, _world_meta()), 0)
        state = json.loads(self._rows()["林昭"]["state_json"])
        self.assertEqual(state["seat_ref"], "掌门")
        self.assertIn("执念", state["essence"])
        self.assertNotIn("seat_ref", json.loads(self._rows()["沈青梧"]["state_json"]))

    def test_world_bad_seat_ref_fails(self):
        roster = [
            {"name": "林昭", "role_class": "main", "arc_role": "主角", "登场卷": 1,
             "预期退场": "持续活跃", "seat_ref": "不存在席"},
        ]
        self.assertEqual(reg.run(self.db, "project:p1", roster, None, None, _world_meta()), 1)

    def test_world_unclaimed_promise_seats_warn(self):
        import contextlib
        import io
        roster = [
            {"name": "林昭", "role_class": "main", "arc_role": "主角", "登场卷": 1,
             "预期退场": "持续活跃", "seat_ref": "掌门"},
        ]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = reg.run(self.db, "project:p1", roster, None, None, _world_meta())
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("客卿", out)          # 待卷级班底 无人认领 → WARN
        self.assertNotIn("掌门", out.split("完成")[0].replace("roster 林昭", ""))  # 掌门已认领

    def test_near_dup_normalized_warns(self):
        import contextlib
        import io
        roster = [
            {"name": "林昭", "role_class": "main", "arc_role": "主角", "登场卷": 1,
             "预期退场": "持续活跃"},
        ]
        self.assertEqual(reg.run(self.db, "project:p1", roster, None, None), 0)
        entries = [{"name": "林　昭", "role_class": "minor",
                    "notes": "全角空格变体"}]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = reg.run(self.db, "project:p1", None, entries, None)
        self.assertEqual(rc, 0)
        self.assertIn("近重名", buf.getvalue())
        # 完全同名（幂等合并）不触发近重名 WARN
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            rc2 = reg.run(self.db, "project:p1", roster, None, None)
        self.assertEqual(rc2, 0)
        self.assertNotIn("近重名", buf2.getvalue())

    def _rows(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        rows = {r["name"]: dict(r) for r in conn.execute(
            "SELECT * FROM characters WHERE project_id='project:p1'")}
        conn.close()
        return rows

    def test_audit_entries_flags_missing(self):
        _locked_volume(self.db, "volume:1", {"volume_number": 1, "volume_characters": [
            {"name": "悬赏猎人·隼", "role_class": "secondary", "arc_role": "支线压力源",
             "预期退场": "完成型"}]})
        self.assertEqual(reg.check_audit_entries(self.db, "project:p1"), 1)  # 漏跑 --entry

    def test_audit_entries_pass_after_registration(self):
        _locked_volume(self.db, "volume:1", {"volume_number": 1, "volume_characters": [
            {"name": "悬赏猎人·隼", "role_class": "secondary", "arc_role": "支线压力源",
             "预期退场": "完成型", "来源卷": 1}]})
        self.assertEqual(reg.run(self.db, "project:p1", None, [
            {"name": "悬赏猎人·隼", "role_class": "secondary", "arc_role": "支线压力源",
             "预期退场": "完成型", "来源卷": 1, "source": "volume_outline"}], None), 0)
        self.assertEqual(reg.check_audit_entries(self.db, "project:p1"), 0)

    def test_audit_entries_old_assets_and_settings_warn(self):
        _locked_volume(self.db, "volume:1", {})  # T39 前旧卷纲：无 volume_characters 字段
        _locked_volume(self.db, "volume:2", {"volume_number": 2, "volume_settings": [
            {"kind": "势力", "name": "漕帮", "spec": "把持水路", "disposition": "登记入world"}]})
        self.assertEqual(reg.check_audit_entries(self.db, "project:p1"), 0)  # 仅 WARN 不阻断


if __name__ == "__main__":
    unittest.main()
