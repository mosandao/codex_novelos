from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.novelos_compose_prompt import (
    ASSET_DIRS,
    compose,
    content_hash,
    write_composition_log,
)


def _ctx(channel: str = "男频") -> dict:
    return {
        "setup": {
            "channel": channel,
            "platform_traits": {"model": "免费算法"},
            "genre_profile": None,
            "aesthetic_styles": ["冷峻"],
        },
    }


class CompositionLog(unittest.TestCase):
    """组装日志：确定性（同输入同 hash）、index 追加、路由事实入账、scope 净化。"""

    def test_same_input_same_hash_two_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            ctx = _ctx()
            text = compose(ASSET_DIRS["direction"], ctx, [])
            p1 = write_composition_log(log_dir, ASSET_DIRS["direction"],
                                       "direction", "project:abc", text, ctx)
            p2 = write_composition_log(log_dir, ASSET_DIRS["direction"],
                                       "direction", "project:abc", text, ctx)
            self.assertEqual(p1.read_text(encoding="utf-8"), p2.read_text(encoding="utf-8"))
            lines = (log_dir / "index.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            e1, e2 = (json.loads(x) for x in lines)
            self.assertEqual(e1["content_hash"], e2["content_hash"])
            self.assertEqual(e1["content_hash"], content_hash(text))

    def test_entry_records_routing_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            ctx = _ctx()
            text = compose(ASSET_DIRS["direction"], ctx, [])
            write_composition_log(log_dir, ASSET_DIRS["direction"],
                                  "direction", "project:abc", text, ctx)
            entry = json.loads(
                (log_dir / "index.jsonl").read_text(encoding="utf-8").strip())
            self.assertIn("channel-male", entry["modules"])
            self.assertNotIn("channel-female", entry["modules"])
            self.assertIn("genre-null", entry["modules"])
            self.assertEqual(entry["divergence"], "expansive")
            self.assertEqual(entry["decision_scope"], "propose_only")
            self.assertIn("persona_full", entry["data_slots"])
            self.assertTrue(entry["file"].startswith("project_abc/direction/"))

    def test_input_change_changes_hash(self):
        ctx_a, ctx_b = _ctx("男频"), _ctx("女频")
        ha = content_hash(compose(ASSET_DIRS["direction"], ctx_a, []))
        hb = content_hash(compose(ASSET_DIRS["direction"], ctx_b, []))
        self.assertNotEqual(ha, hb)


if __name__ == "__main__":
    unittest.main()
