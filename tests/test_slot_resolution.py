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
        CREATE TABLE project_creator_bindings (project_id TEXT, profile_version_id TEXT, kernel_version_id TEXT);
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
        CREATE TABLE reviews (
            id TEXT PRIMARY KEY, subject_type TEXT, subject_ref TEXT, subject_hash TEXT,
            verdict TEXT, findings_json TEXT, reviewer_profile TEXT, created_at TEXT);
        CREATE TABLE characters (
            id TEXT PRIMARY KEY, project_id TEXT, name TEXT,
            role_class TEXT DEFAULT 'secondary', status TEXT DEFAULT 'active',
            description_resource_id TEXT, state_json TEXT DEFAULT '{}',
            first_chapter_id TEXT, exit_chapter_id TEXT, exit_type TEXT,
            version INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT);
        """
    )
    return conn


def _seed_locked_direction(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO resources VALUES ('res:d1', CAST(? AS BLOB))",
                 ("# 故事方向（locked）\n力量货币：名望账。",))
    conn.execute(
        "INSERT INTO planning_assets VALUES "
        "('pa:d1', 'project:p1', 'direction', 'book', 1, 'locked', 'res:d1', "
        "'{\"book_soul\": {\"cadence_plan\": {\"fulfillment_count\": 4, \"interval_volumes\": 2}}}')")
    conn.execute(
        "INSERT INTO planning_assets VALUES "
        "('pa:a1', 'project:p1', 'architecture', 'book', 1, 'candidate', 'res:d1', '{\"engines\": []}')")


def _seed_direction_review(conn: sqlite3.Connection) -> None:
    """direction 锁定时的审查回执：strength 指认 + 豁免记录，供跨阶段注入断言。"""
    findings = [
        {"severity": "strength", "message": "低密度主线的赌注是设计意图，不得削平"},
        {"severity": "note", "message": "次要提示"},
        {"severity": "warning", "message": "下游执行边界提醒",
         "defer_to_downstream": "volume_outline"},
    ]
    conn.execute(
        "INSERT INTO reviews VALUES "
        "('rv:d1', 'planning_asset', 'pa:d1', ?, 'approved', ?, 'direction-review', '2026-01-02')",
        ("sha256:" + "b" * 64, json.dumps(findings, ensure_ascii=False)))


def _seed_locked_architecture_with_review(conn: sqlite3.Connection) -> None:
    """architecture 锁定 + 回执（defer→strategy 移交项），供 strategy-review 注入断言。"""
    conn.execute("UPDATE planning_assets SET status='locked' WHERE id='pa:a1'")
    findings = [
        {"severity": "warning", "message": "阶段侧须兑现单元配额对账",
         "defer_to_downstream": "strategy"},
        {"severity": "strength", "message": "双层引擎嵌套形态是本书独有赌注"},
    ]
    conn.execute(
        "INSERT INTO reviews VALUES "
        "('rv:a1', 'planning_asset', 'pa:a1', ?, 'approved', ?, 'architecture-review', '2026-01-03')",
        ("sha256:" + "d" * 64, json.dumps(findings, ensure_ascii=False)))


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
        # T34：上游 metadata（cadence_plan 等机器门产物）随 upstream 槽注入，不在阶段边界蒸发
        self.assertIn("--- 上游 metadata", sections[2][1])
        self.assertIn("cadence_plan", sections[2][1])
        self.assertIn("fulfillment_count", sections[2][1])

    def test_upstream_reviews_slot_flows_strength(self):
        """T34：direction 锁定回执（strength/豁免）跨阶段注入 architecture-review。"""
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_locked_direction(conn)
        _seed_direction_review(conn)
        sections = resolve_slots(conn, ASSET_DIRS["architecture-review"],
                                 project_id="project:p1", subject_id="pa:a1")
        titles = [t for t, _ in sections]
        self.assertTrue(any(t.startswith("上游 direction 审查回执") for t in titles))
        receipt = next(b for t, b in sections if t.startswith("上游 direction 审查回执"))
        self.assertIn("[strength]", receipt)
        self.assertIn("低密度主线", receipt)
        self.assertIn("defer→volume_outline", receipt)
        # 槽位贫血修复：审查侧补注 persona 全文与 setup 快照
        self.assertTrue(any(t.startswith("创作者人格签名") for t in titles))
        self.assertTrue(any(t.startswith("project_setup") for t in titles))

    def test_upstream_reviews_placeholder_when_absent(self):
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_locked_direction(conn)  # 无审查回执
        sections = resolve_slots(conn, ASSET_DIRS["architecture-review"],
                                 project_id="project:p1", subject_id="pa:a1")
        receipt = next(b for t, b in sections if t.startswith("上游 direction 审查回执"))
        self.assertIn("无回执记录", receipt)

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


class StrategySlots(unittest.TestCase):
    """T35：strategy 双侧槽位补齐——生成侧 persona/genre，审查侧双上游回执 + persona + setup。"""

    def test_generation_slots_include_persona_and_genre(self):
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_locked_direction(conn)
        conn.execute("UPDATE planning_assets SET status='locked' WHERE id='pa:a1'")
        sections = resolve_slots(conn, ASSET_DIRS["strategy"], project_id="project:p1",
                                 context={"setup": {"genre_profile": None}})
        titles = [t for t, _ in sections]
        self.assertIn("project_setup v2 快照（硬输入）", titles)
        self.assertTrue(any(t.startswith("创作者人格签名") for t in titles))
        self.assertTrue(any(t.startswith("上游 direction") for t in titles))
        self.assertTrue(any(t.startswith("上游 architecture") for t in titles))
        self.assertIn("题材信息包", titles)  # genre 缺位 → 占位节（题材缺位分支）

    def test_review_receives_both_upstream_receipts(self):
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_locked_direction(conn)
        _seed_direction_review(conn)
        _seed_locked_architecture_with_review(conn)
        conn.execute(
            "INSERT INTO planning_assets VALUES "
            "('pa:s1', 'project:p1', 'strategy', 'book', 1, 'candidate', 'res:d1', '{}')")
        sections = resolve_slots(conn, ASSET_DIRS["strategy-review"],
                                 project_id="project:p1", subject_id="pa:s1")
        titles = [t for t, _ in sections]
        self.assertTrue(any(t.startswith("上游 direction 审查回执") for t in titles))
        self.assertTrue(any(t.startswith("上游 architecture 审查回执") for t in titles))
        arch_receipt = next(b for t, b in sections if t.startswith("上游 architecture 审查回执"))
        self.assertIn("defer→strategy", arch_receipt)  # 移交给 strategy 的豁免项落地
        self.assertIn("[strength]", arch_receipt)  # 跨阶段 strength 保护
        self.assertTrue(any(t.startswith("创作者人格签名") for t in titles))
        self.assertTrue(any(t.startswith("project_setup") for t in titles))


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
    conn.execute("INSERT INTO project_creator_bindings (project_id, profile_version_id) VALUES ('project:p1', 'cpv:1')")
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
            ["project_setup v2 快照（硬输入）", "作者内核（kernel 全文）",
             "创作者人格签名（第一因，persona 全文）", "题材信息包"],
        )
        self.assertIn("无内核来源", sections[1][1])  # v2 旧项目无内核绑定 → 占位
        self.assertTrue(sections[2][1].startswith("subject_hash: sha256:"))
        self.assertIn("迷恋秩序又怀疑秩序", sections[2][1])

    def test_with_kernel_binding_injects_kernel_full(self):
        """kernel_derive 项目：kernel_full 注入内核全文（P2-1 链上注入）。"""
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_kernel_for_fusion(conn)
        conn.execute(
            "UPDATE project_creator_bindings SET kernel_version_id = 'creator-profile-version:k1:1' "
            "WHERE project_id = 'project:p1'")
        sections = resolve_slots(conn, ASSET_DIRS["direction"], project_id="project:p1",
                                 context={"setup": {}})
        kernel_sec = sections[1]
        self.assertTrue(kernel_sec[0].startswith("作者内核"))
        self.assertIn("测试内核", kernel_sec[1])
        self.assertIn("sha256:", kernel_sec[1])

    def test_without_binding_placeholder(self):
        conn = _make_db()
        conn.execute("INSERT INTO projects VALUES ('project:p2', '{}')")
        sections = resolve_slots(conn, ASSET_DIRS["direction"], project_id="project:p2",
                                 context={"setup": {}})
        self.assertEqual(sections[2][0], "创作者人格签名")
        self.assertIn("禁止无签名生成方向", sections[2][1])

    def test_review_slots_match_direction(self):
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_locked_direction(conn)
        d = resolve_slots(conn, ASSET_DIRS["direction"], project_id="project:p1",
                          context={"setup": {}})
        r = resolve_slots(conn, ASSET_DIRS["direction-review"], project_id="project:p1",
                          subject_id="pa:d1")
        self.assertEqual([t for t, _ in d][:3], [t for t, _ in r][:3])

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
        # continuity-extraction：subject 章节 + canon 最小集七节（含人物状态）
        sections = resolve_slots(conn, ASSET_DIRS["continuity-extraction"],
                                 project_id="project:p1", subject_id="chapter:c1")
        self.assertEqual(len(sections), 8)
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
    conn.execute(
        "INSERT INTO characters (id, project_id, name, role_class, status, exit_type, updated_at) VALUES "
        "('ch:a', 'project:p1', '林昭', 'main', 'active', NULL, '2026-01-02'), "
        "('ch:b', 'project:p1', '沈青梧', 'main', 'dead', '死亡型', '2026-01-03')")
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
        self.assertEqual(len(sections), 7)
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
        chars = by_title["canon 最小集 · 人物状态（死/退/眠优先，近 20 人）"]
        self.assertIn("沈青梧", chars)  # dead 优先
        self.assertIn("死亡型", chars)
        self.assertIn("林昭", chars)

    def test_degradation_is_visible(self):
        """缺表降级必须打 stderr，禁止静默吞错（回归闸）。"""
        import contextlib
        import io
        from scripts.novelos_compose_prompt import _slot_canon_minimal
        conn = sqlite3.connect(":memory:")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            sections = _slot_canon_minimal(conn, "project:x")
        self.assertEqual(len(sections), 7)
        self.assertTrue(all("（空）" == b for _, b in sections))
        self.assertIn("账本查询降级", stderr.getvalue())


def _seed_locked_world_with_meta(conn: sqlite3.Connection) -> None:
    """T36：locked world_contract，带 metadata（seats/lexicon/dimension_costs）。"""
    meta = {
        "seats": [
            {"name": "掌门", "org": "玄阳宗", "duty": "掌法度", "power_tier": "化神",
             "first_consumption": "第1卷·入门考核", "disposition": "待契约认领"},
        ],
        "lexicon": {
            "positive_terms": ["灵潮", "洗髓", "观星台"],
            "banned_categories": {"物理术语": ["能量"], "生物医学术语": ["神经"],
                                  "现代计量": ["米"], "现代认知框架": ["效率"]},
            "measure_system": "里丈尺·一炷香·斤两",
            "exceptions": [],
        },
        "dimension_costs": [
            {"dimension": "力量", "form": "灵潮反噬", "reversibility": "不可逆",
             "threshold": "第三次引潮后灵路焦结"},
        ],
    }
    conn.execute("INSERT INTO resources VALUES ('res:w1', CAST(? AS BLOB))",
                 ("# 世界契约（locked）\n力量体系：灵潮九阶。",))
    conn.execute(
        "INSERT INTO planning_assets VALUES "
        "('pa:w1', 'project:p1', 'world_contract', 'book', 1, 'locked', 'res:w1', ?)",
        (json.dumps(meta, ensure_ascii=False),))


def _seed_character_roster(conn: sqlite3.Connection) -> None:
    """T36：locked character_contract（roster 含 seat_ref）+ 注册表在库人物。"""
    meta = {"character_roster": [
        {"name": "沈青梧", "role_class": "main", "arc_role": "主角", "登场卷": 1,
         "预期退场": "持续活跃", "seat_ref": "掌门"},
    ]}
    conn.execute("INSERT INTO resources VALUES ('res:c1', CAST(? AS BLOB))",
                 ("# 人物契约（locked）\n## 人物档案：主角｜沈青梧",))
    conn.execute(
        "INSERT INTO planning_assets VALUES "
        "('pa:c1', 'project:p1', 'character_contract', 'book', 1, 'locked', 'res:c1', ?)",
        (json.dumps(meta, ensure_ascii=False),))
    conn.execute(
        "INSERT INTO characters VALUES ('char:1', 'project:p1', '陆沉舟', 'main', 'active', "
        "NULL, '{}', NULL, NULL, NULL, 1, '2026-01-01', '2026-01-01')")


class WorldCharacterSlots(unittest.TestCase):
    """T36：世界先行串行化——character 消费 world 上游；world_lexicon/character_roster 新槽。"""

    def test_character_compose_consumes_world_upstream(self):
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_locked_direction(conn)
        conn.execute("UPDATE planning_assets SET status='locked' WHERE id='pa:a1'")
        conn.execute(
            "INSERT INTO planning_assets VALUES "
            "('pa:s1', 'project:p1', 'strategy', 'book', 1, 'locked', 'res:d1', '{}')")
        _seed_locked_world_with_meta(conn)
        sections = resolve_slots(conn, ASSET_DIRS["character-contract"], project_id="project:p1",
                                 context={"setup": {"genre_profile": None}})
        titles = [t for t, _ in sections]
        world = next(b for t, b in sections if t.startswith("上游 world_contract"))
        self.assertIn("灵潮九阶", world)
        self.assertIn("--- 上游 metadata", world)   # seats/语域表随 metadata 到达人物层
        self.assertIn("掌门", world)
        self.assertTrue(any(t.startswith("创作者人格签名") for t in titles))
        self.assertTrue(any(t.startswith("project_setup") for t in titles))

    def test_character_compose_stops_without_world(self):
        """串行化后 world 是 character 硬上游——缺失即停（链形完整性）。"""
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_locked_direction(conn)
        conn.execute("UPDATE planning_assets SET status='locked' WHERE id='pa:a1'")
        conn.execute(
            "INSERT INTO planning_assets VALUES "
            "('pa:s1', 'project:p1', 'strategy', 'book', 1, 'locked', 'res:d1', '{}')")
        with self.assertRaises(SystemExit):
            resolve_slots(conn, ASSET_DIRS["character-contract"], project_id="project:p1")

    def test_world_generation_slots(self):
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_locked_direction(conn)
        conn.execute("UPDATE planning_assets SET status='locked' WHERE id='pa:a1'")
        conn.execute(
            "INSERT INTO planning_assets VALUES "
            "('pa:s1', 'project:p1', 'strategy', 'book', 1, 'locked', 'res:d1', "
            "'{\"handoffs\": {\"world_changes\": [\"第三卷宗门改制\"]}}')")
        sections = resolve_slots(conn, ASSET_DIRS["world-contract"], project_id="project:p1",
                                 context={"setup": {"genre_profile": None}})
        titles = [t for t, _ in sections]
        self.assertTrue(any(t.startswith("创作者人格签名") for t in titles))  # persona 盲区门
        strat = next(b for t, b in sections if t.startswith("上游 strategy"))
        self.assertIn("world_changes", strat)  # strategy 结构化产物随 metadata 注入

    def test_world_lexicon_slot_present_and_absent(self):
        conn = _make_db()
        _seed_user_persona(conn)
        _seed_locked_world_with_meta(conn)
        title, body = SLOT_REGISTRY["world_lexicon"](conn, "project:p1", None)
        self.assertIn("正面词汇表", body)
        self.assertIn("灵潮", body)
        self.assertIn("禁用·物理术语", body)
        self.assertIn("无声明即无例外", body)
        # 未锁定世界（旧项目）→ 警示占位不阻断
        conn2 = _make_db()
        _seed_user_persona(conn2)
        title2, body2 = SLOT_REGISTRY["world_lexicon"](conn2, "project:p1", None)
        self.assertIn("未锁定世界契约", body2)
        self.assertIn("change proposal", body2)

    def test_volume_compose_sees_world_and_roster(self):
        """卷纲盲区修复：world 全文 + 契约 roster/注册表镜像注入卷规划。"""
        conn = _make_db()
        _seed_user_persona(conn)
        conn.execute("INSERT INTO resources VALUES ('res:sa1', CAST(? AS BLOB))",
                     ("# 故事弧（locked）",))
        conn.execute(
            "INSERT INTO planning_assets VALUES "
            "('pa:sa1', 'project:p1', 'story_arc', 'book', 1, 'locked', 'res:sa1', '{}')")
        _seed_locked_world_with_meta(conn)
        _seed_character_roster(conn)
        sections = resolve_slots(conn, ASSET_DIRS["volume-outline"], project_id="project:p1")
        titles = [t for t, _ in sections]
        self.assertTrue(any(t.startswith("上游 world_contract") for t in titles))
        mirror = next(b for t, b in sections if t.startswith("人物名册镜像"))
        self.assertIn("[契约] 沈青梧", mirror)
        self.assertIn("席位:掌门", mirror)
        self.assertIn("[注册表] 陆沉舟", mirror)

    def test_character_roster_slot_empty_placeholder(self):
        conn = _make_db()
        _seed_user_persona(conn)
        title, body = SLOT_REGISTRY["character_roster"](conn, "project:p1", None)
        self.assertIn("均为空", body)


def _seed_persona_with_blindspots(conn: sqlite3.Connection) -> None:
    """T37：带结构化盲区与约束的分身（persona_gate 消费形态）。"""
    signature = {
        "persona": {"anchors": {
            "blindspots": {
                "refuses": ["拒绝写未成年人受虐细节"],
                "cannot_write": ["写不了 old money 酒局暗语——绕开：以外来者疏离感侧写，不展开黑话对白"],
            },
        }},
        "expression_preferences": ["偏好冷峻克制的叙述笔触"],
        "negative_constraints": ["不得放弃力量体系的严密性"],
    }
    conn.execute("INSERT INTO resources VALUES ('res:2', CAST(? AS BLOB))",
                 (json.dumps(signature, ensure_ascii=False),))
    conn.execute("INSERT INTO creator_profiles VALUES ('cp:2', 'user', '盲区分身')")
    conn.execute(
        "INSERT INTO creator_profile_versions VALUES "
        "('cpv:2', 'cp:2', 'creator-profile-version:system-test:2', '2026-01-01', 'res:2', ?)",
        ("sha256:" + "b" * 64,))
    conn.execute(
        "INSERT INTO project_creator_bindings (project_id, profile_version_id) "
        "VALUES ('project:p1', 'cpv:2')")
    conn.execute(
        "INSERT INTO projects VALUES ('project:p1', ?)",
        (json.dumps({"setup": {"channel": "男频", "title": "测试书"}}, ensure_ascii=False),))


def _seed_essence_registry(conn: sqlite3.Connection) -> None:
    """T37：注册表 main/secondary 带 essence/seat_ref（roster 落库形态）+ 退场态。"""
    conn.execute(
        "INSERT INTO characters VALUES ('char:e1', 'project:p1', '沈青梧', 'main', 'active', "
        "NULL, ?, NULL, NULL, NULL, 1, '2026-01-01', '2026-01-01')",
        (json.dumps({"arc_role": "主角", "seat_ref": "掌门",
                     "essence": "对除名牌位执念（谈宗族失措三秒）｜仙门雅言避市井俚语"},
                    ensure_ascii=False),))
    conn.execute(
        "INSERT INTO characters VALUES ('char:e2', 'project:p1', '白鹤鸣', 'secondary', "
        "'departed', NULL, '{}', NULL, 'chapter:x', '迁移型', 1, '2026-01-01', '2026-01-02')")


class EssenceGateSlots(unittest.TestCase):
    """T37：出场人物卡（character_essence）与 persona 硬边界门（persona_gate）双新槽。"""

    def test_character_essence_slot_present(self):
        conn = _make_db()
        _seed_essence_registry(conn)
        title, body = SLOT_REGISTRY["character_essence"](conn, "project:p1", None)
        self.assertIn("执念", body)
        self.assertIn("席位:掌门", body)
        self.assertIn("已退场:迁移型", body)   # 死活状态随行——正文端防无因复活

    def test_character_essence_slot_absent_placeholder(self):
        conn = _make_db()
        _seed_user_persona(conn)
        title, body = SLOT_REGISTRY["character_essence"](conn, "project:p1", None)
        self.assertIn("注册表无 main/secondary", body)

    def test_persona_gate_present_legacy_and_unbound(self):
        conn = _make_db()
        _seed_persona_with_blindspots(conn)
        title, body = SLOT_REGISTRY["persona_gate"](conn, "project:p1", None)
        self.assertIn("写不了", body)
        self.assertIn("绕开", body)
        self.assertIn("表达偏好", body)
        conn2 = _make_db()
        _seed_user_persona(conn2)   # 旧版分身：无结构化盲区/约束
        _, body2 = SLOT_REGISTRY["persona_gate"](conn2, "project:p1", None)
        self.assertIn("无结构化盲区", body2)
        conn3 = _make_db()
        _, body3 = SLOT_REGISTRY["persona_gate"](conn3, "project:p1", None)   # 未绑定
        self.assertIn("未绑定分身", body3)

    def test_chapter_plan_compose_gets_roster_and_gate(self):
        """T37：执行卡注入名册镜像（微档案查重数据）+ persona 硬边界门。"""
        conn = _make_db()
        _seed_persona_with_blindspots(conn)
        conn.execute("INSERT INTO resources VALUES ('res:vo1', CAST(? AS BLOB))",
                     ("# 卷纲（locked）",))
        conn.execute(
            "INSERT INTO planning_assets VALUES "
            "('pa:vo1', 'project:p1', 'volume_outline', 'book', 1, 'locked', 'res:vo1', '{}')")
        _seed_locked_world_with_meta(conn)
        _seed_character_roster(conn)
        _seed_essence_registry(conn)
        sections = resolve_slots(conn, ASSET_DIRS["chapter-plan"], project_id="project:p1")
        titles = [t for t, _ in sections]
        mirror = next(b for t, b in sections if t.startswith("人物名册镜像"))
        self.assertIn("沈青梧", mirror)
        gate = next(b for t, b in sections if t.startswith("persona 硬边界门"))
        self.assertIn("写不了", gate)

    def test_volume_and_draft_compose_get_new_slots(self):
        """卷纲 persona_gate；正文端 character_essence（出场人物卡）。"""
        conn = _make_db()
        _seed_persona_with_blindspots(conn)
        conn.execute("INSERT INTO resources VALUES ('res:sa1', CAST(? AS BLOB))",
                     ("# 故事弧（locked）",))
        conn.execute(
            "INSERT INTO planning_assets VALUES "
            "('pa:sa1', 'project:p1', 'story_arc', 'book', 1, 'locked', 'res:sa1', '{}')")
        _seed_locked_world_with_meta(conn)
        _seed_character_roster(conn)
        sections = resolve_slots(conn, ASSET_DIRS["volume-outline"], project_id="project:p1")
        self.assertTrue(any(b and "写不了" in b for t, b in sections
                            if t.startswith("persona 硬边界门")))
        conn2 = _make_db()
        _seed_persona_with_blindspots(conn2)
        conn2.execute("INSERT INTO resources VALUES ('res:cp1', CAST(? AS BLOB))",
                      ("# 执行卡（locked）",))
        conn2.execute(
            "INSERT INTO planning_assets VALUES "
            "('pa:cp1', 'project:p1', 'chapter_plan', 'book', 1, 'locked', 'res:cp1', '{}')")
        _seed_essence_registry(conn2)
        sections2 = resolve_slots(conn2, ASSET_DIRS["chapter-draft"], project_id="project:p1")
        essence = next(b for t, b in sections2 if t.startswith("出场人物卡"))
        self.assertIn("执念", essence)
        self.assertIn("已退场:迁移型", essence)


if __name__ == "__main__":
    unittest.main()
