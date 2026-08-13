from __future__ import annotations

import unittest

from scripts.novelos_render_projection import _split_character_contract


# 符合新结构约定的样例：总则/立场矩阵/对World假设（跨人物）+ 四个人物档案。
WELL_FORMED = """# 人物契约：示例

## 人物设计总则

三条铁律……

## 人物档案：主角｜塞维尔

### 初始状态
流放次子。

### 核心执念
拒绝成为棋子。

## 人物档案：主锚点｜伊诺

未定型存在。

## 人物档案：棋手｜渡脉者

旧神偷渡者。

## 人物档案：棋手｜余烬记录者

反驳派。

## central_contradiction 立场矩阵

五人光谱……

## Character 对 World 的假设

1. 假设一
"""

# 主角不在第一个位置，用于验证排序。
PROTAGONIST_NOT_FIRST = """## 人物档案：棋手｜渡脉者

旧神偷渡者。

## 人物档案：主角｜塞维尔

拒绝成为棋子。
"""

# 无「人物档案」标题（如当前西幻 r3 残缺契约风格），应触发兜底。
NO_CHARACTER_HEADINGS = """# 人物契约（修订版·核心执念补充）

## 核心执念（新增一级维度）

### 主角塞维尔的核心执念

**核心执念：拒绝成为任何棋手定义的棋子。**

## 早期失稳设计（前 30 章）

失稳点一……
"""


class SplitCharacterContractTest(unittest.TestCase):
    def test_splits_well_formed_contract(self) -> None:
        result = _split_character_contract(WELL_FORMED)
        assert result is not None
        chars = result["characters"]
        self.assertEqual(len(chars), 4)
        # 跨人物内容进总览：总则、立场矩阵、对World假设
        self.assertIn("人物设计总则", result["overview"])
        self.assertIn("立场矩阵", result["overview"])
        self.assertIn("对 World 的假设", result["overview"])
        # 人物 body 含其标题行与字段
        self.assertTrue(chars[0]["body"].startswith("## 人物档案：主角"))
        self.assertIn("核心执念", chars[0]["body"])
        self.assertIn("流放次子", chars[0]["body"])

    def test_protagonist_sorted_first(self) -> None:
        result = _split_character_contract(PROTAGONIST_NOT_FIRST)
        assert result is not None
        chars = result["characters"]
        self.assertEqual(len(chars), 2)
        self.assertEqual(chars[0]["role"], "主角")
        self.assertEqual(chars[0]["name"], "塞维尔")
        self.assertEqual(chars[1]["role"], "棋手")

    def test_returns_none_when_no_character_headings(self) -> None:
        # 无「人物档案」标题 → None（调用方走单文件兜底）
        self.assertIsNone(_split_character_contract(NO_CHARACTER_HEADINGS))
        # 空串同样兜底
        self.assertIsNone(_split_character_contract(""))

    def test_accepts_colon_and_pipe_variants(self) -> None:
        # 兼容英文冒号/竖线与中文冒号/竖线
        text = "## 人物档案: 主角 | 塞维尔\n\n拒绝成为棋子。\n"
        result = _split_character_contract(text)
        assert result is not None
        self.assertEqual(result["characters"][0]["role"], "主角")
        self.assertEqual(result["characters"][0]["name"], "塞维尔")

    def test_multiple_same_type_each_own_section(self) -> None:
        # 同类多人（两名棋手）各自独立 ## 人物档案，不合并
        text = (
            "## 人物档案：主角｜塞维尔\n\n主角。\n\n"
            "## 人物档案：棋手｜渡脉者\n\nA。\n\n"
            "## 人物档案：棋手｜余烬记录者\n\nB。\n"
        )
        result = _split_character_contract(text)
        assert result is not None
        roles = [c["role"] for c in result["characters"]]
        self.assertEqual(roles, ["主角", "棋手", "棋手"])
        names = [c["name"] for c in result["characters"]]
        self.assertEqual(names, ["塞维尔", "渡脉者", "余烬记录者"])


if __name__ == "__main__":
    unittest.main()
