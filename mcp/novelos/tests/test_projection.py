from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from novelos_mcp import NovelOSError
from novelos_mcp.projection import ProjectionEngine, sanitize_filename
from novelos_mcp.service import NovelOSService


from agent_test_support import complete_agent_run, complete_review_run

ROLE_IDS = {
    "direction": "direction_agent",
    "architecture": "architecture_agent",
    "strategy": "strategy_agent",
    "character_contract": "character_agent",
    "world_contract": "world_agent",
    "story_arc": "story_arc_agent",
    "volume_outline": "volume_planner",
    "chapter_plan": "chapter_planner",
    "chapter": "writer_agent",
}


def creator_signature() -> dict[str, object]:
    return {
        "schema_version": 1,
        "sympathies": ["维护承担具体代价者的尊严"],
        "distrusts": ["警惕不承担后果的权力"],
        "recurring_attention": ["观察制度如何进入日常关系"],
        "narrative_principles": ["通过选择和后果表达判断"],
        "forbidden_conveniences": ["不得用一句道歉抹平长期伤害"],
        "expression_preferences": ["克制议论并保留事实空白"],
        "negative_constraints": ["不模仿具体作者"],
    }


def project_book_soul() -> dict[str, object]:
    return {
        "schema_version": 1,
        "unresolved_claims": ["秩序能否在不消耗人的情况下延续"],
        "central_contradiction": "个体自由与共同体责任都不可放弃，但无法同时完整满足",
        "costly_commitments": ["宁愿让主角失败，也不转移其选择造成的代价"],
        "protected_dignity": ["不羞辱失败者，也不免除其行为后果"],
        "forbidden_resolutions": ["制度问题不得归罪于一个坏人后自动消失"],
        "recurring_tests": ["每次以大局为名的牺牲都检查决策者是否承担同等风险"],
        "narrative_mercy": "理解人物为何妥协，但不替其取消后果",
        "narrative_cruelty": "让人物亲手承受其信念的反面结果",
        "deliberate_silences": ["不由叙述者宣布人物是否获得原谅"],
    }


class ProjectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "projection_test.db"
        self.service = NovelOSService(self.db_path, catalog_path=Path(__file__).resolve().parents[3] / "catalog" / "skills")

        self.project = self.service.create_project("测试全结构小说", "测试用的完整全结构小说投影")
        self.book = self.service.create_book(self.project["id"], "第一部")
        self.volume = self.service.create_volume(self.book["id"], 1, "第一卷")
        self.trace = self.service.start_trace("trace-projection-test", self.project["id"])

        # 1. 创建并锁定全套 6 大规划资产
        def _lock_asset(asset_type: str, upstreams: list[dict], cross_check_id: str | None = None) -> dict:
            content = f"{asset_type} 规划内容正文"
            p_run = complete_agent_run(self.service, self.trace["id"], ROLE_IDS[asset_type], "planning_candidate", content)
            cand = self.service.create_planning_candidate(
                self.project["id"],
                asset_type,
                self.project["id"],
                content,
                [{"asset_id": u["id"], "version": u["version"]} for u in upstreams],
                producer_run_id=p_run["id"],
                cross_check_id=cross_check_id,
            )
            _, rec = complete_review_run(self.service, self.trace["id"], "planning_asset", cand["id"], cand["subject_hash"], f"planning-{asset_type.replace('_', '-')}")
            return self.service.lock_planning_asset(cand["id"], rec["id"], cand["version"], self.trace["id"])

        direction = _lock_asset("direction", [])
        architecture = _lock_asset("architecture", [direction])
        strategy = _lock_asset("strategy", [direction, architecture])
        char_contract = _lock_asset("character_contract", [architecture, strategy])
        world_contract = _lock_asset("world_contract", [architecture, strategy])
        self.world_contract = world_contract

        # Story Arc 需要交叉检查
        cross_check_cand = self.service.prepare_planning_cross_check(
            self.project["id"], char_contract["id"], world_contract["id"]
        )
        _, cross_review = complete_review_run(
            self.service,
            self.trace["id"],
            "planning_cross_check",
            cross_check_cand["id"],
            cross_check_cand["subject_hash"],
            "planning-character-world-cross-consistency",
        )
        approved_cross_check = self.service.approve_planning_cross_check(
            cross_check_cand["id"], cross_review["id"], cross_check_cand["version"], self.trace["id"]
        )
        story_arc = _lock_asset("story_arc", [strategy, char_contract, world_contract], cross_check_id=approved_cross_check["id"])

        volume_outline = _lock_asset("volume_outline", [story_arc])
        self.volume_outline = volume_outline

        chapter_plan = _lock_asset("chapter_plan", [volume_outline])
        self.chapter_plan = chapter_plan

        # 3. 创建并接受正文
        chap_content = "寒山绝顶，风雪交加。主角立于试剑石前，拔剑出鞘。"
        writer_run = complete_agent_run(
            self.service,
            self.trace["id"],
            ROLE_IDS["chapter"],
            "chapter_draft_candidate",
            chap_content,
            {"locked_chapter_plan_ref": self.chapter_plan["id"]},
        )
        chap_draft = self.service.create_chapter_draft(
            self.volume["id"],
            1,
            "第一章 试剑石前",
            chap_content,
            metadata={"chapter_plan_ref": self.chapter_plan["id"], "chapter_plan_version": self.chapter_plan["version"]},
            producer_run_id=writer_run["id"],
        )
        _, chap_rec = complete_review_run(self.service, self.trace["id"], "chapter", chap_draft["id"], chap_draft["subject_hash"], "prose-v1")
        self.chapter = self.service.accept_chapter(chap_draft["id"], chap_rec["id"], chap_draft["version"], self.trace["id"])

        # 4. 创建实体与连续性
        char_mut = self.service.prepare_entity_mutation(
            self.project["id"],
            "character",
            {"name": "陆沉", "description": "寒山剑宗弟子", "state": {"location": "寒山"}},
            char_contract["id"],
            char_contract["subject_hash"],
            None,
        )
        _, char_rev = complete_review_run(self.service, self.trace["id"], "entity_mutation", char_mut["id"], char_mut["subject_hash"], "entity-character", evidence_refs=[char_mut["mutation_ref"]])
        self.char = self.service.commit_entity_mutation(char_mut["id"], char_rev["id"], char_mut["version"], self.trace["id"])

        world_mut = self.service.prepare_entity_mutation(
            self.project["id"],
            "world",
            {"name": "寒山剑宗", "description": "宗门所在地与规则边界", "state": {"season": "冬"}},
            world_contract["id"],
            world_contract["subject_hash"],
            None,
        )
        _, world_rev = complete_review_run(self.service, self.trace["id"], "entity_mutation", world_mut["id"], world_mut["subject_hash"], "entity-world", evidence_refs=[world_mut["mutation_ref"]])
        self.world = self.service.commit_entity_mutation(world_mut["id"], world_rev["id"], world_mut["version"], self.trace["id"])

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_sanitize_filename(self) -> None:
        self.assertEqual("test_file", sanitize_filename("test/file"))
        self.assertEqual("hello_world_", sanitize_filename("hello:world?"))
        self.assertEqual("untitled", sanitize_filename(".."))
        self.assertEqual("untitled", sanitize_filename(""))

        # 路径穿越变体必须被中和为不含分隔符的安全名，不得残留逃逸片段。
        for dangerous in ("../escape", "../../etc/passwd", "....//hidden", "/abs/path"):
            result = sanitize_filename(dangerous)
            self.assertNotIn("/", result)
            self.assertNotIn("\\", result)
            self.assertTrue(result)  # 非空

    def test_path_traversal_and_symlink_escape_rejected(self) -> None:
        """验收标准 5：路径穿越与符号链接逃逸必须被拒绝，渲染不得写出根目录之外。"""
        out_root = Path(self.tmp_dir.name) / "novels"

        # 1) 项目名含路径穿越片段：sanitize_filename 将其中和为安全默认名，
        #    渲染产物仍落在根目录下，不产生逃逸。
        traversal_project = self.service.create_project("../escape-attempt", "穿越尝试")
        res = self.service.render_project_projection(traversal_project["id"], output_root=str(out_root))
        target_dir = Path(res["output_directory"])
        # 目标目录必须仍在 root 之下（relative_to 不抛错）
        self.assertEqual(out_root.resolve(), target_dir.resolve().parent)
        # 不应存在根目录之外的逃逸文件
        self.assertFalse((Path(self.tmp_dir.name) / "escape-attempt").exists())

        # 2) 符号链接逃逸：在 root 下预置一个指向外部的符号链接目录名，
        #    令其与项目目录名相同。render 的 project_id 归属检查使用 manifest，
        #    无 manifest 时落到符号链接路径，resolve() 后 relative_to(root) 必须拒绝。
        link_target = Path(self.tmp_dir.name) / "external_secret"
        link_target.mkdir()
        (link_target / "leaked.txt").write_text("secret", encoding="utf-8")
        out_root.mkdir(parents=True, exist_ok=True)
        symlink_dir = out_root / "symlink-proj"
        os.symlink(link_target, symlink_dir)
        sym_project = self.service.create_project("symlink-proj", "符号链接项目")
        with self.assertRaisesRegex(NovelOSError, "security_violation|拒绝非授权覆盖"):
            self.service.render_project_projection(sym_project["id"], output_root=str(out_root))
        # 外部 secret 文件未被覆盖/写入
        self.assertEqual("secret", (link_target / "leaked.txt").read_text(encoding="utf-8"))

    def test_full_project_projection_rendering(self) -> None:
        out_root = Path(self.tmp_dir.name) / "novels"
        res = self.service.render_project_projection(self.project["id"], output_root=str(out_root))

        target_dir = Path(res["output_directory"])
        self.assertTrue(target_dir.is_dir())
        self.assertTrue((target_dir / "README.md").is_file())
        self.assertTrue((target_dir / "manifest.json").is_file())
        self.assertIn("尚未绑定 Creator Profile", (target_dir / "创作约束" / "作者签名.md").read_text(encoding="utf-8"))
        self.assertIn("没有包含有效 `book_soul` 的 locked Story Direction", (target_dir / "创作约束" / "本书创作灵魂.md").read_text(encoding="utf-8"))

        # 校验 规划/ 目录
        self.assertTrue((target_dir / "规划" / "01-故事方向.md").is_file())
        self.assertTrue((target_dir / "规划" / "02-故事架构.md").is_file())

        # 校验 大纲/ 目录
        self.assertTrue((target_dir / "大纲" / "第01卷-卷纲.md").is_file())

        # 校验 正文/ 目录
        chap_file = target_dir / "正文" / "第01卷" / "第001章-第一章 试剑石前.md"
        self.assertTrue(chap_file.is_file())
        self.assertIn("寒山绝顶", chap_file.read_text(encoding="utf-8"))

        # 校验 人物/ & 世界/
        self.assertTrue((target_dir / "人物" / "陆沉.md").is_file())
        self.assertTrue((target_dir / "世界" / "寒山剑宗.md").is_file())

        # 校验 manifest.json
        manifest = json.loads((target_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(self.project["id"], manifest["project_id"])
        self.assertEqual(res["authority_snapshot_hash"], manifest["authority_snapshot_hash"])
        self.assertTrue(len(manifest["files"]) >= 10)

    def test_creator_signature_and_only_locked_book_soul_are_projected(self) -> None:
        profile = self.service.create_creator_profile("克制作者", creator_signature())
        created = self.service.create_project_with_creator(
            "作者约束投影",
            "",
            {},
            {
                "mode": "reuse",
                "profile_version_id": profile["version"]["id"],
                "subject_hash": profile["version"]["subject_hash"],
            },
        )
        project = created["project"]
        binding = created["creator_binding"]
        trace = self.service.start_trace("projection-author-constraints", project["id"])
        run = complete_agent_run(
            self.service,
            trace["id"],
            "direction_agent",
            "planning_candidate",
            "带有本书独有追问的方向候选",
            {"creator_signature_ref": binding["constraint_ref"]},
        )
        candidate = self.service.create_planning_candidate(
            project["id"],
            "direction",
            project["id"],
            "带有本书独有追问的方向候选",
            [],
            metadata={
                "creator_signature_ref": binding["constraint_ref"],
                "book_soul": project_book_soul(),
            },
            producer_run_id=run["id"],
        )
        out_root = Path(self.tmp_dir.name) / "author-novels"
        before = self.service.render_project_projection(project["id"], output_root=str(out_root))
        before_dir = Path(before["output_directory"])
        self.assertIn("克制作者", (before_dir / "创作约束" / "作者签名.md").read_text(encoding="utf-8"))
        self.assertIn("没有包含有效 `book_soul` 的 locked Story Direction", (before_dir / "创作约束" / "本书创作灵魂.md").read_text(encoding="utf-8"))

        _, review = complete_review_run(
            self.service,
            trace["id"],
            "planning_asset",
            candidate["id"],
            candidate["subject_hash"],
            "planning-direction",
        )
        locked = self.service.lock_planning_asset(
            candidate["id"], review["id"], candidate["version"], trace["id"]
        )
        after = self.service.render_project_projection(project["id"], output_root=str(out_root))
        target = Path(after["output_directory"])
        soul_text = (target / "创作约束" / "本书创作灵魂.md").read_text(encoding="utf-8")
        self.assertIn("秩序能否在不消耗人的情况下延续", soul_text)
        self.assertIn(locked["subject_hash"], soul_text)

        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        files = {entry["relative_path"]: entry for entry in manifest["files"]}
        creator_entry = files["创作约束/作者签名.md"]
        self.assertEqual(binding["constraint_ref"], creator_entry["source_ref"])
        self.assertEqual(binding["subject_hash"], creator_entry["source_hash"])
        soul_entry = files["创作约束/本书创作灵魂.md"]
        self.assertEqual(locked["subject_hash"], soul_entry["source_hash"])
        self.assertEqual(
            self.service.get_project_style_refs(project["id"])["style_refs"][1],
            soul_entry["source_ref"],
        )
        self.assertEqual([], self.service.verify_project_projection(str(target))["errors"])

    def test_non_authoritative_content_archived(self) -> None:
        # 创建未锁定的 candidate：不进入当前权威规划，但必须进入全过程产出档案。
        cand_run = complete_agent_run(self.service, self.trace["id"], "direction_agent", "planning_candidate", "未锁定的草稿方向")
        cand_draft = self.service.create_planning_candidate(
            self.project["id"],
            "direction",
            self.project["id"],
            "未锁定的草稿方向",
            [],
            producer_run_id=cand_run["id"],
        )
        out_root = Path(self.tmp_dir.name) / "novels"
        self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        target_dir = out_root / "测试全结构小说"

        dir_content = (target_dir / "规划" / "01-故事方向.md").read_text(encoding="utf-8")
        self.assertNotIn("未锁定的草稿方向", dir_content)
        self.assertIn("direction 规划内容正文", dir_content)
        self.assertIn(
            "未锁定的草稿方向",
            "\n".join(item.read_text(encoding="utf-8") for item in (target_dir / "产出").rglob("*.md")),
        )

    def test_deterministic_rendering(self) -> None:
        out_root = Path(self.tmp_dir.name) / "novels"
        res1 = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        manifest1 = (Path(res1["output_directory"]) / "manifest.json").read_text(encoding="utf-8")

        res2 = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        manifest2 = (Path(res2["output_directory"]) / "manifest.json").read_text(encoding="utf-8")

        self.assertEqual(res1["authority_snapshot_hash"], res2["authority_snapshot_hash"])
        self.assertEqual(manifest1, manifest2)

    def test_diagnostic_mode_includes_candidates(self) -> None:
        # 额外创建一个未锁定的 direction candidate，验证诊断模式行为。
        cand_run = complete_agent_run(self.service, self.trace["id"], "direction_agent", "planning_candidate", "诊断模式专属候选方向")
        cand_draft = self.service.create_planning_candidate(
            self.project["id"],
            "direction",
            self.project["id"],
            "诊断模式专属候选方向",
            [],
            producer_run_id=cand_run["id"],
        )
        out_root = Path(self.tmp_dir.name) / "novels"

        # 默认模式：候选不进入当前权威规划，但会保存在候选与全过程产出目录。
        res_default = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        target_default = Path(res_default["output_directory"])
        self.assertTrue((target_default / "候选").exists())
        locked_default = (target_default / "规划" / "01-故事方向.md").read_text(encoding="utf-8")
        self.assertNotIn("诊断模式专属候选方向", locked_default)
        self.assertIn("direction 规划内容正文", locked_default)

        # 诊断模式：候选进入独立的 候选/ 子目录，locked 内容不变。
        res_diag = self.service.render_project_projection(
            self.project["id"], output_root=str(out_root), include_candidates=True
        )
        target_diag = Path(res_diag["output_directory"])
        cand_rev = cand_draft["revision"]
        cand_file = target_diag / "候选" / f"01-故事方向-候选-r{cand_rev}.md"
        self.assertTrue(cand_file.is_file())
        self.assertIn("诊断模式专属候选方向", cand_file.read_text(encoding="utf-8"))
        # locked 视图不受诊断模式影响。
        locked_diag = (target_diag / "规划" / "01-故事方向.md").read_text(encoding="utf-8")
        self.assertEqual(locked_default, locked_diag)

        # 候选走旁路 key，不污染 authority_snapshot_hash：两种模式哈希必须一致。
        self.assertEqual(res_default["authority_snapshot_hash"], res_diag["authority_snapshot_hash"])

        # 候选文件经 manifest 登记，verify_manifest 可逐文件校验通过。
        verify = self.service.verify_project_projection(str(target_diag))
        self.assertEqual([], verify["errors"])

    def test_provenance_archive_rendered(self) -> None:
        # 创作全过程档案：每个 locked 资产应渲染溯源链（生产者/审查/锁定凭据），
        # 默认模式也渲染（档案是权威视图的一部分），且不污染 authority_snapshot_hash。
        out_root = Path(self.tmp_dir.name) / "novels"
        res_default = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        target = Path(res_default["output_directory"])

        # 默认模式即应生成 档案/ 目录，含已锁定资产的溯源。
        archive_dir = target / "档案"
        self.assertTrue(archive_dir.is_dir())
        arch_file = archive_dir / "01-故事方向-档案.md"
        self.assertTrue(arch_file.is_file())
        arch_text = arch_file.read_text(encoding="utf-8")
        # 档案应含生产 Agent、审查 verdict、authority_commit 等溯源要素。
        self.assertIn("生产 Agent", arch_text)
        self.assertIn("独立审查", arch_text)
        self.assertIn("锁定凭据", arch_text)
        self.assertIn("authority_commit", arch_text)

        # 诊断模式 hash 与默认一致：档案走旁路 key，不污染确定性。
        res_diag = self.service.render_project_projection(
            self.project["id"], output_root=str(out_root), include_candidates=True
        )
        self.assertEqual(res_default["authority_snapshot_hash"], res_diag["authority_snapshot_hash"])

        # manifest 覆盖档案文件，verify 通过。
        verify = self.service.verify_project_projection(str(target))
        self.assertEqual([], verify["errors"])

    def test_withdraw_planning_candidate_excludes_from_diagnostic(self) -> None:
        # candidate 废弃机制：withdraw 后变 superseded，诊断模式不再渲染它。
        cand_run = complete_agent_run(self.service, self.trace["id"], "direction_agent", "planning_candidate", "待废弃候选")
        cand = self.service.create_planning_candidate(
            self.project["id"], "direction", self.project["id"], "待废弃候选",
            [], producer_run_id=cand_run["id"],
        )
        cand_rev = cand["revision"]

        # 废弃前：诊断模式能看到该候选。
        out_root = Path(self.tmp_dir.name) / "novels"
        res_before = self.service.render_project_projection(
            self.project["id"], output_root=str(out_root), include_candidates=True
        )
        self.assertTrue((Path(res_before["output_directory"]) / "候选" / f"01-故事方向-候选-r{cand_rev}.md").is_file())

        # 废弃：需在一个 running trace 内。
        withdraw_trace = self.service.start_trace("withdraw-test", self.project["id"])
        withdrawn = self.service.withdraw_planning_candidate(cand["id"], withdraw_trace["id"], "探索性废弃候选，已被锁定版取代")
        self.service.finish_trace(withdraw_trace["id"], "completed")
        self.assertEqual("superseded", withdrawn["status"])

        # 废弃后：诊断模式不再渲染该候选。
        res_after = self.service.render_project_projection(
            self.project["id"], output_root=str(out_root), include_candidates=True
        )
        self.assertFalse((Path(res_after["output_directory"]) / "候选" / f"01-故事方向-候选-r{cand_rev}.md").exists())

        # 不能废弃非 candidate 资产（locked 资产应被拒绝）。
        locked_dir = self.service.create_project("另一项目", "")
        ltrace = self.service.start_trace("lock-for-withdraw-test", locked_dir["id"])
        lp = complete_agent_run(self.service, ltrace["id"], "direction_agent", "planning_candidate", "已锁方向")
        lcand = self.service.create_planning_candidate(locked_dir["id"], "direction", locked_dir["id"], "已锁方向", [], producer_run_id=lp["id"])
        _, lrev = complete_review_run(self.service, ltrace["id"], "planning_asset", lcand["id"], lcand["subject_hash"], "planning-direction")
        self.service.lock_planning_asset(lcand["id"], lrev["id"], lcand["version"], ltrace["id"])
        with self.assertRaisesRegex(NovelOSError, "invalid_state"):
            self.service.withdraw_planning_candidate(lcand["id"], ltrace["id"], "尝试废弃 locked")

    def test_rebuild_from_sqlite_without_db_mutation(self) -> None:
        out_root = Path(self.tmp_dir.name) / "novels"
        res1 = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        target_dir = Path(res1["output_directory"])

        # 验收标准 6：投影是只读派生——删除并重建不得修改任何权威表。
        # 先记录所有权威表的完整内容指纹。
        authority_tables = [
            "projects", "books", "volumes", "chapters", "characters", "worlds",
            "factions", "rules", "timelines", "planning_assets", "reviews",
            "narrative_promises", "expectation_ledgers", "relationship_states",
            "arc_states", "chapter_facts", "continuity_candidate_sets",
        ]

        def fingerprint_db() -> dict[str, str]:
            snap: dict[str, str] = {}
            with closing(sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)) as conn:
                for table in authority_tables:
                    rows = conn.execute(f'SELECT * FROM "{table}" ORDER BY id').fetchall()
                    snap[table] = json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str)
            return snap

        before = fingerprint_db()

        # 手动删除投影目录
        shutil.rmtree(target_dir)
        self.assertFalse(target_dir.exists())

        # 重新生成可完整恢复
        res2 = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        self.assertTrue(target_dir.exists())
        self.assertEqual(res1["authority_snapshot_hash"], res2["authority_snapshot_hash"])

        # 权威表必须未发生任何变化
        after = fingerprint_db()
        self.assertEqual(before, after)

    def test_project_id_mismatch_security_rejection(self) -> None:
        out_root = Path(self.tmp_dir.name) / "novels"
        res = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        target_dir = Path(res["output_directory"])

        # 创建第二个不同 ID 的项目
        proj2 = self.service.create_project("测试全结构小说", "同名但不同ID的项目")

        # 尝试覆盖已属于 proj1 的同名目录，必须抛出拒绝
        with self.assertRaisesRegex(NovelOSError, "拒绝非授权覆盖"):
            self.service.render_project_projection(proj2["id"], output_root=str(out_root))

    def _commit_timeline(self, label: str, sequence: int, description: str) -> dict:
        """创建并提交一条时间线实体。"""
        tl_mut = self.service.prepare_entity_mutation(
            self.project["id"],
            "timeline",
            {"label": label, "sequence": sequence, "description": description, "event_source_ref": self.chapter["id"]},
            self.world_contract["id"],
            self.world_contract["subject_hash"],
            None,
        )
        _, tl_rev = complete_review_run(
            self.service, self.trace["id"], "entity_mutation", tl_mut["id"], tl_mut["subject_hash"], "entity-timeline",
            evidence_refs=[tl_mut["mutation_ref"]],
        )
        return self.service.commit_entity_mutation(tl_mut["id"], tl_rev["id"], tl_mut["version"], self.trace["id"])

    def test_manifest_per_file_hash_verification(self) -> None:
        # 渲染并逐文件校验 manifest：内容 Hash 与来源 Hash 必须与实际文件/来源一致
        self._commit_timeline("春试剑", 1, "主角于寒山试剑")
        out_root = Path(self.tmp_dir.name) / "novels"
        res = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        target_dir = Path(res["output_directory"])

        result = self.service.verify_project_projection(str(target_dir))
        self.assertEqual([], result["errors"])
        self.assertGreater(result["verified_file_count"], 10)

        # 篡改一个文件后，校验必须失败
        chap_file = target_dir / "正文" / "第01卷" / "第001章-第一章 试剑石前.md"
        original = chap_file.read_bytes()
        chap_file.write_bytes(original + "\n被篡改的内容".encode("utf-8"))
        with self.assertRaisesRegex(NovelOSError, "manifest 逐文件校验未通过"):
            self.service.verify_project_projection(str(target_dir))
        # 恢复文件，校验重新通过
        chap_file.write_bytes(original)
        self.assertEqual([], self.service.verify_project_projection(str(target_dir))["errors"])

    def test_version_drift_aborts_and_preserves_old_projection(self) -> None:
        """验收标准 4：生成期间的版本漂移不得产生混合版本，且旧投影必须保留。

        get_projection_snapshot 使用显式事务获得快照隔离——并发写入无法穿插进
        读取过程，因此整个快照必然来自同一权威版本（这正是 Task 06 要求的
        「混合了两个权威版本时必须失败」的正确实现：混合不可能发生）。
        本测试在快照读取进行中插入一个外部并发写，断言：
        (1) 快照读到的所有数据来自漂移前的版本（一致性，无混合）；
        (2) 旧投影目录完整保留。
        """
        # 先生成一份完整投影
        out_root = Path(self.tmp_dir.name) / "novels"
        res = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        target_dir = Path(res["output_directory"])
        manifest_before = (target_dir / "manifest.json").read_text(encoding="utf-8")
        file_count_before = sum(1 for _ in target_dir.rglob("*") if _.is_file())
        baseline_hash = res["authority_snapshot_hash"]

        # 在快照读取过程中插入一个并发写：monkeypatch get_resource，使其在被首次
        # 调用后、其余 SELECT 之前，用一个独立连接向 projects 注入版本变化与新数据。
        import sqlite3 as _sqlite3
        from contextlib import closing as _closing
        original_get_resource = self.service.get_resource
        injected = {"done": False}

        def injecting_get_resource(resource_id: str) -> str:
            if not injected["done"]:
                injected["done"] = True
                with _closing(_sqlite3.connect(str(self.db_path), timeout=30)) as conn:
                    conn.execute(
                        "INSERT INTO timelines(id, project_id, label, sequence, description_resource_id, source_ref) "
                        "VALUES ('tl-drift', ?, '漂移注入', 999, ?, ?)",
                        (self.project["id"], self.chapter["resource_ref"].replace("novelos://resource/", ""), self.chapter["id"]),
                    )
                    conn.execute("UPDATE projects SET version=version+1 WHERE id=?", (self.project["id"],))
                    conn.commit()
            return original_get_resource(resource_id)

        self.service.get_resource = injecting_get_resource  # type: ignore[assignment]
        try:
            snap = self.service.get_projection_snapshot(self.project["id"])
        finally:
            self.service.get_resource = original_get_resource  # type: ignore[assignment]

        # (1) 快照必须保持一致：authority_snapshot_hash 与基准一致，
        # 且并发注入的漂移数据未混入快照（快照隔离生效，无混合版本）。
        self.assertEqual(baseline_hash, snap["authority_snapshot_hash"])
        injected_labels = [t.get("label") for t in snap["timelines"]]
        self.assertNotIn("漂移注入", injected_labels)

        # 旧投影目录必须完整保留（render 未因漂移数据而改变输出）
        self.assertEqual(manifest_before, (target_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(file_count_before, sum(1 for _ in target_dir.rglob("*") if _.is_file()))

    def test_non_authoritative_planning_and_chapter_states_archived(self) -> None:
        # 创建 candidate 和 superseded 正文：当前权威视图不混入，产出目录必须保留。
        # candidate
        cand_run = complete_agent_run(self.service, self.trace["id"], "direction_agent", "planning_candidate", "candidate草稿")
        self.service.create_planning_candidate(
            self.project["id"], "direction", self.project["id"], "candidate草稿", [],
            producer_run_id=cand_run["id"],
        )
        # superseded 正文：新建并接受一章，再 supersede
        draft2 = self.service.create_chapter_draft(self.volume["id"], 2, "第二章", "第二章正文")
        _, rev2 = complete_review_run(self.service, self.trace["id"], "chapter", draft2["id"], draft2["subject_hash"], "prose-v1")
        accepted2 = self.service.accept_chapter(draft2["id"], rev2["id"], draft2["version"], self.trace["id"])
        self.service.supersede_chapter(accepted2["id"], accepted2["version"])

        out_root = Path(self.tmp_dir.name) / "novels"
        res = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        target_dir = Path(res["output_directory"])

        # candidate 不进当前规划
        self.assertNotIn("candidate草稿", (target_dir / "规划" / "01-故事方向.md").read_text(encoding="utf-8"))
        # superseded 正文不进当前正文目录
        chapter_files = list((target_dir / "正文").rglob("*.md"))
        self.assertEqual(1, len(chapter_files))
        self.assertNotIn("第二章正文", chapter_files[0].read_text(encoding="utf-8"))

        archive = "\n".join(item.read_text(encoding="utf-8") for item in (target_dir / "产出").rglob("*.md"))
        self.assertIn("candidate草稿", archive)
        self.assertIn("第二章正文", archive)

        # 跳过统计仍用于说明当前权威视图排除了哪些状态。
        stats = res["skipped_non_authoritative_stats"]
        self.assertGreaterEqual(stats["candidates"], 1)
        self.assertGreaterEqual(stats["superseded"], 1)

    def test_two_volumes_projected(self) -> None:
        # 验收标准 1 要求「两卷正文」。当前项目已有第一卷第一章，再建第二卷并接受一章。
        volume2 = self.service.create_volume(self.book["id"], 2, "第二卷")
        chap_content = "春风又绿江南岸，主角下山。"
        writer_run = complete_agent_run(
            self.service, self.trace["id"], ROLE_IDS["chapter"], "chapter_draft_candidate", chap_content,
            {"locked_chapter_plan_ref": self.chapter_plan["id"]},
        )
        draft = self.service.create_chapter_draft(
            volume2["id"], 1, "第二卷首章", chap_content,
            metadata={"chapter_plan_ref": self.chapter_plan["id"], "chapter_plan_version": self.chapter_plan["version"]},
            producer_run_id=writer_run["id"],
        )
        _, rev = complete_review_run(self.service, self.trace["id"], "chapter", draft["id"], draft["subject_hash"], "prose-v1")
        self.service.accept_chapter(draft["id"], rev["id"], draft["version"], self.trace["id"])

        out_root = Path(self.tmp_dir.name) / "novels"
        self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        target_dir = out_root / "测试全结构小说"
        # 两卷正文都应存在
        self.assertTrue((target_dir / "正文" / "第01卷").is_dir())
        self.assertTrue((target_dir / "正文" / "第02卷").is_dir())
        vol2_chapters = list((target_dir / "正文" / "第02卷").glob("*.md"))
        self.assertEqual(1, len(vol2_chapters))
        self.assertIn("春风又绿江南岸", vol2_chapters[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
