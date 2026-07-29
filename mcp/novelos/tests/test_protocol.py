from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from novelos_mcp.seed_inventory import build_seed_inventory


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class NovelOSProtocolTest(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_initialize_tools_call_and_resource_template(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(PACKAGE_ROOT / "src")
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "novelos_mcp.server",
                    "--database",
                    str(Path(directory) / "protocol.db"),
                ],
                env=environment,
                cwd=PACKAGE_ROOT,
            )
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    initialized = await session.initialize()
                    self.assertEqual("novelos", initialized.serverInfo.name)

                    tools = await session.list_tools()
                    names = {tool.name for tool in tools.tools}
                    self.assertIn("project.create", names)
                    self.assertIn("chapter.accept", names)
                    self.assertIn("planning.create_candidate", names)
                    self.assertIn("planning.lock", names)
                    self.assertIn("planning.prepare_cross_check", names)
                    self.assertIn("planning.approve_cross_check", names)
                    self.assertIn("agent.start", names)
                    self.assertIn("agent.finish", names)
                    self.assertIn("skill_catalog.validate_output", names)
                    self.assertIn("skill_catalog.validate_input", names)
                    self.assertIn("review.record", names)
                    self.assertIn("review.prepare_subject", names)
                    self.assertIn("review.get_subject", names)
                    self.assertIn("resource.create", names)
                    self.assertIn("trace.audit_authority", names)
                    self.assertIn("entity.prepare_mutation", names)
                    self.assertIn("entity.commit_mutation", names)
                    self.assertNotIn("character.upsert", names)
                    self.assertNotIn("world.upsert", names)
                    self.assertNotIn("faction.upsert", names)
                    self.assertNotIn("rule.upsert", names)
                    self.assertNotIn("timeline.upsert", names)
                    by_name = {tool.name: tool for tool in tools.tools}
                    self.assertIn(
                        "producer_run_id",
                        by_name["planning.create_candidate"].inputSchema["required"],
                    )
                    self.assertNotIn(
                        "producer_role",
                        by_name["planning.create_candidate"].inputSchema["properties"],
                    )
                    self.assertIn(
                        "reviewer_run_id",
                        by_name["review.record"].inputSchema["required"],
                    )
                    for tool_name in (
                        "planning.lock",
                        "planning.approve_cross_check",
                        "chapter.accept",
                        "entity.commit_mutation",
                        "continuity.promote_reviewed",
                    ):
                        self.assertIn("trace_id", by_name[tool_name].inputSchema["required"])

                    result = await session.call_tool("project.create", {"name": "协议测试"})
                    self.assertFalse(result.isError)
                    self.assertEqual("协议测试", result.structuredContent["name"])
                    trace = await session.call_tool(
                        "trace.start",
                        {"operation": "quality-evaluation", "project_id": result.structuredContent["id"]},
                    )
                    output = await session.call_tool(
                        "resource.create",
                        {
                            "trace_id": trace.structuredContent["id"],
                            "content": "协议测试匿名输出",
                        },
                    )
                    self.assertFalse(output.isError)
                    subject = await session.call_tool(
                        "review.prepare_subject",
                        {
                            "trace_id": trace.structuredContent["id"],
                            "subject_kind": "agent_quality_evaluation",
                            "content": {
                                "schema_version": 1,
                                "case_id": "protocol-quality-case",
                                "input_hash": "sha256:" + "1" * 64,
                                "outputs": [
                                    {
                                        "label": "A",
                                        "output_ref": output.structuredContent["resource_ref"],
                                        "output_hash": output.structuredContent["content_hash"],
                                        "media_type": "text/markdown",
                                    }
                                ],
                                "review_profile": "agent-quality-blind-comparison",
                            },
                            "reviewer_profile": "agent-quality-blind-comparison",
                            "evidence_refs": [output.structuredContent["resource_ref"]],
                            "producer_run_ids": [],
                        },
                    )
                    self.assertFalse(subject.isError, subject.content)
                    fetched = await session.call_tool(
                        "review.get_subject", {"subject_id": subject.structuredContent["id"]}
                    )
                    self.assertEqual(
                        subject.structuredContent["subject_hash"],
                        fetched.structuredContent["subject_hash"],
                    )

                    templates = await session.list_resource_templates()
                    self.assertEqual(
                        {
                            "novelos://resource/{resource_id}",
                            "novelos://knowledge/{table}/{record_id}",
                            "novelos://catalog/{name}/{artifact}",
                        },
                        {str(template.uriTemplate) for template in templates.resourceTemplates},
                    )

    async def test_stdio_validates_seed_inventory_before_knowledge_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = root / "seed.db"
            with closing(sqlite3.connect(seed)) as connection:
                connection.execute(
                    "CREATE TABLE kb_methods(id INTEGER PRIMARY KEY, title TEXT, body TEXT)"
                )
                connection.execute("INSERT INTO kb_methods VALUES (1, '递进冲突', '逐步提高阻碍强度')")
                connection.commit()
            inventory = root / "seed-inventory.json"
            inventory.write_text(
                json.dumps(build_seed_inventory(seed, "synthetic-protocol")), encoding="utf-8"
            )
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(PACKAGE_ROOT / "src")
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "novelos_mcp.server",
                    "--database",
                    str(root / "protocol.db"),
                    "--seed-database",
                    str(seed),
                    "--seed-inventory",
                    str(inventory),
                ],
                env=environment,
                cwd=PACKAGE_ROOT,
            )
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    result = await session.call_tool("knowledge.search", {"query": "阻碍"})
                    self.assertFalse(result.isError)
                    self.assertEqual("递进冲突", result.structuredContent["result"][0]["title"])


if __name__ == "__main__":
    unittest.main()
