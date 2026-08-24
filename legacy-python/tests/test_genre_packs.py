from __future__ import annotations

import json
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.novelos_compose_prompt import (
    ASSET_DIRS,
    _slot_review_feedback,
    resolve_slots,
)

from tests.test_slot_resolution import _make_db, _seed_user_persona, _seed_locked_direction

REPO_ROOT = Path(__file__).resolve().parents[2]


def _wizard_genre_profiles() -> dict:
    text = (REPO_ROOT / "plugin/client/project-wizard-data.js").read_text(encoding="utf-8")
    start = text.index("window.NOVELOS_WIZARD_DATA = ") + len("window.NOVELOS_WIZARD_DATA = ")
    return json.loads(text[start:].rstrip().rstrip(";"))["genre_profiles"]


class GenrePackAuthority(unittest.TestCase):
    """P3-1：config/genre-packs.json 与向导数据同步（单一事实源，漂移即红）。"""

    def test_config_in_sync_with_wizard_data(self):
        config = json.loads((REPO_ROOT / "config/genre-packs.json").read_text(encoding="utf-8"))
        wizard = _wizard_genre_profiles()
        self.assertEqual(config, wizard, "config/genre-packs.json 与向导 genre_profiles 漂移——重新抽取同步")

    def test_every_pack_has_four_fields(self):
        config = json.loads((REPO_ROOT / "config/genre-packs.json").read_text(encoding="utf-8"))
        for key, pack in config.items():
            with self.subTest(pack=key):
                for field in ("power_currency_candidates", "typical_dilemmas",
                              "reader_expectations", "taboos"):
                    self.assertIn(field, pack)
                    self.assertTrue(pack[field])


class GenrePackSlot(unittest.TestCase):
    """P3-2：genre_pack 槽——有包展开为一等节，无包声明缺位不回填。"""

    def test_with_and_without_pack(self):
        conn = _make_db()
        _seed_user_persona(conn)
        ctx_with = {"setup": {"genre_profile": {"power_currency_candidates": ["境界"]}}}
        sections = resolve_slots(conn, ASSET_DIRS["direction"], project_id="project:p1",
                                 context=ctx_with)
        pack_sections = [s for s in sections if s[0].startswith("题材信息包")]
        self.assertEqual(pack_sections[0][0], "题材信息包（genre_profile，硬输入）")
        self.assertIn("境界", pack_sections[0][1])

        sections = resolve_slots(conn, ASSET_DIRS["direction"], project_id="project:p1",
                                 context={"setup": {}})
        pack_sections = [s for s in sections if s[0].startswith("题材信息包")]
        self.assertIn("不从 config 回填", pack_sections[0][1])


class CanonMinimalSlot(unittest.TestCase):
    """P3-3：canon_minimal 六节结构（账本空表降级为（空）不炸）。"""

    def test_six_sections_degrade_gracefully(self):
        conn = _make_db()
        _seed_user_persona(conn)
        conn.execute(
            "INSERT INTO resources VALUES ('res:p1', CAST(? AS BLOB))", ("正文",))
        conn.execute("INSERT INTO books VALUES ('book:1', 'project:p1')")
        conn.execute("INSERT INTO volumes VALUES ('vol:1', 'book:1', 1)")
        conn.execute("INSERT INTO chapters VALUES ('chapter:c1','vol:1',1,'第一章','accepted',"
                     "'res:p1','摘要甲','{}',1,'2026-01-01','2026-01-01')")
        from scripts.novelos_compose_prompt import _slot_canon_minimal
        sections = _slot_canon_minimal(conn, "project:p1")
        self.assertEqual(len(sections), 7)  # 六类账本 + 人物状态
        self.assertTrue(sections[0][0].startswith("canon 最小集 · facts"))
        self.assertIn("（空）", sections[0][1])  # 账本未 seed 的节正常降级
        self.assertIn("摘要甲", sections[6][1])


class ReviewFeedbackSlot(unittest.TestCase):
    """P3-4：回执注入只取 blocking+warning；无回执不产生节；轮次入日志。"""

    def test_filters_severity(self):
        feedback = {"verdict": "rejected", "findings": [
            {"severity": "blocking", "message": "计量穿越", "evidence_refs": ["r1"]},
            {"severity": "warning", "message": "钩子弱"},
            {"severity": "note", "message": "备注不进槽"},
        ]}
        section = _slot_review_feedback(feedback)
        self.assertIn("[blocking] 计量穿越", section[1])
        self.assertIn("[warning] 钩子弱", section[1])
        self.assertNotIn("备注不进槽", section[1])
        self.assertIn("证据: ['r1']", section[1])

    def test_none_returns_none(self):
        self.assertIsNone(_slot_review_feedback(None))

    def test_round_logged(self):
        import tempfile
        from scripts.novelos_compose_prompt import write_composition_log
        ctx = {"setup": {"channel": "男频", "platform_traits": {"model": "免费算法"},
                         "genre_profile": None, "aesthetic_styles": []}}
        from scripts.novelos_compose_prompt import compose
        text = compose(ASSET_DIRS["direction"], ctx, [])
        with tempfile.TemporaryDirectory() as tmp:
            write_composition_log(Path(tmp), ASSET_DIRS["direction"], "direction",
                                  "project:x", text, ctx, review_round=2)
            entry = json.loads((Path(tmp) / "index.jsonl").read_text().strip())
            self.assertEqual(entry["review_round"], 2)


if __name__ == "__main__":
    unittest.main()
