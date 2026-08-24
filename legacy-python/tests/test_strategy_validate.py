"""strategy metadata validate 语义校验测试：上游消费覆盖 + 阶段数×档位 +
存债连续上限 + 中盘续命 + 终局纪律（收束预算/字数下限/open 模式）。

schema 层由 jsonschema 保证（结构/if-then），本文件聚焦 validate() 在 schema
之外新增的可判定规则，以及 schema 条件门的冒烟。
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_spec = importlib.util.spec_from_file_location(
    "novelos_validate_strategy",
    Path(__file__).resolve().parents[2] / "legacy-python" / "scripts" / "novelos_validate_strategy.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
validate = _mod.validate


def _stage(i: int, payoff: str = "heavy") -> dict:
    return {
        "name": f"阶段{i}",
        "word_range": {"min": 20, "max": 40},
        "dominant_spiral": "螺旋A" if i % 2 == 0 else "螺旋B",
        "payoff": payoff,
        "progress_types": ["信息", "能力"],
        "pov": "主角单视角",
        "costs": [{
            "type": "irreversible",
            "landing": "plot_character",
            "form": "推动剧情的盟友战死",
            "source": {"source_type": "book_soul_field", "ref": "narrative_cruelty"},
        }],
        "end_condition": "势力版图不可逆改变",
        "cause_bridge": "血案线索移交下一阶段",
    }


def _base(n_stages: int = 4, payoff_cycle=("heavy", "debt")) -> dict:
    stages = [_stage(i + 1, payoff_cycle[i % len(payoff_cycle)]) for i in range(n_stages)]
    return {
        "schema_version": 1,
        "consumption": [
            {"output": o, "translation": "翻译", "ref": "架构机制X"}
            for o in ("rhythm_table", "reveal_ladder", "promise_cadence", "power_escalation",
                      "spiral_rotation", "engine_config", "upstream_receipts")
        ],
        "genre_stage_form": "境界突破弧：阶段结束判据为境界/对手等级升档",
        "persona_usages": {
            "gaze": "法证目光：证据链先碎片后拼图",
            "blindspot_gate": "大战写奏报（cannot_write：大规模战争）",
            "pov_contract": "主角单视角，第三阶段起双人交替",
            "inventory": "工程审计经验供第二阶段博弈弧",
        },
        "stages": stages,
        "claim_ledger": [
            {"claim": "灭门案主使是谁", "disposition": "terminal", "anchor": "阶段4"},
            {"claim": "组织资金来源", "disposition": "silence", "anchor": "全书沉默"},
        ],
        "pairing_cycle": {"debt_streak_limit": 2},
        "midpoint_renewal": {"stage": 2, "form": "换地图", "note": "旧地图人际部分保留"},
        "terminal_mode": "closed",
        "terminal": {"closure_budget": 4, "echo": "终局兑付回指组织原则", "word_floor": 20},
        "handoffs": {
            "character_arcs": [{"stage": 1, "requirement": "师徒弧推进"}],
            "world_changes": [{"stage": 1, "change": "宗门格局重组"}],
        },
        "decision_points": [],
    }


class SchemaCompat(unittest.TestCase):
    def test_base_passes_with_and_without_scale(self):
        self.assertEqual(validate(_base()), [])
        self.assertEqual(validate(_base(), "长篇（100-300万字）"), [])

    def test_missing_consumption_row_fails(self):
        data = _base()
        data["consumption"] = data["consumption"][:-1]  # 缺 upstream_receipts
        data["consumption"][0] = dict(data["consumption"][0])  # 保持 7 行但重复枚举
        data["consumption"][0]["output"] = "rhythm_table"
        data["consumption"].append({"output": "engine_config", "translation": "x", "ref": "y"})
        errors = validate(data)
        self.assertTrue(any("upstream_receipts" in e or "上游消费表缺行" in e for e in errors))

    def test_suppression_cost_requires_release(self):
        data = _base()
        data["stages"][0]["costs"] = [{
            "type": "suppression", "landing": "protagonist_temporary",
            "form": "金手指封印一卷",
            "source": {"source_type": "book_soul_field", "ref": "costly_commitments"},
        }]  # 无 release
        errors = validate(data)
        self.assertTrue(any("release" in e for e in errors))

    def test_protagonist_permanent_requires_book_soul_declaration(self):
        data = _base()
        data["stages"][0]["costs"] = [{
            "type": "irreversible", "landing": "protagonist_permanent",
            "form": "主角灵魂永久损伤",
            "source": {"source_type": "book_soul_field", "ref": "narrative_cruelty"},
        }]  # 无 declared_in_book_soul
        errors = validate(data)
        self.assertTrue(any("declared_in_book_soul" in e for e in errors))

    def test_protagonist_permanent_with_declaration_passes(self):
        data = _base()
        data["stages"][0]["costs"] = [{
            "type": "irreversible", "landing": "protagonist_permanent",
            "form": "主角灵魂永久损伤（book_soul 声明的赌注）",
            "source": {"source_type": "book_soul_field", "ref": "narrative_cruelty"},
            "declared_in_book_soul": True, "book_soul_ref": "narrative_cruelty",
        }]
        self.assertEqual(validate(data), [])


class ScaleStageGate(unittest.TestCase):
    def test_short_form_rejects_four_stages(self):
        errors = validate(_base(n_stages=4), "短篇（30万字以下）")
        self.assertTrue(any("超出 短篇 档区间" in e for e in errors))

    def test_changduo_range_boundaries(self):
        self.assertEqual(validate(_base(n_stages=3), "长篇（100-300万字）"), [])
        self.assertEqual(validate(_base(n_stages=8), "长篇（100-300万字）"), [])
        errors = validate(_base(n_stages=9), "长篇（100-300万字）")
        self.assertTrue(any("超出 长篇 档区间" in e for e in errors))

    def test_chaochangpin_floor(self):
        self.assertEqual(validate(_base(n_stages=5), "超长篇（300万字以上）"), [])
        errors = validate(_base(n_stages=4), "超长篇（300万字以上）")
        self.assertTrue(any("超出 超长篇 档区间" in e for e in errors))

    def test_unknown_scale_flagged(self):
        errors = validate(_base(), "中短篇")
        self.assertTrue(any("不认识的档位" in e for e in errors))

    def test_no_scale_skips_gate(self):
        self.assertEqual(validate(_base(n_stages=9)), [])


class DebtStreak(unittest.TestCase):
    def test_three_consecutive_debt_stages_fail(self):
        data = _base(n_stages=4, payoff_cycle=("heavy", "debt"))
        for st in data["stages"]:
            st["payoff"] = "debt"
        data["stages"][0]["payoff"] = "heavy"  # 只留一个兑付段：后 3 连 debt
        errors = validate(data)
        self.assertTrue(any("连续纯存债" in e for e in errors))

    def test_alternating_debt_passes(self):
        self.assertEqual(validate(_base(n_stages=4, payoff_cycle=("heavy", "debt"))), [])

    def test_all_debt_book_fails(self):
        data = _base(n_stages=3, payoff_cycle=("debt",))
        errors = validate(data)
        self.assertTrue(any("只种不收" in e for e in errors))


class MidpointAndTerminal(unittest.TestCase):
    def test_three_stages_require_midpoint(self):
        data = _base(n_stages=3)
        del data["midpoint_renewal"]
        errors = validate(data)
        self.assertTrue(any("midpoint_renewal" in e for e in errors))

    def test_midpoint_stage_out_of_range(self):
        data = _base(n_stages=4)
        data["midpoint_renewal"]["stage"] = 9
        errors = validate(data)
        self.assertTrue(any("不在阶段表内" in e for e in errors))

    def test_terminal_claims_over_budget_fail(self):
        data = _base()
        data["claim_ledger"] = [
            {"claim": f"claim{i}", "disposition": "terminal", "anchor": "阶段4"}
            for i in range(5)  # 预算 4
        ]
        errors = validate(data)
        self.assertTrue(any("超收束预算" in e for e in errors))

    def test_terminal_word_floor_enforced(self):
        data = _base()
        data["stages"][-1]["word_range"]["min"] = 10  # < floor 20
        errors = validate(data)
        self.assertTrue(any("终局阶段字数下限" in e for e in errors))

    def test_open_mode_requires_note_and_skips_terminal(self):
        data = _base()
        data["terminal_mode"] = "open"
        data.pop("terminal")
        errors = validate(data)  # schema: open 需 open_note
        self.assertTrue(any("open_note" in e for e in errors))
        data["open_note"] = "柯南式开放引擎：单元机器持续供压，主线按季爆发"
        data["claim_ledger"] = [
            {"claim": f"claim{i}", "disposition": "terminal", "anchor": "阶段4"}
            for i in range(9)  # open 模式不查收束预算
        ]
        self.assertEqual(validate(data), [])


if __name__ == "__main__":
    unittest.main()
