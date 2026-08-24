"""story_arc metadata 机器门测试（T38）：弧数档位/映射表活跃窗/台账兑现/载体与机制对账/open 窗口。"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.novelos_validate_story_arc import validate, _resolve_from_db

ROOT = Path(__file__).resolve().parents[2]


def _extra_arc(i: int, kind: str = "其他") -> dict:
    return {"arc_id": f"extra_{i}", "name": f"支线{i}", "kind": kind,
            "carriers": [{"ref": f"待造{i}", "ref_type": "latent"}],
            "start_state": "起点", "end_state": "终点"}


def _meta(n_arcs: int | None = 3) -> dict:
    full = [
        {"arc_id": "main", "name": "复仇主线", "kind": "主线",
         "carriers": [{"ref": "林昭", "ref_type": "roster"}],
         "start_state": "隐忍蛰伏", "end_state": "清算完成"},
        {"arc_id": "growth", "name": "师弟成长", "kind": "人物",
         "carriers": [{"ref": "沈青梧", "ref_type": "roster"}],
         "start_state": "依附", "end_state": "独当一面"},
        {"arc_id": "sect", "name": "宗门变迁", "kind": "世界",
         "carriers": [{"ref": "掌门", "ref_type": "seat"}],
         "start_state": "铁板一块", "end_state": "改天换地"},
    ] + [_extra_arc(i) for i in range(6)]
    arcs = full[:n_arcs]
    plan = [{"index": i, "word_range": {"min": 200000, "max": 300000}}
            for i in range(1, 5)]
    grid = [
        ("main", 1, "推进"), ("growth", 1, "蓄势"), ("sect", 1, "休眠"),
        ("main", 2, "推进"), ("growth", 2, "推进"), ("sect", 2, "蓄势"),
        ("main", 3, "推进"), ("growth", 3, "兑现"), ("sect", 3, "推进"),
        ("main", 4, "推进"), ("growth", 4, "收束"), ("sect", 4, "兑现"),
    ] + [(f"extra_{i}", v, "休眠") for i in range(max(0, n_arcs - 3)) for v in (1, 2, 3, 4)]
    ledger = [
        {"line_id": "l1", "claim": "师门血案真凶", "source_type": "book_soul",
         "plant_volume": 1, "close_volume": 3, "close_form": "兑现"},
        {"line_id": "l2", "claim": "灵根私铸", "source_type": "strategy",
         "plant_volume": 1, "close_volume": 2, "close_form": "兑现"},
        {"line_id": "l3", "claim": "掌门身份", "source_type": "arc",
         "plant_volume": 2, "close_volume": 4, "close_form": "违约"},
    ]
    return {
        "schema_version": 1,
        "volume_plan": plan,
        "arcs": arcs,
        "arc_volume_map": [{"arc_id": a, "volume": v, "duty": d} for a, v, d in grid],
        "plant_payoff_ledger": ledger,
        "variation_alloc": [
            {"test_ref": "0", "volume": 1, "changed": ["处境"], "mech_ref": "变奏器A"},
            {"test_ref": "1", "volume": 3, "changed": ["代价"], "mech_ref": "变奏器B"},
        ],
    }


def _character(debut: int = 1) -> dict:
    return {"character_roster": [
        {"name": "林昭", "role_class": "main", "arc_role": "主角", "登场卷": 1, "预期退场": "持续活跃"},
        {"name": "沈青梧", "role_class": "main", "arc_role": "主锚点", "登场卷": debut, "预期退场": "持续活跃"},
    ]}


def _world() -> dict:
    return {"seats": [{"name": "掌门", "org": "玄阳宗", "duty": "执掌宗门",
                       "power_tier": "金丹", "first_consumption": "第1卷"}]}


def _architecture() -> dict:
    return {"mechanisms": [
        {"name": "变奏器A", "sources": [], "rhythm": "每卷一次", "downstream": [],
         "coupling": {"form": "io", "spec": "输入考验输出代价"}},
        {"name": "变奏器B", "sources": [], "rhythm": "隔卷", "downstream": [],
         "coupling": {"form": "quota", "spec": "配额注入"}},
    ], "mainline_density": {"tier": "高", "beats_per_volume": 1, "gap_limit_volumes": 2}}


def _strategy(mode: str = "closed") -> dict:
    return {"stages": [
        {"name": "s1", "word_range": {"min": 500000, "max": 600000}},
        {"name": "s2", "word_range": {"min": 500000, "max": 600000}},
    ], "terminal_mode": mode}


def _run(meta: dict, scale="长篇", **kw) -> tuple[list[str], list[str]]:
    return validate(meta, scale=scale,
                    character=kw.get("character", _character()),
                    world=kw.get("world", _world()),
                    architecture=kw.get("architecture", _architecture()),
                    strategy=kw.get("strategy", _strategy()))


class StoryArcValidate(unittest.TestCase):

    def test_base_passes(self):
        errors, warns = _run(_meta())
        self.assertEqual(errors, [])
        self.assertEqual(warns, [])  # 推进 ≤2 / 载体全具名 / 变奏 ≤3 全绿

    def test_arc_bands_per_scale(self):
        for scale, lo, hi in (("短篇", 1, 2), ("中篇", 2, 3), ("长篇", 3, 5), ("超长篇", 5, 7)):
            errors, _ = _run(_meta(n_arcs=hi), scale=scale)
            self.assertEqual([e for e in errors if "档区间" in e], [], f"{scale} 上界 {hi} 应通过")
            errors, _ = _run(_meta(n_arcs=hi + 1), scale=scale)
            self.assertTrue(any("超出" in e for e in errors), f"{scale} 超上界应拦")
            if lo > 1:
                errors, _ = _run(_meta(n_arcs=lo - 1), scale=scale)
                self.assertTrue(any("低于" in e for e in errors), f"{scale} 低于下界应拦")

    def test_unknown_scale_rejected(self):
        errors, _ = _run(_meta(), scale="巨篇")
        self.assertTrue(any("未知 scale" in e for e in errors))

    def test_no_scale_skips_band_gate(self):
        errors, _ = validate(_meta(n_arcs=8), scale=None, character=_character(),
                             world=_world(), architecture=_architecture(), strategy=_strategy())
        self.assertFalse(any("档区间" in e for e in errors))

    def test_mainline_exactly_one(self):
        m = _meta()
        m["arcs"] = [a for a in m["arcs"] if a["kind"] != "主线"]
        m["arc_volume_map"] = [r for r in m["arc_volume_map"] if r["arc_id"] != "main"]
        errors, _ = _run(m)
        self.assertTrue(any("主线弧须恰 1 条" in e for e in errors))
        m2 = _meta()
        m2["arcs"].append(_extra_arc(9, kind="主线"))
        m2["arc_volume_map"] += [{"arc_id": "extra_9", "volume": v, "duty": "休眠"} for v in (1, 2, 3, 4)]
        errors, _ = _run(m2)
        self.assertTrue(any("主线弧须恰 1 条" in e for e in errors))

    def test_map_gates(self):
        m = _meta()
        m["arc_volume_map"][0]["arc_id"] = "ghost"
        errors, _ = _run(m)
        self.assertTrue(any("不存在的 arc_id" in e for e in errors))
        m = _meta()
        m["arc_volume_map"] += [{"arc_id": "main", "volume": 9, "duty": "推进"}]
        errors, _ = _run(m)
        self.assertTrue(any("越界" in e for e in errors))
        m = _meta()
        for r in m["arc_volume_map"]:
            if r["volume"] == 1:
                r["duty"] = "蓄势" if r["duty"] == "推进" else "休眠"
        errors, _ = _run(m)
        self.assertTrue(any("无任何活跃弧" in e for e in errors))

    def test_volume_without_advance_warns_not_fails(self):
        m = _meta()
        for r in m["arc_volume_map"]:
            if r["volume"] == 4 and r["duty"] == "推进":
                r["duty"] = "收束"
        errors, warns = _run(m)
        self.assertFalse(any("无「推进」" in e for e in errors))
        self.assertTrue(any("无「推进」弧" in w for w in warns))  # 终卷全收束形态合法但提示

    def test_active_cap_and_overload(self):
        m = _meta(n_arcs=5)
        for r in m["arc_volume_map"]:
            if r["volume"] == 2 and r["duty"] == "蓄势":
                r["duty"] = "推进"
        errors, warns = _run(m, scale="超长篇")
        self.assertTrue(any("推进弧 3 条" in w for w in warns))
        m = _meta(n_arcs=5)
        for r in m["arc_volume_map"]:
            if r["volume"] == 2 and r["duty"] in ("蓄势", "休眠"):
                r["duty"] = "兑现"
        errors, _ = _run(m)
        self.assertTrue(any("同时活跃弧" in e and ">4" in e for e in errors))

    def test_carrier_gates(self):
        m = _meta()
        m["arcs"][0]["carriers"] = [{"ref": "不存在的人", "ref_type": "roster"}]
        errors, _ = _run(m)
        self.assertTrue(any("不在契约 roster" in e for e in errors))
        m = _meta()
        m["arcs"][2]["carriers"] = [{"ref": "不存在席", "ref_type": "seat"}]
        errors, _ = _run(m)
        self.assertTrue(any("不在 world 岗位表" in e for e in errors))
        m = _meta()
        m["arcs"][1]["carriers"] = [{"ref": "远卷对手", "ref_type": "latent"}]
        errors, warns = _run(m)
        self.assertTrue(any("无 roster 具名载体" in e for e in errors))  # 人物弧不许 latent-only
        self.assertTrue(any("latent" in w for w in warns))
        m = _meta()
        errors, _ = _run(m, character=_character(debut=2))
        self.assertTrue(any("早于载体" in e and "登场卷" in e for e in errors))

    def test_ledger_gates(self):
        m = _meta()
        m["plant_payoff_ledger"][0]["exempt"] = "deliberate_silences[0]"
        errors, _ = _run(m)
        self.assertTrue(any("兼有" in e for e in errors))
        m = _meta()
        m["plant_payoff_ledger"].pop(0)  # 卷 3 失去唯一兑现
        errors, _ = _run(m)
        self.assertTrue(any("卷 3 无任何前序悬念兑现" in e for e in errors))
        m = _meta()
        m["plant_payoff_ledger"].append({"line_id": "l4", "claim": "无收束",
                                         "source_type": "arc", "plant_volume": 1})
        errors, _ = _run(m)
        self.assertTrue(any("只种不收" in e for e in errors))
        m = _meta()
        m["plant_payoff_ledger"][0].update(plant_volume=3, close_volume=3)
        errors, _ = _run(m)
        self.assertTrue(any("不晚于种下卷" in e for e in errors))

    def test_variation_gates(self):
        m = _meta()
        m["variation_alloc"][0]["mech_ref"] = "幽灵机制"
        errors, _ = _run(m)
        self.assertTrue(any("mech_ref" in e and "不在" in e for e in errors))
        m = _meta()
        m["variation_alloc"] += [{"test_ref": "0", "volume": 2, "changed": ["答案"]},
                                 {"test_ref": "0", "volume": 3, "changed": ["处境"]},
                                 {"test_ref": "0", "volume": 4, "changed": ["处境", "代价"]}]
        _, warns = _run(m)
        self.assertTrue(any("剩余空间" in w for w in warns))

    def test_volume_plan_contiguous(self):
        m = _meta()
        m["volume_plan"][3]["index"] = 6
        errors, _ = _run(m)
        self.assertTrue(any("卷号不连续" in e for e in errors))

    def test_open_window_gate(self):
        m = _meta()
        errors, _ = _run(m, strategy=_strategy(mode="open"))
        self.assertTrue(any("open_window" in e for e in errors))
        m["open_window"] = {"hard_volumes": 2}
        errors, _ = _run(m, strategy=_strategy(mode="open"))
        self.assertFalse(any("open_window" in e for e in errors))

    def test_resolve_from_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            conn = sqlite3.connect(db)
            conn.executescript("""
                CREATE TABLE projects (id TEXT PRIMARY KEY, metadata_json TEXT);
                CREATE TABLE planning_assets (id TEXT PRIMARY KEY, project_id TEXT,
                  asset_type TEXT, scope_ref TEXT, revision INTEGER, status TEXT,
                  content_resource_id TEXT, metadata_json TEXT);
            """)
            conn.execute("INSERT INTO projects VALUES ('project:p1', ?)",
                         (json.dumps({"setup": {"scale": "超长篇（300万字以上）"}}, ensure_ascii=False),))
            for asset, meta in (("character_contract", _character()), ("world_contract", _world()),
                                ("architecture", _architecture()), ("strategy", _strategy())):
                conn.execute(
                    "INSERT INTO planning_assets VALUES (?, 'project:p1', ?, 'book', 1, "
                    "'locked', NULL, ?)", (f"pa:{asset}", asset, json.dumps(meta, ensure_ascii=False)))
            conn.commit()
            conn.close()
            out = _resolve_from_db("project:p1", db)
            self.assertEqual(out["scale"], "超长篇")  # 全标签归一化
            self.assertEqual(out["world"]["seats"][0]["name"], "掌门")
            self.assertEqual(out["strategy"]["terminal_mode"], "closed")


if __name__ == "__main__":
    unittest.main()
