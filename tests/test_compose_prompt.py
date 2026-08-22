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
# 2026-08 方向阶段反向审查批次有意扩充（七维比较表/证伪清单/负向承诺/
# 血缘逐字段/strength 通道），direction 190→210、direction-review 120 保持。
SIZE_BUDGET = {
    "direction": 210,
    "direction-review": 120,
    "fusion": 280,
    "kernel-fusion": 200,
    # 2026-08 方向阶段反向审查批次有意扩充（T33）：direction 190→210、direction-review 120 保持。
    # 2026-08 架构阶段双层引擎重构（T34）：architecture 130→170（嵌套模型/密度声明/耦合规格/
    # 题材与美学翻译位/验证记录落正文）；architecture-review 60 保持（重写在原预算内）。
    # 2026-08 战略阶段深度整改（T35）：strategy 110→150（七行消费表/题材阶段形态/persona 四用法/
    # 代价类型学/承诺-债务周期/档位区间/中盘终局/交接清单）；strategy-review 60→75（实测 63）。
    # 2026-08 人物‖世界串行化与结构化出口（T36）：world-contract 150→170（上游消费表/岗位表/
    # 代价两轴/语域机器可读/persona 盲区门/中盘演化预留/open 喂料）；character-contract 130→175
    # （世界移交消费/persona 四用法/strategy 挂接/席位认领/roster 档位）；双侧 review 与
    # volume/chapter-draft/prose-review 在原预算内（实测 63/53/70/42/49/54）。
    # 2026-08 人物阶段深度整改（T37）：character-contract 175→180（实测 175 顶格——essence
    # 人物卡出口/写法对照/自检两项）；volume/chapter-plan/draft/prose 在原预算内。
    "architecture": 170,
    "architecture-review": 60,
    "strategy": 150,
    "strategy-review": 75,
    "world-contract": 170,
    "world-contract-review": 70,
    "character-contract": 180,
    "character-contract-review": 70,
    "story-arc": 100,
    "story-arc-review": 70,
    "volume-outline": 100,
    "volume-outline-review": 70,
    "chapter-plan": 110,
    "chapter-plan-review": 70,
    "chapter-draft": 75,
    "prose-review": 65,
    "continuity-extraction": 35,
    "continuity-review": 30,
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
                kernel: bool = True) -> dict:
    setup = {
        "channel": channel,
        "platform": "起点",
        "platform_traits": {"model": "付费订阅"},
        "genre_profile": None,
        "aesthetic_styles": ["冷峻"],
    }
    if kernel:
        setup["author_kernel"] = {
            "mode": "select", "kernel_version_id": "creator-profile-version:k:1",
            "subject_hash": "sha256:" + "d" * 64, "kernel_hints": {}}
    return {"setup": setup, "persona_library_count": library_count}


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
        worst_fusion = _ctx_fusion(channel="男频", library_count=7)
        for asset, ctx in (
            ("direction", worst_direction),
            ("direction-review", _ctx_direction(channel="女频")),
            ("fusion", worst_fusion),
            ("kernel-fusion", {"setup": {}, "mode": "revise"}),
            ("architecture", worst_direction),
            ("architecture-review", _ctx_direction(channel="女频")),
            ("strategy", worst_direction),
            ("strategy-review", _ctx_direction(channel="女频")),
            ("world-contract", worst_direction),
            ("world-contract-review", worst_direction),
            ("character-contract", _ctx_direction(channel="女频")),
            ("character-contract-review", _ctx_direction(channel="女频")),
            ("story-arc", worst_direction),
            ("story-arc-review", worst_direction),
            ("volume-outline", worst_direction),
            ("volume-outline-review", worst_direction),
            ("chapter-plan", _ctx_direction(channel="女频")),
            ("chapter-plan-review", _ctx_direction(channel="女频")),
            ("chapter-draft", _ctx_direction(channel="女频")),
            ("prose-review", _ctx_direction(channel="女频")),
            ("continuity-extraction", worst_direction),
            ("continuity-review", worst_direction),
        ):
            out = compose(ASSET_DIRS[asset], ctx, [])
            lines = len(out.splitlines())
            self.assertLessEqual(
                lines, SIZE_BUDGET[asset],
                f"{asset} 组装结果 {lines} 行超预算 {SIZE_BUDGET[asset]}——"
                "检查是否有人把条件条款回填了主干",
            )


