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
        """
    )
    return conn


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


def _fusion_payload() -> dict:
    a = ARCHETYPES[0]
    version_id = f"creator-profile-version:{a['id']}:{a['revision']}"
    return {
        "request_type": "novelos.project.create.v2",
        "setup": {
            "title": "槽位测试书",
            "creator": {
                "mode": "derive",
                "selected_archetypes": [{
                    "profile_version_id": version_id,
                    "subject_hash": "sha256:" + "b" * 64,
                    "display_name": a["display_name"],
                }],
                "user_persona_hints": {"taste_anchors": ["低温叙事"]},
            },
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
        sections = resolve_slots(conn, ASSET_DIRS["direction"], project_id="project:p1")
        self.assertEqual(
            [t for t, _ in sections],
            ["project_setup v2 快照（硬输入）", "创作者人格签名（第一因，persona 全文）"],
        )
        self.assertTrue(sections[1][1].startswith("subject_hash: sha256:"))
        self.assertIn("迷恋秩序又怀疑秩序", sections[1][1])

    def test_without_binding_placeholder(self):
        conn = _make_db()
        conn.execute("INSERT INTO projects VALUES ('project:p2', '{}')")
        sections = resolve_slots(conn, ASSET_DIRS["direction"], project_id="project:p2")
        self.assertEqual(sections[1][0], "创作者人格签名")
        self.assertIn("禁止无签名生成方向", sections[1][1])

    def test_review_slots_match_direction(self):
        conn = _make_db()
        _seed_user_persona(conn)
        d = resolve_slots(conn, ASSET_DIRS["direction"], project_id="project:p1")
        r = resolve_slots(conn, ASSET_DIRS["direction-review"], project_id="project:p1")
        self.assertEqual([t for t, _ in d], [t for t, _ in r])

    def test_unregistered_slot_rejected(self):
        conn = _make_db()
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            (skill_dir / "modules").mkdir()
            (skill_dir / "modules" / "manifest.json").write_text(
                json.dumps({"modules": [], "data_slots": ["genre_pack"]}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                resolve_slots(conn, skill_dir, project_id="project:x")


class FusionSlots(unittest.TestCase):

    def test_payload_schema_and_section_order(self):
        conn = _make_db()
        _seed_user_persona(conn)
        payload = _fusion_payload()
        validate_fusion_payload(payload)  # 不抛即通过
        sections = resolve_slots(conn, ASSET_DIRS["fusion"], payload=payload)
        self.assertEqual(
            [t for t, _ in sections],
            [
                "selected_archetypes（选中条目全文——parent 判定与气质溯因只用这些）",
                "系统原型全库一行式清单（仅作语境：库里还有什么；禁止从清单外原型取材）",
                "user_persona_hints（人格素材）",
                "project_setup v2 快照",
                "跨批次比对基准人格（existing_persona_fingerprints，按量化范围取数）",
            ],
        )
        self.assertIn("display_name", sections[0][1])
        self.assertEqual(build_context_fusion(conn, payload)["selected_count"], 1)

    def test_empty_library_placeholder(self):
        conn = _make_db()
        sections = resolve_slots(conn, ASSET_DIRS["fusion"], payload=_fusion_payload())
        self.assertEqual(sections[4][0], "跨批次比对基准人格")
        self.assertIn("人格库为空", sections[4][1])

    def test_invalid_payload_rejected(self):
        with self.assertRaises(SystemExit):
            validate_fusion_payload({"setup": {}})  # 缺 request_type
        payload = _fusion_payload()
        payload["setup"]["creator"]["selected_archetypes"][0]["profile_version_id"] = "bogus"
        with self.assertRaises(SystemExit):
            validate_fusion_payload(payload)

    def test_selected_ids_read_from_nested_creator(self):
        # 向导契约：selected_archetypes 在 setup.creator 内（防顶层旧读法回归）
        from scripts.novelos_compose_prompt import _fusion_selected_ids
        ids = _fusion_selected_ids(_fusion_payload())
        self.assertEqual(len(ids), 1)
        self.assertTrue(ids[0].startswith("creator-profile-version:"))


if __name__ == "__main__":
    unittest.main()
