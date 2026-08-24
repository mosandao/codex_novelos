"""architecture metadata validate 语义校验测试：血缘双源覆盖 + 油耗×scale +
主线密度一致性 + 空窗上限×scale + 单元弧粒度。

schema 层由 jsonschema 保证（结构，含耦合条目必填=孤岛不合法），本文件聚焦
validate() 在 schema 之外新增的可判定规则。
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_spec = importlib.util.spec_from_file_location(
    "novelos_validate_architecture",
    Path(__file__).resolve().parents[2] / "legacy-python" / "scripts" / "novelos_validate_architecture.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate = _mod.validate


def _mechanism(name: str = "悬赏阶梯", *, with_persona: bool = True) -> dict:
    sources = [{"source_type": "direction_field", "ref": "book_soul.power_currency"}]
    if with_persona:
        sources.append({"source_type": "persona_part",
                        "ref": "five_dimensions.career_track（法证目光→输入源）"})
    return {
        "name": name,
        "sources": sources,
        "rhythm": "每单元弧一次兑现切片，每卷一次大兑现",
        "downstream": ["strategy"],
        "coupling": {"form": "io", "spec": "A 的公开验证声誉喂 B 的高赌注委托输入"},
    }


def _base() -> dict:
    """合法最小 architecture metadata（双层引擎 + 双源血缘 + 中密度主线）。"""
    return {
        "schema_version": 1,
        "mechanisms": [
            _mechanism("悬赏阶梯"),
            {**_mechanism("主线承载单元注入"),
             "coupling": {"form": "quota", "spec": "每 3 单元注入 1 个承载单元（线索/压力前置）"}},
        ],
        "mainline_density": {
            "tier": "中", "beats_per_volume": 0.5, "gap_limit_volumes": 2,
            "burst_positions": ["卷尾"],
        },
        "unit_arc": {"min_chapters": 2, "max_chapters": 5},
        "engines": {
            "production": {"escalation_levels": 3, "fuel": "一单活/一个过客/一次考验"},
            "integrator": {"escalation_levels": 3},
        },
    }


class SchemaCompat(unittest.TestCase):
    def test_base_passes_without_scale(self):
        self.assertEqual(validate(_base()), [])

    def test_base_passes_with_scale(self):
        self.assertEqual(validate(_base(), scale="长篇（100-300万字）"), [])

    def test_coupling_required_by_schema(self):
        data = _base()
        del data["mechanisms"][0]["coupling"]  # 孤岛：schema 层即不合法
        self.assertTrue(validate(data))

    def test_mechanism_floor_of_two(self):
        data = _base()
        data["mechanisms"] = data["mechanisms"][:1]
        self.assertTrue(validate(data))


class LineageDualSource(unittest.TestCase):
    def test_missing_persona_source_fails(self):
        data = _base()
        for m in data["mechanisms"]:
            m["sources"] = [s for s in m["sources"] if s["source_type"] != "persona_part"]
        errors = validate(data)
        self.assertTrue(any("persona_part" in e for e in errors))

    def test_missing_direction_source_fails(self):
        data = _base()
        for m in data["mechanisms"]:
            m["sources"] = [{"source_type": "persona_part", "ref": "inner_tension"}]
        errors = validate(data)
        self.assertTrue(any("direction_field" in e for e in errors))


class EscalationScaleGate(unittest.TestCase):
    def test_chaochangpeng_requires_five_levels(self):
        data = _base()
        errors = validate(data, scale="超长篇（300万字以上）")
        self.assertTrue(any("escalation_levels=3 低于 超长篇" in e for e in errors))

    def test_duanpan_allows_two_levels(self):
        data = _base()
        data["engines"]["production"]["escalation_levels"] = 2
        data["engines"]["integrator"]["escalation_levels"] = 2
        data["mainline_density"]["gap_limit_volumes"] = 1  # 短篇空窗上限 1 卷
        self.assertEqual(validate(data, scale="短篇（30万字以下）"), [])

    def test_unknown_scale_rejected(self):
        errors = validate(_base(), scale="巨篇")
        self.assertTrue(any("不认识的档位" in e for e in errors))

    def test_no_scale_skips_gate(self):
        data = _base()
        data["engines"]["production"]["escalation_levels"] = 1
        self.assertEqual(validate(data), [])


class DensityConsistency(unittest.TestCase):
    def test_low_tier_with_medium_beats_fails(self):
        data = _base()
        data["mainline_density"]["tier"] = "低"
        data["mainline_density"]["beats_per_volume"] = 0.7
        errors = validate(data)
        self.assertTrue(any("失配" in e for e in errors))

    def test_high_tier_requires_at_least_one_beat(self):
        data = _base()
        data["mainline_density"]["tier"] = "高"
        data["mainline_density"]["beats_per_volume"] = 0.5
        self.assertTrue(any("失配" in e for e in validate(data)))

    def test_low_density_conan_model_passes(self):
        """柯南/X 档案形态：低密度 + 空窗上限 ≤ 档位上限 + 爆发点设计 = 合法。"""
        data = _base()
        data["mainline_density"] = {
            "tier": "低", "beats_per_volume": 0.3, "gap_limit_volumes": 3,
            "burst_positions": ["卷首", "卷尾"],
        }
        data["engines"]["production"]["escalation_levels"] = 5
        data["engines"]["integrator"]["escalation_levels"] = 5
        self.assertEqual(validate(data, scale="超长篇（300万字以上）"), [])

    def test_gap_exceeding_scale_cap_fails(self):
        data = _base()
        data["mainline_density"]["gap_limit_volumes"] = 4  # 长篇上限 3
        errors = validate(data, scale="长篇（100-300万字）")
        self.assertTrue(any("空窗上限" in e for e in errors))


class UnitArcGranularity(unittest.TestCase):
    def test_inverted_bounds_fail(self):
        data = _base()
        data["unit_arc"] = {"min_chapters": 5, "max_chapters": 2}
        self.assertTrue(any("粒度倒置" in e for e in validate(data)))


if __name__ == "__main__":
    unittest.main()
