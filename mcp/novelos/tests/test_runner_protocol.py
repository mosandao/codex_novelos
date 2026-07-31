from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts" / "run_novelos_mcp.sh"


class UnifiedRunnerProtocolTest(unittest.IsolatedAsyncioTestCase):
    async def test_production_runner_starts_only_unified_server(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment.pop("NOVELOS_SEED_DB_PATH", None)
            environment.pop("NOVELOS_SEED_INVENTORY_PATH", None)
            environment["NOVELOS_DB_PATH"] = str(Path(directory) / "fresh.db")
            parameters = StdioServerParameters(
                command="bash",
                args=[str(RUNNER)],
                env=environment,
                cwd=ROOT,
            )
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    initialized = await session.initialize()
                    self.assertEqual("novelos", initialized.serverInfo.name)
                    tools = await session.list_tools()
                    names = {tool.name for tool in tools.tools}
                    self.assertEqual(71, len(names))
                    self.assertIn("project.wizard.render", names)
                    self.assertIn("project.wizard.submit", names)
                    self.assertIn("project.delete", names)
                    self.assertIn("agent.start", names)
                    self.assertIn("planning.prepare_cross_check", names)
                    self.assertIn("skill_catalog.validate_contract_inputs", names)
                    self.assertIn("skill_catalog.review_route", names)
                    self.assertIn("trace.audit_authority", names)
                    self.assertNotIn("save_chapter", names)
                    self.assertNotIn("upsert_entity", names)
                    knowledge = await session.call_tool("knowledge.search", {"query": "冲突", "limit": 1})
                    self.assertFalse(knowledge.isError, knowledge.content)
                    self.assertIsInstance(knowledge.structuredContent["result"], list)


if __name__ == "__main__":
    unittest.main()
