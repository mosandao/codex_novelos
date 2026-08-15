from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

from scripts.novelos_compose_prompt import (
    ASSET_DIRS,
    compose,
    evaluate_when,
    select_modules,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# 组装结果回归闸（纯方法论部分行数：主干 + 命中模块，不含输入数据区）。
# 防未来审查条款无节制回填主干——收紧前先确认模块化结构未被破坏。
SIZE_BUDGET = {
    "direction": 180,
    "direction-review": 120,
    "fusion": 280,
}

# 频道/模式标记行：用于断言「装了 A 就不能装 B」的路由正确性。
DIRECTION_CHANNEL_MARKERS = {
    "男频": "频道语法：男频",
    "女频": "频道语法：女频",
    "全向": "频道语法：全向",
}
FUSION_LIBRARY_MARKERS = {
    "empty": "首个人格",
    "small": "豁免可用，但样样留痕",
    "established": "硬闸全开",
}


def _ctx_direction(channel: str = "男频", model: str = "免费算法",
                   genre_null: bool = False, aesthetic: bool = True) -> dict:
    return {
        "setup": {
            "channel": channel,
            "platform_traits": {"model": model, "patience": "…", "reader_profile": "…"},
            "genre_profile": None if genre_null else {"power_currency_candidates": ["…"]},
            "aesthetic_styles": ["冷峻工业"] if aesthetic else [],
        }
    }


def _ctx_fusion(channel: str = "女频", library_count: int = 6,
                selected_count: int = 1) -> dict:
    return {
        "setup": {
            "channel": channel,
            "platform_traits": {"model": "付费订阅"},
            "genre_profile": {"typical_dilemmas": ["…"]},
            "aesthetic_styles": [],
        },
        "selected_count": selected_count,
        "persona_library_count": library_count,
    }


class ManifestIntegrity(unittest.TestCase):
    """manifest 与文件系统双向一致：引用的文件都在，目录里没有未声明孤儿。"""

    def test_manifest_files_exist_and_no_orphans(self):
        for asset, skill_dir in ASSET_DIRS.items():
            with self.subTest(asset=asset):
                manifest = json.loads(
                    (skill_dir / "modules" / "manifest.json").read_text(encoding="utf-8")
                )
                declared = {"manifest.json"}
                for entry in manifest["modules"]:
                    declared.add(entry["file"])
                    self.assertTrue(
                        (skill_dir / "modules" / entry["file"]).exists(),
                        f"{asset} 模块文件缺失: {entry['file']}",
                    )
                actual = {p.name for p in (skill_dir / "modules").iterdir()}
                self.assertEqual(actual, declared, f"{asset} modules/ 存在未声明文件")


class ManifestSchema(unittest.TestCase):
    """manifest v2：过 compose-manifest.schema.json 校验门 + 顶层声明断言。"""

    SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "compose-manifest.schema.json"

    def setUp(self):
        import jsonschema

        self.jsonschema = jsonschema
        self.schema = json.loads(self.SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_all_manifests_pass_schema(self):
        for asset, skill_dir in ASSET_DIRS.items():
            with self.subTest(asset=asset):
                data = json.loads(
                    (skill_dir / "modules" / "manifest.json").read_text(encoding="utf-8")
                )
                self.jsonschema.validate(data, self.schema)

    def test_top_level_declarations(self):
        direction = json.loads(
            (ASSET_DIRS["direction"] / "modules" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(direction["divergence"], "expansive")
        self.assertEqual(direction["decision_scope"], "propose_only")
        self.assertIn("persona_full", direction["data_slots"])

        review = json.loads(
            (ASSET_DIRS["direction-review"] / "modules" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(review["decision_scope"], "judge")
        self.assertNotIn("divergence", review)  # 审查档位跟随被审对象

        fusion = json.loads(
            (ASSET_DIRS["fusion"] / "modules" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(fusion["decision_scope"], "flag")
        self.assertEqual(fusion["divergence"], "expansive")

    def test_schema_rejects_unknown_fields(self):
        bad = {"modules": [{"id": "x", "file": "x.md", "when": {"field": "a", "equals": 1},
                            "typo": True}]}
        with self.assertRaises(self.jsonschema.ValidationError):
            self.jsonschema.validate(bad, self.schema)
        bad_top = {"modules": [], "divergence": "wild"}
        with self.assertRaises(self.jsonschema.ValidationError):
            self.jsonschema.validate(bad_top, self.schema)


class EnumCoverage(unittest.TestCase):
    """每个枚举维度（channel 三值、model 两值、genre 两态、库规模三档、原型数两档）
    至少命中一个模块——向导新增取值后漏配模块在这里红灯。"""

    def test_direction_all_enums_hit(self):
        cases = [
            (_ctx_direction(channel=c), f"channel={c}") for c in DIRECTION_CHANNEL_MARKERS
        ] + [
            (_ctx_direction(model=m), f"model={m}") for m in ("免费算法", "付费订阅")
        ] + [
            (_ctx_direction(genre_null=True), "genre=null"),
            (_ctx_direction(genre_null=False), "genre=present"),
        ]
        for ctx, label in cases:
            with self.subTest(case=label):
                self.assertTrue(
                    select_modules(ASSET_DIRS["direction"], ctx),
                    f"direction 在 {label} 下一个模块都没命中",
                )

    def test_fusion_all_enums_hit(self):
        cases = [
            (_ctx_fusion(channel=c), f"channel={c}")
            for c in ("男频", "女频", "全向")
        ] + [
            (_ctx_fusion(library_count=n), f"library={n}")
            for n in (0, 1, 4, 5, 11)
        ] + [
            (_ctx_fusion(selected_count=1), "selected=1"),
            (_ctx_fusion(selected_count=3), "selected=3"),
        ]
        for ctx, label in cases:
            with self.subTest(case=label):
                self.assertTrue(
                    select_modules(ASSET_DIRS["fusion"], ctx),
                    f"fusion 在 {label} 下一个模块都没命中",
                )


class RoutingCorrectness(unittest.TestCase):
    """路由正确性：装 A 不装 B；库规模三档互斥。"""

    def test_direction_channel_exclusive(self):
        for channel, marker in DIRECTION_CHANNEL_MARKERS.items():
            out = compose(ASSET_DIRS["direction"], _ctx_direction(channel=channel), [])
            self.assertIn(marker, out)
            for other, other_marker in DIRECTION_CHANNEL_MARKERS.items():
                if other != channel:
                    self.assertNotIn(other_marker, out, f"{channel} 项目混入了 {other} 模块")

    def test_direction_platform_and_genre_exclusive(self):
        out_free = compose(ASSET_DIRS["direction"], _ctx_direction(model="免费算法"), [])
        self.assertIn("免费算法平台", out_free)
        self.assertNotIn("付费订阅平台", out_free)
        out_null = compose(ASSET_DIRS["direction"], _ctx_direction(genre_null=True), [])
        self.assertIn("缺位", out_null)
        self.assertNotIn("题材信息包消费（genre_profile 非空）", out_null)

    def test_fusion_library_tiers_exclusive(self):
        tiers = {
            "empty": _ctx_fusion(library_count=0),
            "small": _ctx_fusion(library_count=3),
            "established": _ctx_fusion(library_count=7),
        }
        for tier, ctx in tiers.items():
            out = compose(ASSET_DIRS["fusion"], ctx, [])
            for other_tier, marker in FUSION_LIBRARY_MARKERS.items():
                if other_tier == tier:
                    self.assertIn(marker, out)
                else:
                    self.assertNotIn(marker, out, f"库={tier} 混入了 {other_tier} 模块")

    def test_fusion_male_carries_rule_hierarchy(self):
        out = compose(ASSET_DIRS["fusion"], _ctx_fusion(channel="男频"), [])
        self.assertIn("规则的力量层级观", out)
        female = compose(ASSET_DIRS["fusion"], _ctx_fusion(channel="女频"), [])
        self.assertNotIn("规则的力量层级观", female)

    def test_review_matches_direction_channel(self):
        out = compose(ASSET_DIRS["direction-review"], _ctx_direction(channel="女频"), [])
        self.assertIn("女频（规则与关系轴）", out)
        self.assertNotIn("男频（力量轴）", out)


class OutputContract(unittest.TestCase):
    """输出契约与自检汇总：主干任务节保留，附加自检收集到尾部。"""

    def test_direction_contract_and_tail_checklist(self):
        out = compose(ASSET_DIRS["direction"], _ctx_direction(), [])
        self.assertIn("# 故事方向", out)
        self.assertIn("## book_soul 十三字段", out)
        self.assertIn("交付前自检", out)
        # 男频附加自检（力量/秩序代价面）必须出现在输出里
        self.assertIn("力量/秩序代价面", out)

    def test_fusion_contract_and_tail_checklist(self):
        ctx = _ctx_fusion(channel="男频", library_count=7)
        out = compose(ASSET_DIRS["fusion"], ctx, [])
        self.assertIn("# 作者签名融合", out)
        self.assertIn('"parent_version_id"', out)
        # 成库 + 男频的附加自检（跨批次撞车 + 规则层级观）出现在尾部汇总
        self.assertIn("跨批次撞车检查", out)
        self.assertIn("规则层级观", out)


class SizeBudget(unittest.TestCase):
    """体量回归闸：纯方法论部分（空数据区组装）不得超过预算。"""

    def test_methodology_within_budget(self):
        worst_direction = _ctx_direction()  # 男频+免费+genre+美学 = 最多模块
        worst_fusion = _ctx_fusion(channel="男频", library_count=7, selected_count=3)
        for asset, ctx in (
            ("direction", worst_direction),
            ("direction-review", _ctx_direction(channel="女频")),
            ("fusion", worst_fusion),
        ):
            out = compose(ASSET_DIRS[asset], ctx, [])
            lines = len(out.splitlines())
            self.assertLessEqual(
                lines, SIZE_BUDGET[asset],
                f"{asset} 组装结果 {lines} 行超预算 {SIZE_BUDGET[asset]}——"
                "检查是否有人把条件条款回填了主干",
            )


class ComposeDeterminism(unittest.TestCase):
    """路由确定性：同 context 两次组装 byte 级一致（三个资产 × 枚举边界）。"""

    def test_compose_is_pure_function(self):
        cases = [
            (ASSET_DIRS["direction"], _ctx_direction()),
            (ASSET_DIRS["direction"], _ctx_direction(channel="女频", model="付费订阅")),
            (ASSET_DIRS["direction-review"], _ctx_direction(channel="全向")),
            (ASSET_DIRS["fusion"], _ctx_fusion(channel="女频", library_count=0, selected_count=1)),
            (ASSET_DIRS["fusion"], _ctx_fusion(channel="男频", library_count=9, selected_count=3)),
        ]
        for skill_dir, ctx in cases:
            with self.subTest(asset=skill_dir.name):
                a = compose(skill_dir, ctx, [])
                b = compose(skill_dir, ctx, [])
                self.assertEqual(a, b)


class WhenEvaluator(unittest.TestCase):
    """when 求值器：is_null / not_null / non_empty / all 组合。"""

    def test_evaluator_semantics(self):
        ctx = {"setup": {"genre_profile": None, "aesthetic_styles": []}, "n": 3}
        self.assertTrue(evaluate_when({"field": "setup.genre_profile", "is_null": True}, ctx))
        self.assertFalse(evaluate_when({"field": "setup.genre_profile", "not_null": True}, ctx))
        self.assertFalse(evaluate_when({"field": "setup.aesthetic_styles", "non_empty": True}, ctx))
        self.assertTrue(evaluate_when(
            {"all": [{"query": "n", "op": ">", "value": 0},
                     {"query": "n", "op": "<", "value": 5}]}, ctx))


class CrossArchetypeSimilarity(unittest.TestCase):
    """校验门跨原型查重：高重合 WARN、低重合静默、选中原型不比对。"""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "novelos_create_project",
            REPO_ROOT / "scripts" / "novelos_create_project.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.mod = mod

    def _arch(self, slug: str, principles: list[str]) -> dict:
        return {
            "id": slug,
            "revision": 1,
            "display_name": slug,
            "signature": {
                "sympathies": [f"{slug} 同情者"],
                "distrusts": [f"{slug} 警惕的倾向"],
                "recurring_attention": [f"{slug} 反复看的题材"],
                "narrative_principles": principles,
                "forbidden_conveniences": [f"{slug} 禁止的捷径"],
                "expression_preferences": [f"{slug} 的笔触"],
                "negative_constraints": [f"{slug} 的底线"],
            },
        }

    def test_high_overlap_warns_and_low_silent(self):
        cfg_list = [
            self._arch("aaa", ["一切力量兑付必有出处与利息，账目必平"]),
            self._arch("bbb", ["温柔的人才能走到最后"]),
        ]
        candidate = {
            "signature": {
                "sympathies": ["被账目压弯的普通人", "同情者样本二"],
                "distrusts": ["白嫖的浪漫", "警惕样本二"],
                "recurring_attention": ["账本与利息的题材", "题材样本二"],
                "narrative_principles": ["一切力量兑付必有出处与利息，账目必平", "主原则样本二"],
                "forbidden_conveniences": ["无账目的爽点", "捷径样本二"],
                "expression_preferences": ["冷账房笔触", "笔触样本二"],
                "negative_constraints": ["账目必平的底线", "底线样本二"],
            }
        }
        warns = self.mod.cross_archetype_similarity(candidate, cfg_list, set())
        self.assertTrue(
            any("aaa" in w for w in warns),
            f"与 aaa 高重合应触发 WARN，实际 {warns}",
        )
        self.assertFalse(any("bbb" in w for w in warns), "与 bbb 低重合不应 WARN")

    def test_selected_archetype_skipped(self):
        cfg_list = [self._arch("aaa", ["一切力量兑付必有出处与利息，账目必平"])]
        candidate = {"signature": {
            f: ["一切力量兑付必有出处与利息，账目必平"] for f in self.mod.SIGNATURE_FIELDS
        }}
        selected = {"creator-profile-version:aaa:1"}
        self.assertEqual(
            self.mod.cross_archetype_similarity(candidate, cfg_list, selected), [],
            "选中原型不参与跨原型查重（其逐字复制由 validate_candidate 另查）",
        )


if __name__ == "__main__":
    unittest.main()
