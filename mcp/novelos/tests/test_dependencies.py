from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DependencyBoundaryTest(unittest.TestCase):
    def test_mcp_has_no_model_provider_or_prompt_runtime_dependency(self) -> None:
        forbidden = ("import openai", "from openai", "pydantic_ai", "langgraph")
        for path in (ROOT / "src").rglob("*.py"):
            source = path.read_text(encoding="utf-8").lower()
            for marker in forbidden:
                self.assertNotIn(marker, source, path)
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
        for dependency in ("openai", "pydantic-ai", "langgraph"):
            self.assertNotIn(dependency, project)


if __name__ == "__main__":
    unittest.main()