class ArchitectureRouting(unittest.TestCase):
    """architecture 双端：频道/平台模块互斥 + 审查端与生成端同维度路由。"""

    def test_channel_exclusive(self):
        for channel, marker in (("男频", "频道轴的架构翻译：男频"), ("女频", "频道轴的架构翻译：女频")):
            ctx = _ctx_direction(channel=channel)
            out = compose(ASSET_DIRS["architecture"], ctx, [])
            self.assertIn(marker, out)
        both = compose(ASSET_DIRS["architecture"], _ctx_direction(), [])
        self.assertNotIn("频道轴的架构翻译：女频", both)
        self.assertIn("代价条款须引用 direction 声明的代价形态", both)  # 阶段2补丁落地

    def test_platform_exclusive(self):
        free = compose(ASSET_DIRS["architecture"], _ctx_direction(), [])
        self.assertIn("平台节奏适配：免费算法", free)
        paid = compose(ASSET_DIRS["architecture"], _ctx_direction(model="付费订阅"), [])
        self.assertIn("平台节奏适配：付费订阅", paid)
        self.assertNotIn("平台节奏适配：免费算法", paid)

    def test_review_matches_generation(self):
        for channel in ("男频", "女频", "全向"):
            ctx = _ctx_direction(channel=channel)
            gen = compose(ASSET_DIRS["architecture"], ctx, [])
            rev = compose(ASSET_DIRS["architecture-review"], ctx, [])
            axis = {"男频": "男频", "女频": "女频", "全向": "全向"}[channel]
            self.assertIn(f"频道轴的架构翻译：{axis}", gen)
            self.assertIn(f"频道轴审查：{axis}", rev)


class StrategyRouting(unittest.TestCase):
    """strategy 双端：模块互斥 + 审查对偶 + 主干增强断言。"""

    def test_channel_and_platform_routing(self):
        ctx = _ctx_direction()  # 男频 + 免费
        out = compose(ASSET_DIRS["strategy"], ctx, [])
        self.assertIn("频道轴的阶段收益：男频", out)
        self.assertIn("平台节奏：免费算法", out)
        self.assertNotIn("频道轴的阶段收益：女频", out)
        self.assertIn("阶段数区间", out)  # T35：体量指引档位区间化（旧 ≥20 万下限废除）
        self.assertIn("晋升-收费配对表", out)

    def test_review_dual(self):
        rev = compose(ASSET_DIRS["strategy-review"], _ctx_direction(channel="女频"), [])
        self.assertIn("频道轴审查：女频", rev)
        self.assertIn("七行翻译", rev)  # T35：上游消费表 v3 全覆盖核验


class P2RoutingBatch(unittest.TestCase):
    """world / character 双端路由与主干增强断言。"""

    def test_world_genre_modules_and_lexicon(self):
        present = compose(ASSET_DIRS["world-contract"], _ctx_direction(), [])
        self.assertIn("语域取材：题材信息包非空", present)
        self.assertIn("术语语域表（必产节，正文执行端消费）", present)
        absent = compose(ASSET_DIRS["world-contract"],
                         _ctx_direction(genre_null=True), [])
        self.assertIn("语域取材：题材信息包缺位", absent)
        rev = compose(ASSET_DIRS["world-contract-review"], _ctx_direction(), [])
        self.assertIn("术语语域表", rev)

    def test_character_channel_modules_and_handover(self):
        female = compose(ASSET_DIRS["character-contract"], _ctx_direction(channel="女频"), [])
        self.assertIn("频道轴的人物层：女频（道德债权账户）", female)
        self.assertIn("架构移交清单消费", female)
        male = compose(ASSET_DIRS["character-contract"], _ctx_direction(), [])
        self.assertIn("频道轴的人物层：男频（力量兑现载体）", male)
        self.assertNotIn("道德债权账户）", male)
        rev = compose(ASSET_DIRS["character-contract-review"], _ctx_direction(channel="女频"), [])
        self.assertIn("频道轴审查：女频", rev)
        self.assertIn("移交清单消费完整", rev)


    def test_arc_and_volume_enhancements(self):
        arc = compose(ASSET_DIRS["story-arc"], _ctx_direction(), [])
        self.assertIn("弧↔卷映射方法", arc)
        self.assertIn("种收台账", arc)
        vol = compose(ASSET_DIRS["volume-outline"], _ctx_direction(), [])
        self.assertIn("每 20-30 万字一个副高潮", vol)
        self.assertIn("四段结构", vol)
        arc_rev = compose(ASSET_DIRS["story-arc-review"], _ctx_direction(channel="女频"), [])
        self.assertIn("弧↔卷映射表", arc_rev)
        self.assertIn("频道轴审查：女频", arc_rev)
        vol_rev = compose(ASSET_DIRS["volume-outline-review"], _ctx_direction(channel="女频"), [])
        self.assertIn("卷内节奏量化", vol_rev)
        self.assertIn("频道轴审查：女频", vol_rev)


    def test_chapter_plan_enhancements(self):
        plan = compose(ASSET_DIRS["chapter-plan"], _ctx_direction(channel="女频"), [])
        self.assertIn("场景序列指引（接章级单元机器三拍）", plan)
        self.assertIn("债权兑付对接", plan)
        rev = compose(ASSET_DIRS["chapter-plan-review"], _ctx_direction(channel="女频"), [])
        self.assertIn("三拍完整", rev)
        self.assertIn("唯一权威源", rev)
        self.assertIn("频道轴审查：女频", rev)


    def test_writing_threshold_collapse_and_lexicon(self):
        from scripts.novelos_compose_prompt import load_manifest
        draft = compose(ASSET_DIRS["chapter-draft"], _ctx_direction(channel="女频"), [])
        self.assertIn("persona 四项执行纪律", draft)
        self.assertIn("唯一权威源", draft)
        self.assertNotIn("≤110 字", draft)  # 数字阈值已收口到 craft 卡
        self.assertIn("频道轴的正文笔触：女频", draft)
        rev = compose(ASSET_DIRS["prose-review"], _ctx_direction(channel="女频"), [])
        self.assertIn("计量穿越", rev)  # 术语语域检查落地
        self.assertIn("频道轴与力量货币依据", rev)
        self.assertIn("频道轴审查：女频", rev)
        crafts = load_manifest(ASSET_DIRS["prose-review"])["craft_refs"]
        self.assertIn("worldview-lexicon", crafts)


