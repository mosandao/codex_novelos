from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIZARD_DATA_FILE = REPO_ROOT / "ui/project-wizard-data.js"
ARCHETYPE_CONFIG = REPO_ROOT / "config/system_archetypes.json"
REQUEST_SCHEMA = REPO_ROOT / "config/schemas/project-create-request.schema.json"


def _load_wizard_data() -> dict:
    raw = WIZARD_DATA_FILE.read_text(encoding="utf-8")
    return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])


class WizardMirrorConsistency(unittest.TestCase):
    """向导原型镜像必须与 config/system_archetypes.json 逐项一致（防漂移守护）。

    向导用镜像里的 subject_hash 生成提交 JSON；config 是落库反查的权威。
    两者漂移 = 血缘链从创建第一天就是歪的。
    """

    @classmethod
    def setUpClass(cls):
        cls.wizard = _load_wizard_data()
        cls.mirror = {a["profile_version_id"]: a for a in cls.wizard["system_archetypes"]}
        cls.cfg = {
            f"creator-profile-version:{a['id']}:{a['revision']}": a
            for a in json.loads(ARCHETYPE_CONFIG.read_text(encoding="utf-8"))
        }

    def test_mirror_covers_all_config_archetypes(self):
        self.assertEqual(
            set(self.mirror), set(self.cfg),
            "镜像与 config 的原型集合不一致（增删原型后忘记同步镜像）",
        )

    def test_mirror_subject_hash_no_drift(self):
        drift = [
            pvid for pvid, m in self.mirror.items()
            if pvid in self.cfg and m["subject_hash"] != self.cfg[pvid]["subject_hash"]
        ]
        self.assertEqual(drift, [], f"镜像 subject_hash 漂移: {drift}")

    def test_mirror_display_name_and_channel_affinity(self):
        for pvid, m in self.mirror.items():
            a = self.cfg.get(pvid)
            if a is None:
                continue
            self.assertEqual(m["display_name"], a["display_name"], f"{pvid} display_name 漂移")
            self.assertEqual(
                m.get("channel_affinity"), a.get("channel_affinity"),
                f"{pvid} channel_affinity 漂移",
            )
            self.assertIn(m.get("channel_affinity"), ("男频", "女频", "通吃"))

    def test_mirror_signature_matches_config(self):
        for pvid, m in self.mirror.items():
            a = self.cfg.get(pvid)
            if a is None:
                continue
            self.assertEqual(m.get("signature"), a.get("signature"), f"{pvid} signature 漂移")


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

    def test_recommendation_rules_present(self):
        rules = self.wizard["recommendation_rules"]
        self.assertIsInstance(rules, dict)
        self.assertTrue(rules, "recommendation_rules 为空")


class RequestSchemaIntegrity(unittest.TestCase):
    def test_schema_json_loadable_with_expected_anchor(self):
        schema = json.loads(REQUEST_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["properties"]["request_type"]["const"],
            "novelos.project.create.v2",
        )
        setup_props = schema["properties"]["setup"]["properties"]
        for field in (
            "title", "creator", "channel", "platform", "platform_traits",
            "scale", "primary_genre", "secondary_directions",
            "emotional_surface", "emotional_core", "tonal_contrast",
            "aesthetic_styles", "genre_profile", "reference_material",
        ):
            self.assertIn(field, setup_props)


if __name__ == "__main__":
    unittest.main()
