from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novelos_mcp import NovelOSService
from novelos_mcp.errors import NovelOSError
from novelos_mcp.project_wizard import (
    SECONDARY_DIRECTION_SUGGESTIONS,
    WIZARD_OPTIONS,
    normalize_project_setup,
    project_wizard_html,
)


class ProjectWizardTest(unittest.TestCase):
    @staticmethod
    def _signature(label: str = "制度") -> dict[str, object]:
        return {
            "schema_version": 1,
            "sympathies": [f"维护{label}中的普通人尊严"],
            "distrusts": [f"警惕{label}中不承担代价的权力"],
            "recurring_attention": [f"观察{label}如何进入日常关系"],
            "narrative_principles": ["通过选择和后果表达判断"],
            "forbidden_conveniences": ["不得用一句道歉抹平长期伤害"],
            "expression_preferences": ["保持克制叙述并允许留白"],
            "negative_constraints": ["不模仿具体作者，不根据人口属性推导文风"],
        }

    def _setup(self, service: NovelOSService | None = None) -> dict:
        parent_id = "creator-profile-version:system-youthful-bonds:v1"
        parent_hash = "sha256:" + "0" * 64
        if service is not None:
            archetype = service.list_system_archetypes()[0]["latest_version"]
            parent_id = archetype["id"]
            parent_hash = archetype["subject_hash"]
        return {
            "title": "向导测试项目",
            "creator": {
                "mode": "derive",
                "parent_version_id": parent_id,
                "parent_subject_hash": parent_hash,
                "display_name": "向导测试作者",
                "overrides": {"recurring_attention": ["观察少年羁绊与日常矛盾"]},
            },
            "channel": "男频",
            "platform": "起点",
            "scale": "超长篇（500万字以上）",
            "primary_genre": "奇幻",
            "secondary_directions": ["西方玄幻", "领主战争"],
            "emotional_tones": ["史诗厚重", "黑暗压抑"],
            "aesthetic_styles": ["西幻史诗", "黑暗哥特"],
            "reference_material": "主角从边境小镇出发，避免无敌开局。",
        }

    def test_normalizes_structured_constraints_for_project_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            title, description, metadata, creator = normalize_project_setup(self._setup(service))
            self.assertEqual("向导测试项目", title)
            self.assertIn("男频", description)
            self.assertEqual("derive", creator["mode"])
            self.assertEqual(3, metadata["project_setup"]["version"])
            self.assertEqual("derive", metadata["project_setup"]["creator_selection"]["mode"])
            self.assertEqual("起点", metadata["project_setup"]["creation_context"]["platform"])
            self.assertEqual("主角从边境小镇出发，避免无敌开局。", metadata["project_setup"]["creation_context"]["reference_material"])
            self.assertEqual(["史诗厚重", "黑暗压抑"], metadata["project_setup"]["taxonomy"]["emotional_tones"])
            self.assertEqual(["西幻史诗", "黑暗哥特"], metadata["project_setup"]["taxonomy"]["aesthetic_styles"])

            created = service.create_project_with_creator(title, description, metadata, creator)
            stored = service.get_project(created["project"]["id"])
            self.assertEqual(metadata, stored["metadata"])
            self.assertEqual(
                created["creator_binding"]["subject_hash"],
                service.get_project_creator_binding(stored["id"])["subject_hash"],
            )

    def test_normalizes_and_creates_derive_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            archetype = service.list_system_archetypes()[0]["latest_version"]
            derive_setup = self._setup(service) | {
                "title": "派生作者项目",
                "creator": {
                    "mode": "derive",
                    "parent_version_id": archetype["id"],
                    "parent_subject_hash": archetype["subject_hash"],
                    "display_name": "城市冷峻分支",
                    "overrides": {"expression_preferences": ["短句、低议论、保留事实空白"]},
                },
            }
            name, description, metadata, creator = normalize_project_setup(derive_setup)
            derived = service.create_project_with_creator(name, description, metadata, creator)
            derived_version = derived["creator_binding"]["profile_version"]
            self.assertEqual("derive", derived["creator_binding"]["binding_mode"])
            self.assertEqual(archetype["id"], derived_version["parent_version_id"])
            self.assertEqual(creator["overrides"], derived_version["derivation"])

    @staticmethod
    def _archetype_entry(service: NovelOSService, config_id: str) -> dict[str, object]:
        archetype = next(a for a in service.system_archetypes if a["id"] == config_id)
        return {
            "profile_version_id": f"creator-profile-version:{config_id}:1",
            "subject_hash": archetype["subject_hash"],
            "display_name": archetype["display_name"],
        }

    def _project_setup_for_reconcile(self) -> dict[str, object]:
        return {
            "creation_context": {
                "primary_genre": "奇幻",
                "secondary_directions": ["领主战争", "神明战争"],
            },
            "taxonomy": {
                "emotional_tones": ["黑暗压抑", "疯癫混乱"],
                "aesthetic_styles": ["西幻史诗", "黑暗哥特"],
            },
        }

    def test_reconcile_picks_top_scored_parent_and_merges_secondary_promises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            selected = [
                self._archetype_entry(service, "system-epic-framework"),
                self._archetype_entry(service, "system-shadowed-choice"),
                self._archetype_entry(service, "system-restoration-craft"),
            ]
            result = service.reconcile_project_wizard_archetypes(
                selected,
                self._project_setup_for_reconcile(),
                "暗影权柄：神战纪元",
            )
            creator = result["creator"]
            self.assertEqual("derive", creator["mode"])
            # 黑暗压抑/疯癫混乱 让 shadowed-choice 得分最高
            self.assertEqual(
                "creator-profile-version:system-shadowed-choice:1",
                creator["parent_version_id"],
            )
            self.assertEqual("暗影权柄：神战纪元", creator["display_name"])
            # 辅风格融合：其余两个原型的 reader_promise 应进入 recurring_attention
            merged = " ".join(creator["overrides"]["recurring_attention"])
            self.assertIn("体系史诗", merged)
            self.assertIn("经营复兴", merged)
            self.assertEqual(
                ["体系史诗", "经营复兴"],
                result["merged_secondary_archetypes"],
            )

    def test_reconcile_rejects_unknown_archetype_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            selected = [
                {
                    "profile_version_id": "creator-profile-version:system-no-such:1",
                    "subject_hash": "sha256:" + "0" * 64,
                    "display_name": "不存在",
                }
            ]
            with self.assertRaisesRegex(NovelOSError, "找不到选中的系统叙事原型"):
                service.reconcile_project_wizard_archetypes(
                    selected,
                    self._project_setup_for_reconcile(),
                    "测试作者",
                )

    def test_reconcile_rejects_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            entry = self._archetype_entry(service, "system-shadowed-choice")
            entry["subject_hash"] = "sha256:" + "a" * 64
            with self.assertRaisesRegex(NovelOSError, "subject_hash 与配置不一致"):
                service.reconcile_project_wizard_archetypes(
                    [entry],
                    self._project_setup_for_reconcile(),
                    "测试作者",
                )

    def test_reconcile_output_passes_wizard_submit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            selected = [
                self._archetype_entry(service, "system-shadowed-choice"),
                self._archetype_entry(service, "system-disaster-survivor"),
            ]
            result = service.reconcile_project_wizard_archetypes(
                selected,
                self._project_setup_for_reconcile(),
                "端到端作者",
            )
            # reconcile 输出的 creator 结构应能直接驱动 normalize + create
            setup = self._setup(service) | {"creator": result["creator"]}
            name, description, metadata, creator = normalize_project_setup(setup)
            created = service.create_project_with_creator(name, description, metadata, creator)
            binding = created["creator_binding"]
            profile_version = binding["profile_version"]
            self.assertEqual("derive", binding["binding_mode"])
            # binding 绑定的是新生成的派生版本，其 parent 才是 reconcile 选定的原型
            self.assertEqual(
                result["creator"]["parent_version_id"],
                profile_version["parent_version_id"],
            )
            self.assertEqual(
                result["creator"]["overrides"],
                profile_version["derivation"],
            )

    def _fused_signature_for(self, service: NovelOSService, config_id: str) -> dict[str, object]:
        """构造一份相对 parent 各字段都不同的深度融合签名（含 schema_version）。"""
        # archetype 本身不参与校验，仅用来确保 config_id 存在。
        next(a for a in service.system_archetypes if a["id"] == config_id)
        # 7 个签名字段全部写成与任何 parent base 不同的内容，schema_version 保持 1。
        return {
            "schema_version": 1,
            "sympathies": [f"同理融合后的 {config_id} 主角"],
            "distrusts": [f"警惕融合后 {config_id} 的反模式"],
            "recurring_attention": [
                f"持续关注 {config_id} 融合后的体系与代价",
                "持续关注其余原型的辅风格约束",
            ],
            "narrative_principles": [f"融合叙事原则：{config_id} 为骨架"],
            "forbidden_conveniences": ["禁止融合路径下任何无代价便利"],
            "expression_preferences": ["融合笔法：冷峻且富结构感"],
            "negative_constraints": ["不得放弃融合后骨架的严密性"],
        }

    def test_reconcile_uses_fused_parent_when_provided(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            selected = [
                self._archetype_entry(service, "system-shadowed-choice"),
                self._archetype_entry(service, "system-disaster-survivor"),
                self._archetype_entry(service, "system-epic-framework"),
            ]
            fused_archetype_id = "system-epic-framework"
            fused_parent_entry = next(
                e for e in selected
                if e["profile_version_id"].endswith(f"{fused_archetype_id}:1")
            )
            fused_signature = self._fused_signature_for(service, fused_archetype_id)
            result = service.reconcile_project_wizard_archetypes(
                selected,
                self._project_setup_for_reconcile(),
                "融合作者",
                fused_parent_version_id=fused_parent_entry["profile_version_id"],
                fused_signature=fused_signature,
            )
            creator = result["creator"]
            # parent 必须是 Agent 判定的 fused parent，而非打分最高者
            self.assertEqual(
                fused_parent_entry["profile_version_id"],
                creator["parent_version_id"],
            )
            self.assertEqual("fused", result["parent_source"])
            # overrides 应等于自动折算的 diff：全部 7 字段均与 parent 不同
            self.assertEqual(
                {k: fused_signature[k] for k in (
                    "sympathies", "distrusts", "recurring_attention",
                    "narrative_principles", "forbidden_conveniences",
                    "expression_preferences", "negative_constraints",
                )},
                creator["overrides"],
            )
            # schema_version 不应进入 overrides
            self.assertNotIn("schema_version", creator["overrides"])

    def test_reconcile_fused_rejects_partial_args(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            selected = [self._archetype_entry(service, "system-epic-framework")]
            fused_signature = self._fused_signature_for(service, "system-epic-framework")
            # 只给 fused_parent_version_id，缺 fused_signature
            with self.assertRaisesRegex(NovelOSError, "必须同时提供或同时缺省"):
                service.reconcile_project_wizard_archetypes(
                    selected,
                    self._project_setup_for_reconcile(),
                    "融合作者",
                    fused_parent_version_id=selected[0]["profile_version_id"],
                    fused_signature=None,
                )
            # 只给 fused_signature，缺 fused_parent_version_id
            with self.assertRaisesRegex(NovelOSError, "必须同时提供或同时缺省"):
                service.reconcile_project_wizard_archetypes(
                    selected,
                    self._project_setup_for_reconcile(),
                    "融合作者",
                    fused_parent_version_id=None,
                    fused_signature=fused_signature,
                )

    def test_reconcile_fused_output_passes_wizard_submit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            selected = [
                self._archetype_entry(service, "system-shadowed-choice"),
                self._archetype_entry(service, "system-epic-framework"),
            ]
            fused_archetype_id = "system-epic-framework"
            fused_parent_entry = next(
                e for e in selected
                if e["profile_version_id"].endswith(f"{fused_archetype_id}:1")
            )
            fused_signature = self._fused_signature_for(service, fused_archetype_id)
            result = service.reconcile_project_wizard_archetypes(
                selected,
                self._project_setup_for_reconcile(),
                "端到端融合作者",
                fused_parent_version_id=fused_parent_entry["profile_version_id"],
                fused_signature=fused_signature,
            )
            # fused 路径产出的 creator 必须能直接驱动 normalize + create
            setup = self._setup(service) | {"creator": result["creator"]}
            name, description, metadata, creator = normalize_project_setup(setup)
            created = service.create_project_with_creator(name, description, metadata, creator)
            binding = created["creator_binding"]
            profile_version = binding["profile_version"]
            self.assertEqual("derive", binding["binding_mode"])
            self.assertEqual(
                result["creator"]["parent_version_id"],
                profile_version["parent_version_id"],
            )
            self.assertEqual(
                result["creator"]["overrides"],
                profile_version["derivation"],
            )


    def test_rejects_removed_options_and_invalid_choices(self) -> None:
        with self.assertRaisesRegex(NovelOSError, "最多选择两项"):
            normalize_project_setup(self._setup() | {"aesthetic_styles": ["西幻史诗", "黑暗哥特", "蒸汽幻想"]})
        with self.assertRaisesRegex(NovelOSError, "未支持字段"):
            normalize_project_setup(self._setup() | {"custom_word_count": 680_000})
        with self.assertRaisesRegex(NovelOSError, "二级方向"):
            normalize_project_setup(self._setup() | {"secondary_directions": ["古典仙侠"]})
        with self.assertRaisesRegex(NovelOSError, "主情绪基调"):
            normalize_project_setup(self._setup() | {"emotional_tones": ["不存在的情绪"]})

    def test_local_preview_contains_all_choices_without_javascript(self) -> None:
        html = project_wizard_html()

        for key in ("channels", "platforms", "scales", "primary_genres", "emotional_tones", "aesthetic_styles"):
            for value in WIZARD_OPTIONS[key]:
                self.assertIn(f">{value}</label>", html)
        for genre, suggestions in SECONDARY_DIRECTION_SUGGESTIONS.items():
            self.assertIn(f'"{genre}"', html)
            for value in suggestions:
                self.assertIn(f'"{value}"', html)
        self.assertNotIn("知乎盐选", html)
        self.assertNotIn("自定义字数", html)
        self.assertNotIn('value="自定义"', html)
        self.assertIn("reference_material", html)
        self.assertIn("emotional_tones", html)
        self.assertNotIn('name="creator_mode"', html)
        self.assertNotIn('id="creator_reuse"', html)
        self.assertNotIn('id="creator_create"', html)
        self.assertIn('id="archetype_recommendations"', html)
        self.assertIn("recommendationScore", html)
        self.assertIn("继承自原型（只读）", html)
        self.assertIn("提供给 Main Agent 的作者偏好原始输入", html)
        self.assertIn('id="creator_parent_options"', html)
        self.assertIn('name="creator_parents"', html)
        self.assertIn("selected_archetypes", html)
        self.assertIn("user_signature_inputs", html)
        self.assertIn("main_agent_processing", html)
        self.assertNotIn('id="generate_derived_signature"', html)
        self.assertNotIn('id="reset_derived_signature"', html)
        self.assertNotIn("已清空本书差异", html)
        self.assertNotIn("生成基础差异草稿", html)
        self.assertNotIn("fillGeneratedDerivation", html)
        self.assertIn('mode: "derive"', html)
        self.assertNotIn("fillGeneratedSignature", html)
        for field in ("recurring_attention", "narrative_principles", "forbidden_conveniences", "expression_preferences"):
            self.assertIn(field, html)
        self.assertIn('appInfo: { name: "novelos-project-wizard", version: "3.0.0" }', html)
        self.assertNotIn("clientInfo:", html)
        self.assertNotIn('name: "project.wizard.render"', html)
        self.assertIn("loadCreatorProfiles();", html)
        self.assertIn("bridgePromise = undefined;", html)
        self.assertIn("window.NOVELOS_WIZARD_DATA || {}", html)
        self.assertIn('get("mode") === "offline"', html)
        self.assertIn('request_type: "novelos.project.create.v1"', html)
        self.assertIn("generateStandaloneJson", html)
        self.assertIn('submit.textContent = "生成项目提交 JSON";', html)
        self.assertNotIn('name: "project.wizard.submit"', html)
        self.assertIn("JSON.stringify(request, null, 2)", html)
        self.assertIn("navigator.clipboard.writeText", html)
        self.assertIn('document.execCommand("copy")', html)
        self.assertIn('id="json_output"', html)
        self.assertIn('id="copy_json"', html)
        self.assertIn('script src="./project-wizard-data.js"', html)


if __name__ == "__main__":
    unittest.main()
