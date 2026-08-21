"""book_soul validate 语义校验测试：lineage 覆盖检查 + cadence_plan×scale 数字门。

schema 层由 jsonschema 保证（结构），本文件聚焦 validate() 在 schema 之外
新增的可判定规则。
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "novelos_validate_book_soul",
    Path(__file__).resolve().parent.parent / "scripts" / "novelos_validate_book_soul.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate = _mod.validate


def _base() -> dict:
    """合法最小 book_soul（十三字段，无可选扩展）。"""
    return {
        "schema_version": 2,
        "organizing_principle": "每一场硬仗都在一张谈判桌上完成，胜负在茶凉之前",
        "central_contradiction": "他必须练成仇人的手艺才能复仇 / 这门手艺每精进一分就把他变成仇人一分",
        "promise_cadence": "每卷级弧兑现一次核心承诺的一个侧面",
        "power_currency": "证据链：谁掌握完整证据链谁更强",
        "unresolved_claims": ["当年灭门案的主使是谁"],
        "costly_commitments": ["放弃即时复仇的爽快：主角五年内不动手，叙事必须维持悬置张力"],
        "protected_dignity": ["证人不受威胁连坐"],
        "forbidden_resolutions": ["禁止以巧合方式让关键证据自动出现"],
        "recurring_tests": ["新到手的力量第一次考验持有人"],
        "narrative_mercy": "仁慈体现在反派也有可理解的动机",
        "narrative_cruelty": "残酷落在主角最想保护的人身上",
        "deliberate_silences": ["暂不解释幕后组织的资金来源"],
    }


def _lineage(*fields: str, variation_fields: frozenset[str] = frozenset()) -> list[dict]:
    return [
        {
            "field": f,
            "source_type": "persona",
            "source_ref": "five_dimensions.career_track",
            "derivation": "从法证目光长出证据链组织方式" + ("（变奏：越界取极端化）" if f in variation_fields else ""),
            **({"variation": True} if f in variation_fields else {}),
        }
        for f in fields
    ]


class SchemaCompat(unittest.TestCase):
    def test_base_without_optional_fields_passes(self):
        self.assertEqual(validate(_base()), [])

    def test_lineage_and_cadence_plan_schema_valid(self):
        soul = _base()
        soul["lineage"] = _lineage("organizing_principle", "central_contradiction")
        soul["cadence_plan"] = {"fulfillment_count": 4, "interval_volumes": 2.0}
        self.assertEqual(validate(soul), [])

    def test_variation_flag_schema_valid(self):
        soul = _base()
        soul["lineage"] = _lineage(
            "organizing_principle", "central_contradiction",
            variation_fields=frozenset({"organizing_principle"}),
        )
        self.assertEqual(validate(soul), [])

    def test_unknown_lineage_field_rejected(self):
        soul = _base()
        soul["lineage"] = _lineage("organizing_principle", "central_contradiction")
        soul["lineage"][0]["field"] = "not_a_field"
        self.assertTrue(validate(soul))


class LineageCoverage(unittest.TestCase):
    def test_missing_organizing_principle_fails(self):
        soul = _base()
        soul["lineage"] = _lineage("central_contradiction", "promise_cadence")
        errors = validate(soul)
        self.assertTrue(any("organizing_principle" in e for e in errors))

    def test_missing_central_contradiction_fails(self):
        soul = _base()
        soul["lineage"] = _lineage("organizing_principle", "promise_cadence")
        errors = validate(soul)
        self.assertTrue(any("central_contradiction" in e for e in errors))

    def test_variation_entry_counts_toward_coverage(self):
        soul = _base()
        soul["lineage"] = _lineage(
            "organizing_principle", "central_contradiction",
            variation_fields=frozenset({"organizing_principle"}),
        )
        self.assertEqual(validate(soul), [])


class CadenceScaleGate(unittest.TestCase):
    def _with_plan(self, count: int) -> dict:
        soul = _base()
        soul["cadence_plan"] = {"fulfillment_count": count, "interval_volumes": 2.0}
        return soul

    def test_short_below_range_passes_upper_fails(self):
        self.assertEqual(validate(self._with_plan(2), "短篇（30万字以下）"), [])
        errors = validate(self._with_plan(3), "短篇（30万字以下）")
        self.assertTrue(any("失配" in e for e in errors))

    def test_medium_minimum_three(self):
        self.assertEqual(validate(self._with_plan(3), "中篇（30-100万字）"), [])
        self.assertTrue(validate(self._with_plan(2), "中篇（30-100万字）"))

    def test_long_minimum_three(self):
        self.assertEqual(validate(self._with_plan(4), "长篇（100-300万字）"), [])
        self.assertTrue(validate(self._with_plan(2), "长篇（100-300万字）"))

    def test_superlong_minimum_five(self):
        self.assertEqual(validate(self._with_plan(5), "超长篇（300万字以上）"), [])
        errors = validate(self._with_plan(3), "超长篇（300万字以上）")
        self.assertTrue(any("失配" in e for e in errors))

    def test_plan_without_scale_skips_gate(self):
        self.assertEqual(validate(self._with_plan(1)), [])

    def test_unknown_scale_rejected(self):
        errors = validate(self._with_plan(3), "巨篇")
        self.assertTrue(any("scale" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
