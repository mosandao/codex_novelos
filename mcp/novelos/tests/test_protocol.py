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
                cwd=Path(directory),
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
                    self.assertIn("planning.create_candidate_from_run", names)
                    self.assertIn("planning.lock", names)
                    self.assertIn("planning.prepare_cross_check", names)
                    self.assertIn("planning.approve_cross_check", names)
                    self.assertIn("agent.start", names)
                    self.assertIn("agent.finish", names)
                    self.assertIn("skill_catalog.validate_output", names)
                    self.assertIn("skill_catalog.validate_input", names)
                    self.assertIn("review.record", names)
                    self.assertIn("review.record_from_run", names)
                    self.assertIn("review.prepare_subject", names)
                    self.assertIn("review.get_subject", names)
                    self.assertIn("resource.create", names)
                    self.assertIn("trace.audit_authority", names)
                    self.assertIn("entity.prepare_mutation", names)
                    self.assertIn("entity.commit_mutation", names)
                    self.assertIn("projection.get_snapshot", names)
                    self.assertIn("projection.render_project_folder", names)
                    self.assertNotIn("project.wizard.render", names)
                    self.assertIn("project.wizard.submit", names)
                    self.assertNotIn("project.wizard.suggest_secondary_directions", names)
                    self.assertIn("projection.verify_manifest", names)
                    self.assertNotIn("character.upsert", names)
                    self.assertNotIn("world.upsert", names)
                    self.assertNotIn("faction.upsert", names)
                    self.assertNotIn("rule.upsert", names)
                    self.assertNotIn("timeline.upsert", names)
                    by_name = {tool.name: tool for tool in tools.tools}
                    self.assertEqual(
                        ["app"],
                        by_name["project.wizard.submit"].meta["ui"]["visibility"],
                    )
                    self.assertTrue(
                        by_name["project.wizard.submit"].meta["openai/widgetAccessible"]
                    )
                    submit_annotations = by_name["project.wizard.submit"].annotations
                    self.assertFalse(submit_annotations.readOnlyHint)
                    self.assertFalse(submit_annotations.destructiveHint)
                    self.assertFalse(submit_annotations.idempotentHint)
                    self.assertFalse(submit_annotations.openWorldHint)
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
                    self.assertEqual(
                        ["reviewer_run_id"],
                        by_name["review.record_from_run"].inputSchema["required"],
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
                    wizard_title = f"向导协议项目-{Path(directory).name}"
                    archetype = await session.call_tool(
                        "creator_profile.get_version",
                        {"profile_version_id": "creator-profile-version:system-epic-framework:1"},
                    )
                    archetype_id = archetype.structuredContent["id"]
                    archetype_hash = archetype.structuredContent["subject_hash"]
                    wizard_result = await session.call_tool(
                        "project.wizard.submit",
                        {
                            "setup": {
                                "title": wizard_title,
                                "creator": {
                                    "mode": "derive",
                                    "parent_version_id": archetype_id,
                                    "parent_subject_hash": archetype_hash,
                                    "display_name": "协议测试作者",
                                    "overrides": {
                                        "recurring_attention": ["观察制度如何进入日常关系"],
                                    },
                                },
                                "channel": "女频",
                                "platform": "晋江",
                                "scale": "中篇（100-300万字）",
                                "primary_genre": "悬疑",
                                "secondary_directions": ["推理悬疑"],
                                "emotional_tones": ["悬疑紧张", "冷峻克制"],
                                "aesthetic_styles": ["民俗志怪"],
                                "reference_material": "案件线索应遵守公平推理。",
                            }
                        },
                    )
                    self.assertFalse(wizard_result.isError, wizard_result.content)
                    self.assertEqual(wizard_title, wizard_result.structuredContent["project"]["name"])
                    self.assertEqual("derive", wizard_result.structuredContent["creator_binding"]["binding_mode"])
                    self.assertEqual(1, wizard_result.structuredContent["creator_binding"]["profile_revision"])


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

    async def test_stdio_full_catalog_and_contract_boundary_flow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(PACKAGE_ROOT / "src")
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "novelos_mcp.server",
                    "--database",
                    str(Path(directory) / "boundary_flow.db"),
                    "--catalog",
                    str(PACKAGE_ROOT.parents[1] / "catalog" / "skills"),
                ],
                env=environment,
                cwd=Path(directory),
            )
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()

                    # 1. Catalog 搜索与选包验证 (全流程统一使用 story-causal-structure)
                    search_res = await session.call_tool("skill_catalog.search", {"stage": "plan", "asset": "architecture", "capability": "generate", "lifecycle": "experiment"})
                    self.assertFalse(search_res.isError, str(search_res))
                    names = [c["name"] for c in search_res.structuredContent["candidates"]]
                    self.assertIn("story-causal-structure", names)

                    sel_res = await session.call_tool("skill_catalog.validate", {
                        "selected_names": ["story-causal-structure"],
                        "candidate_names": names,
                        "snapshot_hash": search_res.structuredContent["snapshot_hash"],
                    })
                    self.assertFalse(sel_res.isError, str(sel_res))
                    self.assertTrue(sel_res.structuredContent["valid"])

                    # 2. Resource 读取
                    resource_res = await session.read_resource("novelos://catalog/story-causal-structure/prompt")
                    self.assertIn("因果", resource_res.contents[0].text)

                    def _get_res(res, key):
                        if res.structuredContent and isinstance(res.structuredContent, dict):
                            sc = res.structuredContent
                            if key in sc:
                                val = sc[key]
                                return int(val) if key == "version" and isinstance(val, (int, str)) and str(val).isdigit() else val
                            if key == "id" and "resource_id" in sc:
                                return sc["resource_id"]
                        if res.content and res.content[0].text:
                            text = res.content[0].text
                            try:
                                data = json.loads(text)
                                if isinstance(data, dict):
                                    if key in data:
                                        val = data[key]
                                        return int(val) if key == "version" and isinstance(val, (int, str)) and str(val).isdigit() else val
                                    if key == "id" and "resource_id" in data:
                                        return data["resource_id"]
                            except Exception:
                                pass
                            if key == "version":
                                return 1
                            if not text.strip().startswith("{"):
                                return text.strip("'\"")
                        return None

                    # 3. 通过本地向导生成的 setup 原子创建作者绑定项目与规划资产
                    archetype = await session.call_tool(
                        "creator_profile.get_version",
                        {"profile_version_id": "creator-profile-version:system-epic-framework:1"},
                    )
                    archetype_id = archetype.structuredContent["id"]
                    archetype_hash = archetype.structuredContent["subject_hash"]

                    proj_res = await session.call_tool("project.wizard.submit", {
                        "setup": {
                            "title": "Boundary Flow Project",
                            "creator": {
                                "mode": "derive",
                                "parent_version_id": archetype_id,
                                "parent_subject_hash": archetype_hash,
                                "display_name": "Boundary Flow Creator",
                                "overrides": {
                                    "recurring_attention": ["观察制度如何进入日常关系"],
                                },
                            },
                            "channel": "全向",
                            "platform": "起点",
                            "scale": "短篇（1-100万字）",
                            "primary_genre": "现实",
                            "secondary_directions": ["行业纪实"],
                            "emotional_tones": ["冷峻克制"],
                            "aesthetic_styles": ["市井烟火"],
                            "reference_material": None,
                        }
                    })

                    self.assertFalse(proj_res.isError, str(proj_res))
                    proj_id = proj_res.structuredContent["project"]["id"]
                    creator_ref = proj_res.structuredContent["creator_binding"]["constraint_ref"]
                    trace_res = await session.call_tool("trace.start", {"operation": "planning", "project_id": proj_id})
                    trace_id = _get_res(trace_res, "id")

                    agent_start = await session.call_tool("agent.start", {
                        "trace_id": trace_id,
                        "role_id": "direction_agent",
                        "input_bindings": {
                            "project_profile_ref": proj_id,
                            "user_constraints": "Story Constraints",
                            "catalog_snapshot_ref": "catalog:v1",
                            "creator_signature_ref": creator_ref,
                        },
                        "isolation_evidence": {"source": "test_protocol"},
                    })
                    producer_run_id = _get_res(agent_start, "id")
                    finish_res = await session.call_tool("agent.finish", {
                        "run_id": producer_run_id,
                        "status": "completed",
                        "output_type": "planning_candidate",
                        "output": "Story Direction Content",
                    })
                    self.assertFalse(finish_res.isError, str(finish_res))

                    dir_cand = await session.call_tool("planning.create_candidate_from_run", {
                        "project_id": proj_id,
                        "asset_type": "direction",
                        "scope_ref": proj_id,
                        "upstream_refs": [],
                        "metadata": {
                            "creator_signature_ref": creator_ref,
                            "book_soul": {
                                "schema_version": 1,
                                "unresolved_claims": ["制度能否在不消耗人的情况下维持效率"],
                                "central_contradiction": "个体自由与共同体责任都不可放弃，但无法同时完整满足",
                                "costly_commitments": ["宁愿让主角失败，也不转移其选择造成的代价"],
                                "protected_dignity": ["不羞辱失败者，也不免除其行为后果"],
                                "forbidden_resolutions": ["制度问题不得归罪于一个坏人后自动消失"],
                                "recurring_tests": ["每次以效率为名的牺牲都检查决策者是否承担同等风险"],
                                "narrative_mercy": "理解人物为何妥协，但不替其取消后果",
                                "narrative_cruelty": "让人物亲手承受其信念的反面结果",
                                "deliberate_silences": ["不由叙述者宣布人物是否获得原谅"],
                            },
                        },
                        "producer_run_id": producer_run_id,
                    })
                    self.assertFalse(dir_cand.isError, str(dir_cand))

                    rev_start = await session.call_tool("agent.start", {
                        "trace_id": trace_id,
                        "role_id": "review_agent",
                        "input_bindings": {
                            "immutable_subject_ref": _get_res(dir_cand, "id"),
                            "subject_hash": _get_res(dir_cand, "subject_hash"),
                            "review_profile": "planning-direction",
                            "authority_context_refs": [_get_res(dir_cand, "id")],
                        },
                        "isolation_evidence": {"source": "test_protocol"},
                    })
                    reviewer_run_id = _get_res(rev_start, "id")
                    rev_output = {
                        "subject_type": "planning_asset",
                        "subject_ref": _get_res(dir_cand, "id"),
                        "subject_hash": _get_res(dir_cand, "subject_hash"),
                        "verdict": "approved",
                        "findings": [],
                        "reviewer_profile": "planning-direction",
                        "evidence_refs": [_get_res(dir_cand, "id")],
                    }
                    await session.call_tool("agent.finish", {
                        "run_id": reviewer_run_id,
                        "status": "completed",
                        "output_type": "review_receipt_candidate",
                        "output": rev_output,
                    })

                    prep_sub = await session.call_tool("review.prepare_subject", {
                        "trace_id": trace_id,
                        "subject_kind": "planning_asset",
                        "subject_id": _get_res(dir_cand, "id"),
                        "subject_hash": _get_res(dir_cand, "subject_hash"),
                        "content": {"content": "Story Direction Content"},
                        "reviewer_profile": "planning-direction",
                        "evidence_refs": [_get_res(dir_cand, "id")],
                        "producer_run_ids": [producer_run_id],
                    })

                    rec_rev = await session.call_tool("review.record_from_run", {
                        "reviewer_run_id": reviewer_run_id,
                    })

                    lock_res = await session.call_tool("planning.lock", {
                        "asset_id": _get_res(dir_cand, "id"),
                        "review_id": _get_res(rec_rev, "id"),
                        "expected_version": _get_res(dir_cand, "version"),
                        "trace_id": trace_id,
                    })
                    self.assertFalse(lock_res.isError, str(lock_res))

                    # 4. validate_contract_inputs
                    contract_val = await session.call_tool("skill_catalog.validate_contract_inputs", {
                        "package_name": "story-causal-structure",
                        "project_id": proj_id,
                        "bindings": [
                            {
                                "contract": "direction",
                                "subject_ref": _get_res(lock_res, "id"),
                                "version": _get_res(lock_res, "version"),
                                "subject_hash": _get_res(lock_res, "subject_hash"),
                                "status": "locked",
                            }
                        ]
                    })
                    self.assertFalse(contract_val.isError, str(contract_val))
                    self.assertTrue(_get_res(contract_val, "valid"))


if __name__ == "__main__":
    unittest.main()
