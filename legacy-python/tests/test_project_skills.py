from __future__ import annotations

import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = ROOT / ".agents" / "skills"
EXPECTED_SKILLS = {
    "novel-project",
    "novel-planning",
    "novel-memory",
    "novel-writing",
    "novel-review",
    "novel-continuity",
}


class ProjectSkillsTest(unittest.TestCase):
    def test_exactly_six_top_level_business_skills_exist(self) -> None:
        actual = {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()}
        self.assertEqual(EXPECTED_SKILLS, actual)

    def test_skill_frontmatter_and_interface_are_consistent(self) -> None:
        for name in EXPECTED_SKILLS:
            skill_text = (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(skill_text.startswith("---\n"), name)
            _, frontmatter, body = skill_text.split("---", 2)
            metadata = yaml.safe_load(frontmatter)
            self.assertEqual({"name", "description"}, set(metadata), name)
            self.assertEqual(name, metadata["name"])
            self.assertNotIn("TODO", body)

            interface_path = SKILLS_ROOT / name / "agents" / "openai.yaml"
            interface = yaml.safe_load(interface_path.read_text(encoding="utf-8"))["interface"]
            self.assertEqual({"display_name", "short_description", "default_prompt"}, set(interface), name)
            self.assertTrue(25 <= len(interface["short_description"]) <= 64, name)
            self.assertIn(f"${name}", interface["default_prompt"], name)


if __name__ == "__main__":
    unittest.main()
