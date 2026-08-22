"""T36：world-metadata / character-roster 双 validate 机器门测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from novelos_validate_world import validate as validate_world  # noqa: E402
from novelos_validate_character import validate as validate_character  # noqa: E402


def _world_base() -> dict:
    return {
        "schema_version": 1,
        "seats": [
            {"name": "掌门", "org": "玄阳宗", "duty": "掌法度与传承", "power_tier": "化神",
             "rule_links": ["宗门法度"], "first_consumption": "第1卷·入门考核",
             "disposition": "待契约认领"},
            {"name": "执法长老", "org": "玄阳宗", "duty": "执行门规", "power_tier": "元婴",
             "first_consumption": "第1卷·冤枉打脸"},
        ],
        "lexicon": {
            "positive_terms": ["灵潮", "洗髓", "观星台"],
            "banned_categories": {
                "物理术语": ["能量"], "生物医学术语": ["神经"],
                "现代计量": ["米"], "现代认知框架": ["效率"],
            },
            "measure_system": "里丈尺·一炷香·斤两",
            "exceptions": ["穿越者内心 OS（POV 声明）"],
        },
        "dimension_costs": [
            {"dimension": "力量", "form": "灵潮反噬心智", "reversibility": "不可逆",
             "threshold": "第三次引潮后灵路焦结", "bearer": "plot_character"},
            {"dimension": "封印", "form": "金手指封印", "reversibility": "压制",
             "release": "集齐三枚星核解除", "bearer": "world"},
        ],
        "decision_points": [],
    }


def _roster(n: int = 4) -> list[dict]:
    people = [
        ("沈青梧", "main", "主角", 1, "持续活跃", "掌门"),
        ("陆沉舟", "main", "核心对手", 1, "持续活跃", None),
        ("阿九", "secondary", "主锚点", 1, "休眠型", None),
        ("白观星", "secondary", "卷级载体", 2, "完成型", "执法长老"),
        ("甲五", "secondary", "载体", 3, "迁移型", None),
        ("乙六", "secondary", "载体", 4, "转化型", None),
        ("丙七", "secondary", "载体", 5, "关系型", None),
        ("丁八", "secondary", "载体", 6, "功能转移型", None),
        ("戊九", "secondary", "载体", 7, "完成型", None),
        ("己十", "secondary", "载体", 8, "死亡型", None),
        ("庚一", "secondary", "载体", 9, "完成型", None),
        ("辛二", "secondary", "载体", 10, "完成型", None),
        ("壬三", "secondary", "载体", 11, "完成型", None),
        ("癸四", "secondary", "载体", 12, "完成型", None),
        ("子五", "secondary", "载体", 13, "完成型", None),
        ("丑六", "secondary", "载体", 14, "完成型", None),
        ("寅七", "secondary", "载体", 15, "完成型", None),
    ]
    return [
        {"name": n_, "role_class": rc, "arc_role": ar, "登场卷": vol,
         "预期退场": ex, **({"seat_ref": seat} if seat else {})}
        for n_, rc, ar, vol, ex, seat in people[:n]
    ]


def _char_base(n: int = 4) -> dict:
    return {"character_roster": _roster(n)}


class WorldSchemaCompat(unittest.TestCase):
    def test_base_passes(self):
        self.assertEqual(validate_world(_world_base()), [])

    def test_missing_seats_rejected(self):
        m = _world_base()
        m.pop("seats")
        self.assertTrue(validate_world(m))

    def test_lexicon_missing_category_rejected(self):
        m = _world_base()
        m["lexicon"]["banned_categories"].pop("现代计量")
        self.assertTrue(validate_world(m))

    def test_suppression_without_release_rejected(self):
        m = _world_base()
        m["dimension_costs"][1].pop("release")
        errs = validate_world(m)
        # schema 条件门先拦（required 报错），机器门中文复核在后——两级任一命中即缺陷
        self.assertTrue(any("release" in e or "解除通道" in e for e in errs))

    def test_irreversible_without_threshold_rejected(self):
        m = _world_base()
        m["dimension_costs"][0]["threshold"] = ""
        errs = validate_world(m)
        self.assertTrue(any("阈值" in e for e in errs))

    def test_protagonist_permanent_requires_book_soul_ref(self):
        m = _world_base()
        m["dimension_costs"][0]["bearer"] = "protagonist_permanent"
        errs = validate_world(m)
        self.assertTrue(any("book_soul_ref" in e for e in errs))
        # 回填 ref 后通过——主角永久代价只许回指 strategy 已声明条目
        m["dimension_costs"][0]["book_soul_ref"] = "book_soul.narrative_cruelty: 灵路焦结"
        self.assertEqual(validate_world(m), [])

    def test_seat_duplicate_rejected(self):
        m = _world_base()
        m["seats"][1]["name"] = "掌门"
        errs = validate_world(m)
        self.assertTrue(any("岗位重名" in e for e in errs))


class CharacterRosterGate(unittest.TestCase):
    def test_base_passes_with_world(self):
        errors, warns = validate_character(_char_base(4), scale="中篇", world=_world_base())
        self.assertEqual(errors, [])
        self.assertEqual(warns, [])  # 两席位均被认领或带 disposition

    def test_scale_bands(self):
        for scale, lo, hi in (("短篇", 2, 5), ("中篇", 3, 8), ("长篇", 5, 12), ("超长篇", 8, 16)):
            errors, _ = validate_character(_char_base(hi), scale=scale)
            self.assertEqual(errors, [], f"{scale} 上界 {hi} 应通过")
            errors, _ = validate_character(_char_base(hi + 1), scale=scale)
            self.assertTrue(any("超出" in e for e in errors), f"{scale} 超上界应拦")
            if lo > 1:
                errors, _ = validate_character(_char_base(lo - 1), scale=scale)
                self.assertTrue(any("低于" in e for e in errors), f"{scale} 低于下界应拦")

    def test_unknown_scale_rejected(self):
        errors, _ = validate_character(_char_base(4), scale="巨篇")
        self.assertTrue(any("未知 scale" in e for e in errors))

    def test_no_scale_skips_gate(self):
        errors, _ = validate_character(_char_base(17))
        self.assertEqual(errors, [])

    def test_duplicate_names_rejected(self):
        m = _char_base(4)
        m["character_roster"][1]["name"] = "沈青梧"
        errors, _ = validate_character(m, scale="中篇")
        self.assertTrue(any("重名" in e for e in errors))

    def test_missing_main_rejected(self):
        m = _char_base(4)
        for p in m["character_roster"]:
            p["role_class"] = "secondary"
        errors, _ = validate_character(m, scale="中篇")
        self.assertTrue(any("main" in e for e in errors))

    def test_seat_ref_unknown_rejected(self):
        m = _char_base(4)
        m["character_roster"][0]["seat_ref"] = "不存在席"
        errors, _ = validate_character(m, scale="中篇", world=_world_base())
        self.assertTrue(any("不存在的席位" in e for e in errors))

    def test_unclaimed_seat_warns_not_fails(self):
        world = _world_base()
        world["seats"][1]["disposition"] = None  # 执法长老已被 roster 认领，掌门带处置——造一个没人认领的
        world["seats"].append({"name": "客卿", "org": "玄阳宗", "duty": "外聘供奉",
                               "power_tier": "金丹", "first_consumption": "第2卷"})
        errors, warns = validate_character(_char_base(4), scale="中篇", world=world)
        self.assertEqual(errors, [])
        self.assertEqual(len(warns), 1)
        self.assertIn("客卿", warns[0])


class SeatDispositionGates(unittest.TestCase):
    """T37：处置承诺分级（待契约认领=error/待卷级班底=WARN/显式虚位=静默）+ essence schema + --project 自动解析。"""

    def test_pending_contract_claim_unclaimed_is_error(self):
        m = _char_base(4)
        m["character_roster"][0].pop("seat_ref")   # 沈青梧放弃认领掌门
        errors, _ = validate_character(m, scale="中篇", world=_world_base())
        self.assertTrue(any("待契约认领" in e and "掌门" in e for e in errors))

    def test_pending_volume_roster_unclaimed_warns(self):
        world = _world_base()
        world["seats"][0]["disposition"] = "待卷级班底"
        m = _char_base(4)
        m["character_roster"][0].pop("seat_ref")
        errors, warns = validate_character(m, scale="中篇", world=world)
        self.assertEqual(errors, [])
        self.assertTrue(any("待卷级班底" in w and "掌门" in w for w in warns))

    def test_explicit_vacancy_silent(self):
        world = _world_base()
        world["seats"][0]["disposition"] = "显式虚位"
        m = _char_base(4)
        m["character_roster"][0].pop("seat_ref")
        errors, warns = validate_character(m, scale="中篇", world=world)
        self.assertEqual(errors, [])
        self.assertFalse(any("掌门" in w for w in warns))

    def test_essence_schema_bounds(self):
        m = _char_base(4)
        m["character_roster"][0]["essence"] = "执念牌位（谈宗族失措三秒）｜仙门雅言避俚语"
        errors, _ = validate_character(m, scale="中篇")
        self.assertEqual(errors, [])
        m["character_roster"][0]["essence"] = "x" * 161
        errors, _ = validate_character(m, scale="中篇")
        self.assertTrue(any("essence" in e or "161" in e or "too long" in e for e in errors))

    def test_resolve_from_db_auto(self):
        import json
        import sqlite3
        import tempfile

        from novelos_validate_character import _resolve_from_db
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, metadata_json TEXT)")
            conn.execute(
                "CREATE TABLE planning_assets (id TEXT PRIMARY KEY, project_id TEXT, "
                "asset_type TEXT, scope_ref TEXT, revision INTEGER, status TEXT, "
                "content_resource_id TEXT, metadata_json TEXT)")
            conn.execute("INSERT INTO projects VALUES ('project:p1', ?)",
                         (json.dumps({"setup": {"scale": "长篇"}}, ensure_ascii=False),))
            conn.execute(
                "INSERT INTO planning_assets VALUES "
                "('pa:w1', 'project:p1', 'world_contract', 'book', 1, 'locked', NULL, ?)",
                (json.dumps(_world_base(), ensure_ascii=False),))
            conn.commit()
            conn.close()
            scale, world = _resolve_from_db("project:p1", db)
            self.assertEqual(scale, "长篇")
            self.assertEqual(world["seats"][0]["name"], "掌门")


if __name__ == "__main__":
    unittest.main()
