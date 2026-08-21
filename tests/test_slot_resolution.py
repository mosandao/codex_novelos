from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.novelos_compose_prompt import (
    ASSET_DIRS,
    SLOT_REGISTRY,
    build_context_fusion,
    resolve_slots,
    validate_fusion_payload,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHETYPES = json.loads(
    (REPO_ROOT / "config" / "system_archetypes.json").read_text(encoding="utf-8"))


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY, metadata_json TEXT);
        CREATE TABLE resources (id TEXT PRIMARY KEY, content BLOB);
        CREATE TABLE creator_profiles (id TEXT PRIMARY KEY, ownership TEXT, display_name TEXT);
        CREATE TABLE creator_profile_versions (
            id TEXT PRIMARY KEY, profile_id TEXT, parent_version_id TEXT,
            created_at TEXT, content_resource_id TEXT, subject_hash TEXT);
        CREATE TABLE project_creator_bindings (project_id TEXT, profile_version_id TEXT);
        CREATE TABLE planning_assets (
            id TEXT PRIMARY KEY, project_id TEXT, asset_type TEXT, scope_ref TEXT,
            revision INTEGER, status TEXT, content_resource_id TEXT, metadata_json TEXT);
        CREATE TABLE books (id TEXT PRIMARY KEY, project_id TEXT);
        CREATE TABLE volumes (id TEXT PRIMARY KEY, book_id TEXT, number INTEGER);
        CREATE TABLE chapters (
            id TEXT PRIMARY KEY, volume_id TEXT, number INTEGER, title TEXT,
            status TEXT, content_resource_id TEXT, summary TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '{}', version INTEGER DEFAULT 1,
            created_at TEXT, updated_at TEXT);
        CREATE TABLE chapter_facts (
            id TEXT PRIMARY KEY, project_id TEXT, source_chapter_id TEXT,
            fact_type TEXT, subject TEXT, description_resource_id TEXT, status TEXT);
        CREATE TABLE narrative_promises (
            id TEXT PRIMARY KEY, project_id TEXT, promise_key TEXT,
            description_resource_id TEXT, status TEXT);
        CREATE TABLE expectation_ledgers (
            id TEXT PRIMARY KEY, project_id TEXT, expectation_key TEXT,
            description_resource_id TEXT, status TEXT);
        CREATE TABLE relationship_states (
            id TEXT PRIMARY KEY, project_id TEXT, subject_ref TEXT,
            object_ref TEXT, state_resource_id TEXT);
        CREATE TABLE arc_states (
            id TEXT PRIMARY KEY, project_id TEXT, arc_ref TEXT, state_resource_id TEXT);
        """
    )
    return conn


def _seed_locked_direction(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO resources VALUES ('res:d1', CAST(? AS BLOB))",
                 ("# 故事方向（locked）\n力量货币：名望账。",))
    conn.execute(
        "INSERT INTO planning_assets VALUES "
        "('pa:d1', 'project:p1', 'direction', 'book', 1, 'locked', 'res:d1', '{}')")
    conn.execute(
        "INSERT INTO planning_assets VALUES "
        "('pa:a1', 'project:p1', 'architecture', 'book', 1, 'candidate', 'res:d1', '{\"engines\": []}')")


class UpstreamAndSubjectSlots(unittest.TestCase):
    """architecture 链路合成素材实测：upstream 槽注入 locked 原文，subject 槽注入被审对象。"""

    def test_architecture_upstream_slot(self):
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_locked_direction(conn)
        sections = resolve_slots(conn, ASSET_DIRS["architecture"], project_id="project:p1",
                                 context={"setup": {}})
        titles = [t for t, _ in sections]
        self.assertEqual(titles[0], "project_setup v2 快照（硬输入）")
        self.assertTrue(titles[2].startswith("上游 direction（scope: book，locked rev 1"))
        self.assertIn("力量货币：名望账", sections[2][1])

    def test_missing_upstream_stops(self):
        conn = _make_db()
        _seed_user_persona(conn)  # 无 locked direction
        with self.assertRaises(SystemExit):
            resolve_slots(conn, ASSET_DIRS["architecture"], project_id="project:p1")

    def test_review_subject_slot(self):
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_locked_direction(conn)
        sections = resolve_slots(conn, ASSET_DIRS["architecture-review"],
                                 project_id="project:p1", subject_id="pa:a1")
        self.assertTrue(sections[0][0].startswith("被审对象全文（subject: pa:a1）"))
        self.assertIn("engines", sections[0][1])  # metadata 注入
        self.assertTrue(sections[1][0].startswith("上游 direction"))

    def test_subject_slot_requires_arg(self):
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_locked_direction(conn)
        with self.assertRaises(SystemExit):
            resolve_slots(conn, ASSET_DIRS["architecture-review"], project_id="project:p1")


def _seed_user_persona(conn: sqlite3.Connection) -> None:
    signature = {
        "persona": {"anchors": {
            "five_dimensions": {"life_trajectory": "国企技术岗二十年", "career_track": "工程审计"},
            "trait_profile": ["较真到惹人烦"],
            "inner_tension": "迷恋秩序又怀疑秩序",
            "theme_orientation": {"dominant": "agency"},
        }},
        "narrative_principles": ["先立规矩再拆规矩"],
        "forbidden_conveniences": ["天降贵人"],
    }
    conn.execute("INSERT INTO resources VALUES ('res:1', CAST(? AS BLOB))",
                 (json.dumps(signature, ensure_ascii=False),))
    conn.execute("INSERT INTO creator_profiles VALUES ('cp:1', 'user', '测试人格')")
    conn.execute(
        "INSERT INTO creator_profile_versions VALUES "
        "('cpv:1', 'cp:1', 'creator-profile-version:system-test:1', '2026-01-01', 'res:1', ?)",
        ("sha256:" + "a" * 64,))
    conn.execute("INSERT INTO project_creator_bindings VALUES ('project:p1', 'cpv:1')")
    conn.execute(
        "INSERT INTO projects VALUES ('project:p1', ?)",
        (json.dumps({"setup": {"channel": "男频", "title": "测试书"}}, ensure_ascii=False),))


def _seed_kernel_for_fusion(conn: sqlite3.Connection) -> None:
    kernel = {"schema_version": 1,
              "identity": {"display_name": "测试内核", "core_questions": ["秩序的代价"]}}
    conn.execute("INSERT INTO resources VALUES ('res:k1', CAST(? AS BLOB))",
                 (json.dumps(kernel, ensure_ascii=False),))
    conn.execute("INSERT INTO creator_profiles VALUES ('cp:k1', 'author_kernel', '测试内核')")
    conn.execute(
        "INSERT INTO creator_profile_versions VALUES "
        "('creator-profile-version:k1:1', 'cp:k1', NULL, '2026-01-01', 'res:k1', ?)",
        ("sha256:" + "c" * 64,))


def _fusion_payload(mode: str = "create") -> dict:
    """v3 融合载荷：create 模式（kernel_full 占位）；select 模式需 seed 内核后用。"""
    ak = {"mode": mode, "kernel_hints": {"taste_anchors": ["低温叙事"]}}
    if mode == "select":
        ak["kernel_version_id"] = "creator-profile-version:k1:1"
        ak["subject_hash"] = "sha256:" + "c" * 64
        ak["kernel_hints"] = {}
    return {
        "request_type": "novelos.project.create.v3",
        "setup": {
            "title": "槽位测试书",
            "author_kernel": ak,
            "channel": "男频",
            "platform": "起点",
            "platform_traits": {"model": "免费算法", "patience": "快节奏", "reader_profile": "广谱"},
            "scale": "长篇（100-300万字）",
            "primary_genre": "都市",
            "secondary_directions": [],
            "emotional_surface": ["热血"],
            "emotional_core": "翻案",
            "tonal_contrast": None,
            "aesthetic_styles": ["冷峻"],
            "genre_profile": None,
            "reference_material": None,
        },
    }


class DirectionSlots(unittest.TestCase):

    def test_with_persona_binding(self):
        conn = _make_db()
        _seed_user_persona(conn)
        sections = resolve_slots(conn, ASSET_DIRS["direction"], project_id="project:p1",
                                 context={"setup": {"genre_profile": None}})
        self.assertEqual(
            [t for t, _ in sections],
            ["project_setup v2 快照（硬输入）", "创作者人格签名（第一因，persona 全文）",
             "题材信息包"],
        )
        self.assertTrue(sections[1][1].startswith("subject_hash: sha256:"))
        self.assertIn("迷恋秩序又怀疑秩序", sections[1][1])

    def test_without_binding_placeholder(self):
        conn = _make_db()
        conn.execute("INSERT INTO projects VALUES ('project:p2', '{}')")
        sections = resolve_slots(conn, ASSET_DIRS["direction"], project_id="project:p2",
                                 context={"setup": {}})
        self.assertEqual(sections[1][0], "创作者人格签名")
        self.assertIn("禁止无签名生成方向", sections[1][1])

    def test_review_slots_match_direction(self):
        conn = _make_db()
        _seed_user_persona(conn)
        d = resolve_slots(conn, ASSET_DIRS["direction"], project_id="project:p1",
                          context={"setup": {}})
        r = resolve_slots(conn, ASSET_DIRS["direction-review"], project_id="project:p1")
        self.assertEqual([t for t, _ in d][:2], [t for t, _ in r])

    def test_unregistered_slot_rejected(self):
        conn = _make_db()
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            (skill_dir / "modules").mkdir()
            (skill_dir / "modules" / "manifest.json").write_text(
                json.dumps({"modules": [], "data_slots": ["nonexistent_slot"]}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                resolve_slots(conn, skill_dir, project_id="project:x")


class FusionSlots(unittest.TestCase):

    def test_payload_schema_and_section_order(self):
        conn = _make_db()
        payload = _fusion_payload()
        validate_fusion_payload(payload)  # 不抛即通过
        sections = resolve_slots(conn, ASSET_DIRS["fusion"], payload=payload)
        self.assertEqual(
            [t for t, _ in sections],
            [
                "作者内核（kernel 全文）",  # create 模式未建核 → 占位节
                "系统原型全库一行式清单（仅作语境：库里还有什么；禁止从清单外原型取材）",
                "project_setup v2 快照",
                "跨批次比对基准人格",  # 空库 → 占位标题
            ],
        )
        self.assertIn("无内核来源", sections[0][1])
        self.assertIn("人格库为空", sections[3][1])

    def test_empty_library_placeholder(self):
        conn = _make_db()
        sections = resolve_slots(conn, ASSET_DIRS["fusion"], payload=_fusion_payload())
        self.assertEqual(sections[3][0], "跨批次比对基准人格")
        self.assertIn("人格库为空", sections[3][1])

    def test_invalid_payload_rejected(self):
        with self.assertRaises(SystemExit):
            validate_fusion_payload({"setup": {}})  # 缺 request_type
        payload = _fusion_payload()
        del payload["setup"]["author_kernel"]
        with self.assertRaises(SystemExit):
            validate_fusion_payload(payload)

    def test_v3_kernel_derive_sections_and_marker(self):
        """select 模式：kernel_full 注入内核全文，kernel-derive 模块命中。"""
        from scripts.novelos_compose_prompt import (
            build_context_fusion as _bcf, compose as _compose,
        )
        conn = _make_db()
        _seed_kernel_for_fusion(conn)
        payload = _fusion_payload("select")
        validate_fusion_payload(payload)
        context = _bcf(conn, payload)
        sections = resolve_slots(conn, ASSET_DIRS["fusion"], payload=payload)
        kernel_sec = next(b for t, b in sections if t.startswith("作者内核"))
        self.assertIn("测试内核", kernel_sec)
        self.assertIn("sha256:", kernel_sec)
        out = _compose(ASSET_DIRS["fusion"], context, sections)
        self.assertIn("内核派生分支（v3）", out)
        self.assertIn("kernel_origin", out)

    def test_kernel_derive_absent_without_kernel(self):
        from scripts.novelos_compose_prompt import compose as _compose
        conn = _make_db()
        context = {"setup": {"channel": "男频", "genre_profile": None}}
        out = _compose(ASSET_DIRS["fusion"], context, [])
        self.assertNotIn("内核派生分支（v3）", out)


class FullChainSmoke(unittest.TestCase):
    """P2 总验收：同一合成项目贯穿 direction → … → chapter-draft 的组装链路。"""

    def _seed_chain(self, conn: sqlite3.Connection) -> None:
        _seed_user_persona(conn)
        _seed_locked_direction(conn)
        for i, (aid, atype) in enumerate((
            ("pa:arch1", "architecture"), ("pa:str1", "strategy"),
            ("pa:vol1", "volume_outline"), ("pa:cp1", "chapter_plan"),
        )):
            conn.execute("INSERT INTO resources VALUES (?, CAST(? AS BLOB))",
                         (f"res:{aid}", f"# {atype}（locked）\n机制节选 {i}。"))
            conn.execute(
                "INSERT INTO planning_assets VALUES "
                f"('{aid}', 'project:p1', '{atype}', 'book', 1, 'locked', 'res:{aid}', '{{}}')")
        conn.execute("INSERT INTO resources VALUES ('res:ch1', CAST(? AS BLOB))",
                     ("第一章正文……",))
        conn.execute(
            "INSERT INTO chapters VALUES ('chapter:c1', 'vol:1', 1, '第一章', 'draft', "
            "'res:ch1', '', '{}', 1, '2026-01-01', '2026-01-01')")
        conn.execute(
            "INSERT INTO planning_assets VALUES "
            "('pa:draft1', 'project:p1', 'chapter_plan', 'ch1', 1, 'candidate', 'res:cp1', '{}')")

    def test_chain_composes_end_to_end(self):
        from scripts.novelos_compose_prompt import compose as _compose
        conn = _make_db()
        self._seed_chain(conn)
        # strategy 组装：吃到 direction + architecture 双上游
        sections = resolve_slots(conn, ASSET_DIRS["strategy"], project_id="project:p1")
        upstreams = [t for t, _ in sections if t.startswith("上游 ")]
        self.assertTrue(any("direction" in t for t in upstreams))
        self.assertTrue(any("architecture" in t for t in upstreams))
        # chapter-draft 组装：persona + chapter_plan 上游 + 四张 craft 卡
        sections = resolve_slots(conn, ASSET_DIRS["chapter-draft"], project_id="project:p1")
        titles = [t for t, _ in sections]
        self.assertTrue(any("创作者人格签名" in t for t in titles))
        self.assertTrue(any(t.startswith("上游 chapter_plan") for t in titles))
        self.assertEqual(sum(t.startswith("craft 方法卡") for t in titles), 4)
        # prose-review 组装：subject 为章节正文（chapter 表）+ craft 卡
        sections = resolve_slots(conn, ASSET_DIRS["prose-review"],
                                 project_id="project:p1", subject_id="chapter:c1")
        self.assertTrue(sections[0][0].startswith("被审章节正文"))
        self.assertIn("第一章正文", sections[0][1])
        self.assertGreaterEqual(sum(t.startswith("craft 方法卡") for t, _ in sections), 5)
        # continuity-extraction：subject 章节 + canon 最小集六节
        sections = resolve_slots(conn, ASSET_DIRS["continuity-extraction"],
                                 project_id="project:p1", subject_id="chapter:c1")
        self.assertEqual(len(sections), 7)
        self.assertTrue(sections[0][0].startswith("被审章节正文"))
        out = _compose(ASSET_DIRS["continuity-extraction"], {"setup": {}}, sections)
        self.assertIn("判定标准（五条边界）", out)


def _seed_canon_ledgers(conn: sqlite3.Connection) -> None:
    """按活库列名（schema.sql）seed 六类 canon 账本——P0-1 的注入断言素材。"""
    conn.executemany(
        "INSERT INTO resources VALUES (?, CAST(? AS BLOB))",
        [("res:f1", "师弟私铸灵根被逐出师门"),
         ("res:np1", "师门血案真相未明"), ("res:ep1", "每卷至少一次打脸兑现"),
         ("res:rl1", "同门至交，渐生嫌隙"), ("res:ar1", "复仇弧进入第二阶段")])
    conn.execute("INSERT INTO books VALUES ('book:1', 'project:p1')")
    conn.execute("INSERT INTO volumes VALUES ('vol:1', 'book:1', 1)")
    conn.execute(
        "INSERT INTO chapters VALUES ('chapter:c9', 'vol:1', 9, '第九章', 'accepted', "
        "'res:f1', '主角查明铸根案一角', '{}', 1, '2026-01-01', '2026-01-02')")
    conn.execute(
        "INSERT INTO chapter_facts VALUES "
        "('fact:1', 'project:p1', 'chapter:c9', 'character_state', '林昭', 'res:f1', 'accepted')")
    conn.execute(
        "INSERT INTO narrative_promises VALUES "
        "('promise:1', 'project:p1', '师门血案真相', 'res:np1', 'open')")
    conn.execute(
        "INSERT INTO expectation_ledgers VALUES "
        "('exp:1', 'project:p1', '打脸节奏', 'res:ep1', 'open')")
    conn.execute(
        "INSERT INTO relationship_states VALUES "
        "('rel:1', 'project:p1', '林昭', '沈青梧', 'res:rl1')")
    conn.execute(
        "INSERT INTO arc_states VALUES ('arc:1', 'project:p1', '复仇弧', 'res:ar1')")
    # 干扰项：他项目的账本不得混入
    conn.execute(
        "INSERT INTO chapter_facts VALUES "
        "('fact:2', 'project:other', 'chapter:c9', 'character_state', '别人家的角色', 'res:f1', 'accepted')")


class CanonLedgerInjection(unittest.TestCase):
    """P0-1：canon 账本 SQL 对齐活库列名——五账本 + 近期章节真实注入，且按项目隔离。"""

    def test_ledgers_injected_with_live_columns(self):
        from scripts.novelos_compose_prompt import _slot_canon_minimal
        conn = _make_db()
        _seed_canon_ledgers(conn)
        sections = _slot_canon_minimal(conn, "project:p1")
        self.assertEqual(len(sections), 6)
        by_title = {t: b for t, b in sections}
        facts = by_title["canon 最小集 · facts（近 12 条）"]
        self.assertIn("林昭", facts)
        self.assertIn("师弟私铸灵根被逐出师门", facts)  # 描述来自 resources JOIN
        self.assertNotIn("别人家的角色", facts)
        self.assertIn("师门血案真相", by_title["canon 最小集 · narrative_promises（未决近 8 条）"])
        self.assertIn("打脸节奏", by_title["canon 最小集 · expectations（近 6 条）"])
        rel = by_title["canon 最小集 · relationship_states（近 8 条）"]
        self.assertIn("林昭", rel)
        self.assertIn("沈青梧", rel)
        self.assertIn("复仇弧", by_title["canon 最小集 · arc_states（近 4 条）"])
        recent = by_title["canon 最小集 · 近期已接受章节（近 5 章）"]
        self.assertIn("第九章", recent)
        self.assertIn("主角查明铸根案一角", recent)

    def test_degradation_is_visible(self):
        """缺表降级必须打 stderr，禁止静默吞错（回归闸）。"""
        import contextlib
        import io
        from scripts.novelos_compose_prompt import _slot_canon_minimal
        conn = sqlite3.connect(":memory:")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            sections = _slot_canon_minimal(conn, "project:x")
        self.assertEqual(len(sections), 6)
        self.assertTrue(all("（空）" == b for _, b in sections))
        self.assertIn("账本查询降级", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
