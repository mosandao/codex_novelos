from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.novelos_compose_prompt import ASSET_DIRS, load_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPES_PATH = REPO_ROOT / "config" / "agent-recipes.json"
RECIPES_MD = REPO_ROOT / "documentation" / "agent-recipes.md"


def _recipes() -> dict:
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))


def _render_table(recipes: dict) -> str:
    header = (
        "| 资产 | 槽位配方 | 发散档位 | 决策权限 | 输出契约 | 失败行为 |\n"
        "|---|---|---|---|---|---|\n"
    )
    rows = []
    for a in recipes["assets"]:
        div = a["divergence"] or "跟随被审对象"
        rows.append(
            f"| {a['asset']}（{a['skill']}） | {', '.join(a['slots'])} | {div} | "
            f"{a['decision_scope']} | {a['output']} | {a['failure']} |\n"
        )
    return header + "".join(rows)


class RecipeMatrix(unittest.TestCase):
    """配方矩阵：composer 已注册资产的 manifest 与矩阵一致；md 表格与 JSON 同步。"""

    def test_registered_assets_conform_to_matrix(self):
        recipes = {a["composer_key"]: a for a in _recipes()["assets"] if a["composer_key"]}
        for key, skill_dir in ASSET_DIRS.items():
            with self.subTest(asset=key):
                self.assertIn(key, recipes, f"composer 注册资产 {key} 缺矩阵行")
                manifest = load_manifest(skill_dir)
                row = recipes[key]
                self.assertEqual(manifest.get("divergence"), row["divergence"],
                                 f"{key}: divergence 与矩阵不符")
                self.assertEqual(manifest.get("decision_scope"), row["decision_scope"],
                                 f"{key}: decision_scope 与矩阵不符")
                extra = set(manifest.get("data_slots", [])) - set(row["slots"])
                self.assertFalse(extra, f"{key}: manifest 槽位超出矩阵（只许增长矩阵先行）: {extra}")

    def test_matrix_skill_dirs_exist(self):
        for a in _recipes()["assets"]:
            with self.subTest(asset=a["asset"]):
                self.assertTrue(
                    (REPO_ROOT / "catalog/skills" / a["skill"]).is_dir(),
                    f"矩阵行 {a['asset']} 指向的 skill 目录不存在: {a['skill']}",
                )

    def test_md_table_in_sync_with_json(self):
        self.assertTrue(RECIPES_MD.exists(), "documentation/agent-recipes.md 缺失")
        md = RECIPES_MD.read_text(encoding="utf-8")
        begin = "<!-- BEGIN RECIPES TABLE -->"
        end = "<!-- END RECIPES TABLE -->"
        self.assertIn(begin, md)
        block = md.split(begin, 1)[1].split(end, 1)[0]
        self.assertEqual(block.strip(), _render_table(_recipes()).strip(),
                         "agent-recipes.md 表格与 config/agent-recipes.json 漂移——重新生成表格")


if __name__ == "__main__":
    unittest.main()
