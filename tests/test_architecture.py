from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novelos.agents import AgentRuntime, MainAgent
from novelos.domain import Chapter, ContinuationRequest, Entity
from novelos.mcp import InProcessMemoryGateway, MemoryMCPService
from novelos.skills import MemorySkill, ReviewSkill, WritingSkill


class ScriptedModel:
    def __init__(self, approved: bool = True) -> None:
        self.approved = approved

    def complete(self, system: str, prompt: str) -> str:
        if "REVIEW_REQUEST" in prompt:
            if self.approved:
                return '{"approved": true, "findings": []}'
            return (
                '{"approved": false, "findings": ['
                '{"severity": "blocking", "message": "Canon conflict", "excerpt": "x"}'
                "]}"
            )
        return "A new canonical scene."


class ArchitectureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database = Path(self.temp_dir.name) / "novel.db"
        self.gateway = InProcessMemoryGateway(MemoryMCPService(database))
        self.gateway.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def build_agent(
        self, approved: bool = True, threshold: int = 20
    ) -> tuple[MainAgent, AgentRuntime]:
        model = ScriptedModel(approved)
        runtime = AgentRuntime()
        return (
            MainAgent(
                gateway=self.gateway,
                memory_skill=MemorySkill(self.gateway, chapter_limit=3),
                writing_skill=WritingSkill(model),
                review_skill=ReviewSkill(model),
                runtime=runtime,
                spawn_context_builder_after=threshold,
            ),
            runtime,
        )

    def test_approved_chapter_is_reviewed_and_saved(self) -> None:
        self.gateway.save_chapter(Chapter(1, "Start", "Opening", "The journey begins."))
        self.gateway.upsert_entity(
            Entity("character", "Lin", "A cautious courier", {"location": "gate"})
        )
        agent, runtime = self.build_agent()

        result = agent.continue_chapter(
            ContinuationRequest(2, "Lin enters the city", title="The Gate")
        )

        self.assertTrue(result.saved)
        self.assertEqual(self.gateway.chapter_count(), 2)
        self.assertEqual(result.runtime_events, ("spawn:review", "destroy:review"))
        self.assertFalse(runtime.active)

    def test_blocking_review_prevents_save(self) -> None:
        agent, _ = self.build_agent(approved=False)

        result = agent.continue_chapter(ContinuationRequest(1, "Open the story"))

        self.assertFalse(result.saved)
        self.assertEqual(self.gateway.chapter_count(), 0)
        self.assertEqual(result.review.findings[0].severity, "blocking")

    def test_large_history_spawns_context_builder(self) -> None:
        for number in range(1, 4):
            self.gateway.save_chapter(Chapter(number, f"C{number}", "Body", "Summary"))
        agent, runtime = self.build_agent(threshold=3)

        result = agent.continue_chapter(ContinuationRequest(4, "Resolve the old thread"))

        self.assertEqual(
            result.runtime_events,
            (
                "spawn:context-builder",
                "destroy:context-builder",
                "spawn:review",
                "destroy:review",
            ),
        )
        self.assertFalse(runtime.active)

    def test_memory_search_crosses_mcp_boundary(self) -> None:
        self.gateway.add_memory("thread", "Broken seal", "The seal remains unresolved", 7)
        hits = self.gateway.search("seal")
        self.assertEqual(hits[0].label, "Broken seal")


class DependencyRuleTest(unittest.TestCase):
    def test_reasoning_layers_do_not_import_storage(self) -> None:
        repository = Path(__file__).parents[1]
        root = repository / "src" / "novelos"
        for layer in ("agents", "skills"):
            for path in (root / layer).glob("*.py"):
                source = path.read_text()
                self.assertNotIn("novelos.storage", source, path)
                self.assertNotIn("import sqlite3", source, path)
        for path in (repository / ".agents" / "skills").rglob("*"):
            if not path.is_file():
                continue
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("novelos.storage", source, path)
            self.assertNotIn("import sqlite3", source, path)


if __name__ == "__main__":
    unittest.main()
