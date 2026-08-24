"""volume_outline metadata 机器门测试（T39）：卷号连续/字数对表/高潮门/线弧双向/单元/换图/终卷。"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.novelos_validate_volume_outline import validate, _resolve_from_db

ROOT = Path(__file__).resolve().parent.parent


def _meta(**over) -> dict:
    base = {
        "schema_version": 1,
        "volume_number": 2,
        "word_range": {"min": 200000, "target": 250000, "max": 300000},
        "volume_form": "连续四段",
        "lines": [
            {"name": "复仇主线", "scope": "跨卷弧", "arc_id": "main", "share_pct": 40,
             "mainline": True, "pov": "林昭"},
            {"name": "师弟成长", "scope": "跨卷弧", "arc_id": "growth", "share_pct": 30,
             "pov": "沈青梧"},
            {"name": "市井悬案", "scope": "卷内自含", "share_pct": 30, "pov": "林昭",
             "note": "三起连环骗案加压，卷末并案结算"},
        ],
        "mainline_beats": 1,
        "climax_positions": [0.5, 1.0],
        "new_plants": [
            {"line_id": "market_case", "claim": "市井骗局幕后是谁", "close_volume": 2},
        ],
        "test_alloc": [{"test_ref": "0", "changed": ["处境"]}],
        "volume_characters": [
            {"name": "钱掌柜", "role_class": "minor", "arc_role": "骗案饵料", "预期退场": "完成型"},
        ],
    }
    base.update(over)
    return base


def _story_arc() -> dict:
    return {
        "schema_version": 1,
        "volume_plan": [
            {"index": i, "word_range": {"min": 200000, "max": 300000}} for i in range(1, 5)
        ],
        "arcs": [
            {"arc_id": "main", "name": "复仇主线", "kind": "主线",
             "carriers": [{"ref": "林昭", "ref_type": "roster"}],
             "start_state": "蛰伏", "end_state": "清算"},
            {"arc_id": "growth", "name": "师弟成长", "kind": "人物",
             "carriers": [{"ref": "沈青梧", "ref_type": "roster"}],
             "start_state": "依附", "end_state": "独当一面"},
        ],
        "arc_volume_map": [
            {"arc_id": "main", "volume": 2, "duty": "推进"},
            {"arc_id": "growth", "volume": 2, "duty": "推进"},
        ],
        "plant_payoff_ledger": [
            {"line_id": "l1", "claim": "血案真凶", "source_type": "book_soul",
             "plant_volume": 1, "close_volume": 3, "close_form": "兑现"},
        ],
        "variation_alloc": [
            {"test_ref": "0", "volume": 2, "changed": ["处境"], "mech_ref": "变奏器A"},
        ],
    }


def _architecture(tier: str = "中") -> dict:
    return {"mainline_density": {"tier": tier, "beats_per_volume": 1,
                                 "gap_limit_volumes": 2}}


def _strategy(mode: str = "closed") -> dict:
    return {"stages": [
        {"name": "s1", "word_range": {"min": 400000, "max": 600000}},
        {"name": "s2", "word_range": {"min": 400000, "max": 600000}},
    ], "terminal_mode": mode}


def _run(meta: dict, scale="长篇", **kw) -> tuple[list[str], list[str]]:
    return validate(meta, scale=scale,
                    story_arc=kw.get("story_arc", _story_arc()),
                    architecture=kw.get("architecture", _architecture()),
                    strategy=kw.get("strategy", _strategy()),
                    prev_volume_numbers=kw.get("prev_volume_numbers", [1]),
                    registry_names=kw.get("registry_names", {"林昭", "沈青梧", "钱掌柜"}))


class VolumeOutlineValidate(unittest.TestCase):

    def test_pass_baseline(self):
        errors, _ = _run(_meta())
        self.assertEqual(errors, [])

    def test_prev_volume_gap_blocks_disorder(self):
        errors, _ = _run(_meta(volume_number=3), prev_volume_numbers=[1])
        self.assertTrue(any("前置锁定卷号" in e for e in errors))

    def test_word_range_overlap(self):
        errors, _ = _run(_meta(word_range={"min": 350000, "target": 380000, "max": 400000}))
        self.assertTrue(any("无交集" in e for e in errors))
        errors2, warns2 = _run(_meta(word_range={"min": 200000, "target": 310000, "max": 330000}))
        self.assertFalse(any("无交集" in e for e in errors2))
        self.assertTrue(any("target" in w and "区间外" in w for w in warns2))

    def test_climax_gap_and_count_gates(self):
        meta = _meta(word_range={"min": 600000, "target": 700000, "max": 800000},
                     climax_positions=[0.1, 1.0])
        errors, _ = _run(meta)
        self.assertTrue(any("间距" in e for e in errors))
        self.assertTrue(any("高潮总数" in e for e in errors))

    def test_climax_last_must_be_main(self):
        errors, _ = _run(_meta(climax_positions=[0.5, 0.9]))
        self.assertTrue(any("末位" in e for e in errors))

    def test_short_form_degenerate(self):
        meta = _meta(volume_number=1, word_range={"min": 100000, "target": 150000, "max": 180000},
                     climax_positions=[1.0])
        arc = _story_arc()
        arc["volume_plan"] = [{"index": 1, "word_range": {"min": 100000, "max": 180000}}]
        arc["arc_volume_map"] = [
            {"arc_id": "main", "volume": 1, "duty": "推进"},
            {"arc_id": "growth", "volume": 1, "duty": "蓄势"},
        ]
        meta["lines"] = [ln for ln in meta["lines"] if ln.get("arc_id") != "growth"] + [
            {"name": "师弟成长", "scope": "卷内自含", "share_pct": 30, "pov": "沈青梧",
             "note": "自含线"}]
        meta["new_plants"] = [{"line_id": "market_case", "claim": "市井骗局幕后是谁",
                               "close_volume": 1}]
        errors, _ = _run(meta, scale="短篇", story_arc=arc, prev_volume_numbers=[])
        self.assertEqual(errors, [])

    def test_duty_evaporation(self):
        meta = _meta(lines=[
            {"name": "复仇主线", "scope": "跨卷弧", "arc_id": "main", "share_pct": 40,
             "mainline": True, "pov": "林昭"},
            {"name": "市井悬案", "scope": "卷内自含", "share_pct": 30, "pov": "林昭",
             "note": "自含线"},
            {"name": "漕运纠纷", "scope": "卷内自含", "share_pct": 30, "pov": "沈青梧",
             "note": "自含线"},
        ])
        errors, _ = _run(meta)
        self.assertTrue(any("职责蒸发" in e for e in errors))

    def test_dormant_arc_carrying_line_warns(self):
        arc = _story_arc()
        arc["arc_volume_map"] = [
            {"arc_id": "main", "volume": 2, "duty": "推进"},
            {"arc_id": "growth", "volume": 2, "duty": "蓄势"},
        ]
        errors, warns = _run(_meta(), story_arc=arc)
        self.assertEqual(errors, [])
        self.assertTrue(any("反向活跃" in w for w in warns))

    def test_cross_line_requires_arc_id(self):
        meta = _meta()
        meta["lines"][1] = {"name": "师弟成长", "scope": "跨卷弧", "share_pct": 30,
                            "pov": "沈青梧"}
        errors, _ = _run(meta)
        self.assertTrue(any("无 arc_id" in e for e in errors))

    def test_unknown_arc_reference(self):
        meta = _meta()
        meta["lines"][1]["arc_id"] = "ghost"
        errors, _ = _run(meta)
        self.assertTrue(any("不存在的 arc_id" in e for e in errors))

    def test_units_gates(self):
        errors, _ = _run(_meta(volume_form="单元编排"))
        self.assertTrue(any("缺 units" in e for e in errors))
        meta = _meta(volume_form="单元编排", units=[
            {"unit_id": "dungeon_a", "theme": "忠义考验", "chapter_window": {"min": 8, "max": 12},
             "mainline_advance": 0},
            {"unit_id": "interlude", "theme": "主世界休整", "chapter_window": {"min": 2, "max": 3},
             "mainline_advance": 0, "interlude": True},
        ])
        errors2, _ = _run(meta)
        self.assertTrue(any("主线渗透" in e for e in errors2))
        self.assertFalse(any("interlude" in e for e in errors2))

    def test_exit_settlement_unknown_ledger_ref(self):
        meta = _meta(exit_settlement={"carry": ["林昭"], "cut": ["ghost_line"],
                                      "pre_close": []})
        _, warns = _run(meta)
        self.assertTrue(any("ghost_line" in w and "line_id" in w for w in warns))

    def test_new_plants_gates(self):
        meta = _meta(new_plants=[
            {"line_id": "x1", "claim": "早收", "close_volume": 1},
            {"line_id": "x2", "claim": "双收", "close_volume": 3, "exempt": "有意挖坑"},
            {"line_id": "l1", "claim": "撞台账", "close_volume": 3},
        ])
        errors, _ = _run(meta)
        self.assertTrue(any("先收后种" in e for e in errors))
        self.assertTrue(any("二选一" in e for e in errors))
        self.assertTrue(any("冲突" in e for e in errors))

    def test_final_volume_discipline(self):
        meta = _meta(volume_number=4, new_plants=[
            {"line_id": "f1", "claim": "终卷新坑", "close_volume": 5},
            {"line_id": "f2", "claim": "终卷豁免", "exempt": "续作钩子"},
        ])
        arc = _story_arc()
        arc["arc_volume_map"] = [
            {"arc_id": "main", "volume": 4, "duty": "收束"},
            {"arc_id": "growth", "volume": 4, "duty": "兑现"},
        ]
        meta["test_alloc"] = []
        arc["variation_alloc"] = []
        errors, _ = _run(meta, story_arc=arc)
        self.assertTrue(any("溢出终卷" in e for e in errors))
        self.assertTrue(any("closed" in e for e in errors))
        errors2, warns2 = _run(meta, story_arc=arc, strategy=_strategy(mode="open"))
        self.assertFalse(any("closed" in e for e in errors2))
        self.assertTrue(any("open" in w for w in warns2))

    def test_stage_span_bounds(self):
        errors, _ = _run(_meta(stage_span=[1, 3]))
        self.assertTrue(any("stage_span" in e for e in errors))

    def test_mainline_share_vs_tier(self):
        meta = _meta()
        meta["lines"][0]["share_pct"] = 60
        meta["lines"][1]["share_pct"] = 10
        meta["lines"][2]["share_pct"] = 30
        _, warns = _run(meta, architecture=_architecture(tier="低"))
        self.assertTrue(any("削平" in w for w in warns))
        meta2 = _meta()
        meta2["lines"][0]["share_pct"] = 20
        meta2["lines"][1]["share_pct"] = 50
        meta2["lines"][2]["share_pct"] = 30
        _, warns2 = _run(meta2, architecture=_architecture(tier="高"))
        self.assertTrue(any("喂不饱" in w for w in warns2))

    def test_test_alloc_reconciliation(self):
        _, warns = _run(_meta(test_alloc=[]))
        self.assertTrue(any("未被 test_alloc 承接" in w for w in warns))
        _, warns2 = _run(_meta(test_alloc=[{"test_ref": "0", "changed": ["处境"]},
                                           {"test_ref": "9", "changed": ["代价"]}]))
        self.assertTrue(any("超出" in w for w in warns2))

    def test_registry_and_settings_precheck(self):
        meta = _meta(volume_settings=[
            {"kind": "势力", "name": "漕帮", "spec": "把持水路的一句规格", "disposition": "登记入world"},
            {"kind": "地点", "name": "鬼市", "spec": "卷内黑市", "disposition": "卷内自闭"},
        ])
        _, warns = _run(meta, registry_names=set())
        self.assertTrue(any("钱掌柜" in w and "注册表" in w for w in warns))
        self.assertTrue(any("漕帮" in w and "登记入 world" in w for w in warns))

    def test_settings_duplicate_names(self):
        meta = _meta(volume_settings=[
            {"kind": "地点", "name": "鬼市", "spec": "一号", "disposition": "卷内自闭"},
            {"kind": "地点", "name": "鬼市", "spec": "二号", "disposition": "卷内自闭"},
        ])
        errors, _ = _run(meta)
        self.assertTrue(any("名称重复" in e for e in errors))


class VolumeOutlineResolveFromDB(unittest.TestCase):

    def test_project_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE projects (id TEXT PRIMARY KEY, metadata_json TEXT);
                CREATE TABLE planning_assets (id TEXT PRIMARY KEY, project_id TEXT, asset_type TEXT,
                  scope_ref TEXT, revision INTEGER, status TEXT, content_resource_id TEXT,
                  metadata_json TEXT);
                CREATE TABLE resources (id TEXT PRIMARY KEY, content BLOB);
                CREATE TABLE characters (id TEXT PRIMARY KEY, project_id TEXT, name TEXT);
                """
            )
            conn.execute("INSERT INTO projects VALUES ('project:p1', ?)",
                         (json.dumps({"setup": {"scale": "长篇（30-80万字）"}}, ensure_ascii=False),))
            for aid, atype, meta in (("pa:a", "architecture", json.dumps(_architecture())),
                                     ("pa:s", "strategy", json.dumps(_strategy()))):
                conn.execute("INSERT INTO planning_assets VALUES "
                             "(?, 'project:p1', ?, 'book', 1, 'locked', NULL, ?)", (aid, atype, meta))
            conn.execute("INSERT INTO planning_assets VALUES "
                         "('pa:v1', 'project:p1', 'volume_outline', 'volume:1', 1, 'locked', NULL, ?)",
                         (json.dumps({"volume_number": 1}),))
            conn.execute("INSERT INTO characters VALUES ('c:1', 'project:p1', '林昭')")
            conn.commit()
            conn.close()
            out = _resolve_from_db("project:p1", db)
        self.assertEqual(out["scale"], "长篇")
        self.assertEqual(out.get("prev_volume_numbers"), [1])
        self.assertEqual(out.get("registry_names"), {"林昭"})
        self.assertEqual(out["architecture"]["mainline_density"]["tier"], "中")


if __name__ == "__main__":
    unittest.main()
