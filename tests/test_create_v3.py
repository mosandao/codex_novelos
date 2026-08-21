from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "novelos_create_project", REPO_ROOT / "scripts" / "novelos_create_project.py")
create_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(create_mod)

WIZARD = create_mod.load_wizard_data()


def _make_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE resources (id TEXT PRIMARY KEY, media_type TEXT, content BLOB, content_hash TEXT);
        CREATE TABLE creator_profiles (
            id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active', version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ownership TEXT NOT NULL DEFAULT 'user');
        CREATE TABLE creator_profile_versions (
            id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, revision INTEGER NOT NULL,
            content_resource_id TEXT NOT NULL, subject_hash TEXT NOT NULL,
            parent_version_id TEXT, derivation_resource_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
            version INTEGER NOT NULL DEFAULT 1, metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE project_creator_bindings (
            project_id TEXT PRIMARY KEY, profile_id TEXT NOT NULL,
            profile_version_id TEXT NOT NULL, profile_revision INTEGER NOT NULL,
            subject_hash TEXT NOT NULL, binding_mode TEXT NOT NULL,
            kernel_version_id TEXT, version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    """)
    return conn


def _v3_payload(mode: str = "create") -> dict:
    ak = {"mode": mode, "kernel_hints": {
        "taste_anchors": ["低温叙事"], "core_questions": ["秩序的代价"]}}
    if mode == "select":
        ak["kernel_version_id"] = None  # 测试内回填
        ak["subject_hash"] = None
    return {
        "request_type": "novelos.project.create.v3",
        "setup": {
            "title": "内核管线测试书",
            "author_kernel": ak,
            "channel": "男频",
            "platform": "起点",
            "platform_traits": WIZARD["platform_traits"]["起点"],
            "scale": "长篇（100-300万字）",
            "primary_genre": "都市",
            "secondary_directions": [],
            "emotional_surface": ["冷峻克制"],
            "emotional_core": "热血悲壮",
            "tonal_contrast": None,
            "aesthetic_styles": [WIZARD["aesthetic_styles"][0]],
            "genre_profile": WIZARD["genre_profiles"]["男频|都市"],
            "reference_material": None,
        },
    }


def _kernel_candidate(mode: str = "create", display_name: str = "测试内核") -> dict:
    kernel = _kernel_json(display_name)
    cand = {
        "request_type": "novelos.kernel.candidate.v1",
        "mode": mode,
        "display_name": display_name,
        "kernel": kernel,
        "rationale": "素材→内核反推说明",
    }
    if mode == "revise":
        cand["base_version"] = None  # 测试内回填
    return cand


def _kernel_json(display_name: str) -> dict:
    dim = {"tendency": "先看规则漏洞", "triggers": ["新环境"], "reactions": ["查证"],
           "blindspots": ["高估制度"], "revision": "接触执行层后修正"}
    return {
        "schema_version": 1,
        "identity": {
            "display_name": display_name,
            "core_questions": ["秩序崩坏时普通人靠什么站住"],
            "value_axioms": ["失败比成功更值得写"],
            "emotional_stance": {"sympathies": ["守规矩的普通人"], "wariness": ["无代价的奇迹"]},
            "aesthetic_commitments": ["低温克制的叙述"],
            "knowledge_discipline": "查证到能写清机制为止",
            "creative_axioms": ["代价先于收益"],
            "kernel_blindspots": {"overcommits": ["结构感"], "overlooks": ["身体性细节"]},
        },
        "psychology": {k: dict(dim) for k in (
            "attention_bias", "emotion_processing", "core_needs", "attachment_pattern",
            "defense_compensation", "uncertainty_tolerance", "moral_intuition", "belief_updating")},
        "knowledge_ecology": {"domains": [{
            "domain": "工程审计", "depth": "工作知识", "primary_use": "机制真实感",
            "verification": "对照公开案例", "common_errors": ["把流程当因果"]}]},
        "growth_log": [],
    }


def _persona_candidate(parent_id: str, parent_hash: str) -> dict:
    fields = {
        "sympathies": ["被账目压弯的普通人", "同情样本二"],
        "distrusts": ["白嫖的浪漫", "警惕样本二"],
        "recurring_attention": ["账本与利息的题材", "题材样本二"],
        "narrative_principles": ["先立规矩再拆规矩", "主原则样本二"],
        "forbidden_conveniences": ["无账目的爽点", "捷径样本二"],
        "expression_preferences": ["冷账房笔触", "笔触样本二"],
        "negative_constraints": ["账目必平的底线", "底线样本二"],
    }
    return {
        "parent_version_id": parent_id,
        "parent_subject_hash": parent_hash,
        "display_name": "冷账房",
        "signature": {
            "schema_version": 2,
            "persona": {
                "narrative": (
                    "在审计岗泡了二十年的写作者，看什么都先找账。"
                    "国企技术岗出身，经手过基建项目的每一张单据，见过数字怎么在报表里被搬运，"
                    "也见过搬运的人怎么一步步说服自己那不算错。下班后在论坛写行业帖攒了第一批读者，"
                    "习惯把复杂的事情拆成能对账的条目再讲出来。不擅长当场表达感情，"
                    "情绪都压在措辞的轻重里。相信秩序，又亲眼看过秩序被谁定价，"
                    "所以写故事时总忍不住给每个便宜标好出处。读者说他冷，"
                    "他知道那不是冷，是不肯把账算糊涂。"),
                "anchors": {
                    "profile_sketch": "国企审计岗出身、转写行业帖攒读者的写作者",
                    "five_dimensions": {
                        "generation_age": "85 后", "education_horizon": "工科本科",
                        "class_circle_inventory": "基层技术官僚",
                        "career_track": "工程审计", "life_trajectory": "国企技术岗二十年",
                    },
                    "trait_profile": ["较真到惹人烦，复核过的数字容不得四舍五入",
                                      "口袋里总揣着计算器，听人讲故事先心算成本",
                                      "深夜重读自己白天写的段落，删掉所有感叹号"],
                    "theme_orientation": {"dominant": "agency", "evidence": "先掌控局面再谈别的，遇到失控先补计划"},
                    "inner_tension": "迷恋秩序又怀疑秩序",
                    "voice_samples": ["这笔账不平，故事就不平。"],
                    "blindspots": {
                        "refuses": ["因为怕失控所以不写天降奇迹——绕开：代价前置"],
                        "cannot_write": ["写不了 old money 酒局——绕开：外来者视角感受疏离"],
                    },
                },
            },
            **fields,
        },
        "parent_rationale": "内核在都市频道落地为账房视角分身",
    }


class KernelPipeline(unittest.TestCase):
    """v3 创建管线端到端：入口校验 → 建核 → 缝合 payload → 分身校验门 → 项目落库。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self.conn = _make_db(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_full_v3_create_flow(self):
        payload = _v3_payload("create")
        errors, warns = create_mod.validate_request(payload, WIZARD, self.conn)
        self.assertEqual(errors, [])

        # 内核候选校验 + 落库
        cand = _kernel_candidate("create")
        k_errors, kernel_hash = create_mod.validate_kernel_candidate(cand, self.conn)
        self.assertEqual(k_errors, [])
        kernel = create_mod.persist_kernel(self.db_path, cand, kernel_hash, payload)

        # 缝合 payload（select 形态）再过入口校验
        bound_path = Path(self.tmp.name) / "bound.json"
        create_mod._emit_bound_payload(payload, kernel, bound_path)
        bound = json.loads(bound_path.read_text(encoding="utf-8"))
        self.assertEqual(bound["setup"]["author_kernel"]["mode"], "select")
        errors, _ = create_mod.validate_request(bound, WIZARD, self.conn)
        self.assertEqual(errors, [])

        # 分身候选校验门 + 项目落库
        persona = _persona_candidate(kernel["kernel_version"], kernel["subject_hash"])
        g_errors, sig_hash = create_mod.validate_candidate(persona, bound, self.conn)
        self.assertEqual(g_errors, [])
        ids = create_mod.persist(self.db_path, bound, persona, sig_hash)

        binding = self.conn.execute(
            "SELECT binding_mode, kernel_version_id FROM project_creator_bindings "
            "WHERE project_id = ?", (ids["project"],)).fetchone()
        self.assertEqual(binding[0], "kernel_derive")
        self.assertEqual(binding[1], kernel["kernel_version"])
        version = self.conn.execute(
            "SELECT parent_version_id FROM creator_profile_versions WHERE id = ?",
            (ids["profile_version"],)).fetchone()
        self.assertEqual(version[0], kernel["kernel_version"])
        kernel_profile = self.conn.execute(
            "SELECT ownership FROM creator_profiles WHERE id = ?",
            (kernel["kernel_profile"],)).fetchone()
        self.assertEqual(kernel_profile[0], "author_kernel")

    def test_select_unknown_kernel_rejected(self):
        payload = _v3_payload("select")
        payload["setup"]["author_kernel"]["kernel_version_id"] = "creator-profile-version:ghost:1"
        payload["setup"]["author_kernel"]["subject_hash"] = "sha256:" + "a" * 64
        errors, _ = create_mod.validate_request(payload, WIZARD, self.conn)
        self.assertTrue(any("库中不存在" in e for e in errors))

    def test_select_non_kernel_profile_rejected(self):
        # 造一个 user 分身版本冒充内核
        self.conn.execute("INSERT INTO resources VALUES ('res:p', 'application/json', CAST('{}' AS BLOB), 'sha256:" + "b" * 64 + "')")
        self.conn.execute("INSERT INTO creator_profiles VALUES ('cp:user', '分身', 'active', 1, '2026-01-01', '2026-01-01', 'user')")
        self.conn.execute("INSERT INTO creator_profile_versions VALUES ('cpv:user', 'cp:user', 1, 'res:p', 'sha256:" + "b" * 64 + "', NULL, NULL, '2026-01-01')")
        payload = _v3_payload("select")
        payload["setup"]["author_kernel"]["kernel_version_id"] = "cpv:user"
        payload["setup"]["author_kernel"]["subject_hash"] = "sha256:" + "b" * 64
        errors, _ = create_mod.validate_request(payload, WIZARD, self.conn)
        self.assertTrue(any("author_kernel" in e for e in errors))

    def test_kernel_revise_requires_growth_and_name_continuity(self):
        cand = _kernel_candidate("create")
        k_errors, kernel_hash = create_mod.validate_kernel_candidate(cand, self.conn)
        kernel = create_mod.persist_kernel(self.db_path, cand, kernel_hash)

        revise = _kernel_candidate("revise", display_name="改名内核")
        revise["base_version"] = kernel["kernel_version"]
        errors, _ = create_mod.validate_kernel_candidate(revise, self.conn)
        self.assertTrue(any("display_name" in e for e in errors))

        revise = _kernel_candidate("revise")
        revise["base_version"] = kernel["kernel_version"]
        errors, _ = create_mod.validate_kernel_candidate(revise, self.conn)
        self.assertTrue(any("growth_log" in e for e in errors))

        revise["kernel"]["growth_log"] = [
            {"trigger": "读者反馈主线账目过密", "attribution": "slot", "change": "记录不改内核"},
            {"trigger": "第二本书反复避开身体细节", "attribution": "kernel",
             "change": "attention_bias 增加 revision 提示"}]
        errors, rh = create_mod.validate_kernel_candidate(revise, self.conn)
        self.assertEqual(errors, [])
        rev = create_mod.persist_kernel(self.db_path, revise, rh)
        self.assertEqual(rev["kernel_profile"], kernel["kernel_profile"])
        revision = self.conn.execute(
            "SELECT revision, parent_version_id FROM creator_profile_versions WHERE id = ?",
            (rev["kernel_version"],)).fetchone()
        self.assertEqual(revision[0], 2)
        self.assertEqual(revision[1], kernel["kernel_version"])

    def test_persona_verbatim_copy_of_kernel_rejected(self):
        cand = _kernel_candidate("create")
        _, kernel_hash = create_mod.validate_kernel_candidate(cand, self.conn)
        kernel = create_mod.persist_kernel(self.db_path, cand, kernel_hash)
        payload = _v3_payload("select")
        payload["setup"]["author_kernel"]["kernel_version_id"] = kernel["kernel_version"]
        payload["setup"]["author_kernel"]["subject_hash"] = kernel["subject_hash"]
        persona = _persona_candidate(kernel["kernel_version"], kernel["subject_hash"])
        persona["signature"]["narrative_principles"] = ["失败比成功更值得写", "主原则样本二"]
        errors, _ = create_mod.validate_candidate(persona, payload, self.conn)
        self.assertTrue(any("逐字复制父值" in e for e in errors))

    def test_kernel_candidate_shape_gate(self):
        # 完整 JSON 但形状错位由信封 schema 兜住（shape 门只管括号修复路径）
        errors, _ = create_mod.validate_kernel_candidate(
            {"request_type": "novelos.kernel.candidate.v1", "mode": "create"}, self.conn)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
