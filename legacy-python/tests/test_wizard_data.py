from __future__ import annotations

import json
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[2]
WIZARD_DATA_FILE = REPO_ROOT / "plugin/client/project-wizard-data.js"
ARCHETYPE_CONFIG = REPO_ROOT / "config/system_archetypes.json"
REQUEST_SCHEMA = REPO_ROOT / "config/schemas/project-create-request.schema.json"


def _load_wizard_data() -> dict:
    raw = WIZARD_DATA_FILE.read_text(encoding="utf-8")
    return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])


class ArchetypeReferenceLibrary(unittest.TestCase):
    """原型退出创建链后的参考资料库完整性（Task 30 决策 2：内核完全取代原型）。

    config/system_archetypes.json 不再被向导镜像或创建管线消费，只作
    author-kernel-fusion / creator-signature-fusion 的气质参考。守护它的
    结构完整（条目数/字段/hash 格式），防止参考资料库慢慢烂掉。
    """

    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads(ARCHETYPE_CONFIG.read_text(encoding="utf-8"))

    def test_reference_library_shape(self):
        self.assertEqual(len(self.cfg), 26, "参考资料库条目数变化——确认是否有意增删原型")
        for a in self.cfg:
            for field in ("id", "display_name", "reader_promise", "subject_hash",
                          "signature", "revision"):
                self.assertIn(field, a, f"{a.get('id')} 缺 {field}")
            self.assertRegex(a["subject_hash"], r"^sha256:[0-9a-f]{64}$")
            self.assertRegex(a["id"], r"^system-[a-z][a-z0-9-]*$")

    def test_wizard_data_no_archetype_mirror(self):
        wizard = _load_wizard_data()
        self.assertNotIn("system_archetypes", wizard, "向导数据不得残留原型镜像（已由内核名册取代）")
        self.assertNotIn("recommendation_rules", wizard, "向导数据不得残留原型打分规则")


class WizardWordTables(unittest.TestCase):
    """词表完整性：级联与打分依赖的静态数据必须自洽。"""

    @classmethod
    def setUpClass(cls):
        cls.wizard = _load_wizard_data()

    def test_channel_platforms_covered_by_platform_traits(self):
        for channel, spec in self.wizard["channels"].items():
            for platform in spec["platforms"]:
                self.assertIn(
                    platform, self.wizard["platform_traits"],
                    f"{channel} 的平台 {platform} 缺 platform_traits 画像",
                )

    def test_genres_non_empty_per_channel(self):
        for channel in self.wizard["channels"]:
            genres = self.wizard["genres"].get(channel, [])
            if isinstance(genres, dict):
                genres = list(genres.keys())
            self.assertTrue(genres, f"{channel} 题材库为空")

    def test_secondary_directions_cover_all_genres(self):
        for channel in self.wizard["channels"]:
            genres = self.wizard["genres"].get(channel, [])
            if isinstance(genres, dict):
                genres = list(genres.keys())
            sd = self.wizard["secondary_directions"].get(channel, {})
            for genre in genres:
                self.assertTrue(
                    sd.get(genre),
                    f"{channel}×{genre} 缺二级方向词表",
                )

    def test_tone_pools_well_formed(self):
        poles = {"light", "dark", "neutral"}
        for channel, pool in self.wizard["tone_pools"].items():
            values = [t["value"] for t in pool]
            self.assertTrue(values, f"{channel} 基调池为空")
            self.assertEqual(len(values), len(set(values)), f"{channel} 基调池有重复项")
            for t in pool:
                self.assertIn(t["pole"], poles, f"{channel} 基调 {t['value']} 极性非法")

    def test_genre_profile_keys_reference_valid_genres(self):
        for key in self.wizard["genre_profiles"]:
            channel, _, genre = key.partition("|")
            self.assertIn(channel, self.wizard["channels"], f"genre_profile 键频道非法: {key}")
            genres = self.wizard["genres"].get(channel, [])
            if isinstance(genres, dict):
                genres = list(genres.keys())
            self.assertIn(genre, genres, f"genre_profile 键题材不在词表: {key}")

    def test_aesthetic_styles_unique(self):
        styles = self.wizard["aesthetic_styles"]
        self.assertGreaterEqual(len(styles), 10)
        self.assertEqual(len(styles), len(set(styles)))

class RequestSchemaIntegrity(unittest.TestCase):
    def test_schema_json_loadable_with_expected_anchor(self):
        schema = json.loads(REQUEST_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["properties"]["request_type"]["const"],
            "novelos.project.create.v3",
        )
        setup_props = schema["properties"]["setup"]["properties"]
        for field in (
            "title", "author_kernel", "channel", "platform",
            "platform_traits", "scale", "primary_genre", "secondary_directions",
            "emotional_surface", "emotional_core", "tonal_contrast",
            "aesthetic_styles", "genre_profile", "reference_material",
        ):
            self.assertIn(field, setup_props)
        self.assertNotIn("creator", setup_props, "v2 creator 段必须移除（内核完全取代原型）")


if __name__ == "__main__":
    unittest.main()