class ComposeDeterminism(unittest.TestCase):
    """路由确定性：同 context 两次组装 byte 级一致（三个资产 × 枚举边界）。"""

    def test_compose_is_pure_function(self):
        cases = [
            (ASSET_DIRS["direction"], _ctx_direction()),
            (ASSET_DIRS["direction"], _ctx_direction(channel="女频", model="付费订阅")),
            (ASSET_DIRS["direction-review"], _ctx_direction(channel="全向")),
            (ASSET_DIRS["fusion"], _ctx_fusion(channel="女频", library_count=0)),
            (ASSET_DIRS["fusion"], _ctx_fusion(channel="男频", library_count=9)),
        ]
        for skill_dir, ctx in cases:
            with self.subTest(asset=skill_dir.name):
                a = compose(skill_dir, ctx, [])
                b = compose(skill_dir, ctx, [])
                self.assertEqual(a, b)


class ProposalChannel(unittest.TestCase):
    """模型提议路由：结构校验（未注册即拒）、合法并入、无提议输出不变。"""

    def test_unknown_module_rejected(self):
        from scripts.novelos_compose_prompt import resolve_proposal
        with self.assertRaises(SystemExit):
            resolve_proposal(ASSET_DIRS["direction"], {"modules": [{"id": "no-such"}]})

    def test_legal_proposal_merges_and_dedupes(self):
        from scripts.novelos_compose_prompt import resolve_proposal
        ctx = _ctx_direction()  # 男频/免费/genre_null=False → genre-present 已规则命中
        modules = resolve_proposal(ASSET_DIRS["direction"], {"modules": [
            {"id": "channel-omni", "reason": "材料含双频道桥段"},
            {"id": "genre-present", "reason": "重复项应被去重"},
        ]})
        base = compose(ASSET_DIRS["direction"], ctx, [])
        out = compose(ASSET_DIRS["direction"], ctx, [], proposal_modules=modules)
        # channel-omni 未被规则命中 → 提议并入（全向模块标志出现）
        self.assertIn("频道语法：全向", out)
        self.assertNotIn("频道语法：全向", base)
        # genre-present 已命中 → 不重复出现（标题只出现一次）
        self.assertEqual(out.count("## 题材信息包消费"), 1)

    def test_no_proposal_output_unchanged(self):
        ctx = _ctx_direction()
        self.assertEqual(compose(ASSET_DIRS["direction"], ctx, [], proposal_modules=[]),
                         compose(ASSET_DIRS["direction"], ctx, []))


class KernelPsychologyRouting(unittest.TestCase):
    """P2-2：kernel-psychology 模块按 has_kernel 挂接（v2 旧项目不挂）。"""

    def test_module_attaches_with_kernel(self):
        ctx = _ctx_direction(channel="女频")
        ctx["has_kernel"] = True
        out = compose(ASSET_DIRS["chapter-draft"], ctx, [])
        self.assertIn("内核心理呈现纪律（kernel_psychology）", out)

    def test_module_absent_without_kernel(self):
        ctx = _ctx_direction(channel="女频")
        ctx["has_kernel"] = False
        out = compose(ASSET_DIRS["chapter-draft"], ctx, [])
        self.assertNotIn("内核心理呈现纪律（kernel_psychology）", out)

    def test_direction_consumes_kernel_layer(self):
        out = compose(ASSET_DIRS["direction"], _ctx_direction(), [])
        self.assertIn("上游消费：作者内核怎么用", out)
        self.assertIn("核心问题 → organizing_principle 的种子", out)


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


if __name__ == "__main__":
    unittest.main()
