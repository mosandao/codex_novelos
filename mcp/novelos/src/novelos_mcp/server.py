from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from novelos_mcp.service import NovelOSService
from novelos_mcp.project_wizard import (
    normalize_project_setup,
)


def create_server(
    database_path: str | Path,
    seed_database_path: str | Path | None = None,
    catalog_path: str | Path | None = None,
    agent_contract_path: str | Path | None = None,
    seed_inventory_path: str | Path | None = None,
) -> FastMCP:
    service = NovelOSService(
        database_path=database_path,
        seed_database_path=seed_database_path,
        catalog_path=catalog_path,
        agent_contract_path=agent_contract_path,
        seed_inventory_path=seed_inventory_path,
    )
    server = FastMCP("novelos")

    def create_planning_candidate(
        project_id: str,
        asset_type: str,
        scope_ref: str,
        content: str,
        upstream_refs: list[dict[str, Any]],
        producer_run_id: str,
        metadata: dict[str, Any] | None = None,
        cross_check_id: str | None = None,
    ) -> dict[str, Any]:
        return service.create_planning_candidate(
            project_id,
            asset_type,
            scope_ref,
            content,
            upstream_refs,
            metadata=metadata,
            producer_run_id=producer_run_id,
            cross_check_id=cross_check_id,
        )

    def record_review(
        subject_type: str,
        subject_ref: str,
        subject_hash: str,
        verdict: str,
        findings: list[dict[str, Any]],
        reviewer_profile: str,
        reviewer_run_id: str,
        evidence_refs: list[str] | None = None,
        assessment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return service.record_review(
            subject_type,
            subject_ref,
            subject_hash,
            verdict,
            findings,
            reviewer_profile,
            evidence_refs,
            reviewer_run_id,
            assessment,
        )


    def submit_project_wizard(setup: dict[str, Any]) -> dict[str, Any]:
        name, description, metadata, creator = normalize_project_setup(setup)
        created = service.create_project_with_creator(name, description, metadata, creator)
        project = created["project"]
        projection = service.render_project_projection(project["id"])
        return {
            "project": project,
            "creator_binding": created["creator_binding"],
            "projection": projection,
        }

    tools: dict[str, Any] = {
        "creator_profile.create": service.create_creator_profile,
        "creator_profile.derive": service.derive_creator_profile,
        "creator_profile.revise": service.revise_creator_profile,
        "creator_profile.archive": service.archive_creator_profile,
        "creator_profile.get": service.get_creator_profile,
        "creator_profile.get_version": service.get_creator_profile_version,
        "creator_profile.list": service.list_creator_profiles,
        "project.create": service.create_project,
        "project.get": service.get_project,
        "project.list": service.list_projects,
        "project.update": service.update_project,
        "project.delete": service.delete_project,
        "project.creator.get_binding": service.get_project_creator_binding,
        "project.creator.get_style_refs": service.get_project_style_refs,
        "project.creator.rebind": service.rebind_project_creator,
        "creation_seed.get": service.get_creation_seed,
        "creation_seed.update": service.update_creation_seed,
        "creation_seed.list": service.list_creation_seeds,
        "book.create": service.create_book,
        "book.get": service.get_book,
        "book.list": service.list_books,
        "volume.create": service.create_volume,
        "volume.get": service.get_volume,
        "volume.list": service.list_volumes,
        "chapter.create_draft": service.create_chapter_draft,
        "chapter.update_draft": service.update_chapter_draft,
        "chapter.get": service.get_chapter,
        "chapter.list": service.list_chapters,
        "chapter.accept": service.accept_chapter,
        "chapter.supersede": service.supersede_chapter,
        "planning.create_candidate": create_planning_candidate,
        "planning.create_candidate_from_run": service.create_planning_candidate_from_run,
        "planning.create_revision_candidate": service.create_revision_candidate,
        "planning.extract_decision_points": service.extract_decision_points,
        "planning.get": service.get_planning_asset,
        "planning.list": service.list_planning_assets,
        "planning.lock": service.lock_planning_asset,
        "planning.prepare_cross_check": service.prepare_planning_cross_check,
        "planning.approve_cross_check": service.approve_planning_cross_check,
        "planning.get_cross_check": service.get_planning_cross_check,
        "entity.prepare_mutation": service.prepare_entity_mutation,
        "entity.commit_mutation": service.commit_entity_mutation,
        "character.get": service.get_character,
        "character.list": service.list_characters,
        "world.get": service.get_world,
        "world.list": service.list_worlds,
        "faction.get": service.get_faction,
        "faction.list": service.list_factions,
        "rule.get": service.get_rule,
        "rule.list": service.list_rules,
        "timeline.get": service.get_timeline,
        "timeline.list": service.list_timelines,
        "memory.recent_chapters": service.recent_chapters,
        "memory.search_facts": service.search_facts,
        "memory.get_entity_states": service.get_entity_states,
        "memory.get_authority_snapshot": service.get_authority_snapshot,
        "continuity.record_candidates": service.record_continuity_candidates,
        "continuity.get_candidates": service.get_continuity_candidates,
        "continuity.promote_reviewed": service.promote_reviewed_continuity,
        "resource.create": service.create_resource,
        "review.prepare_subject": service.prepare_review_subject,
        "review.get_subject": service.get_review_subject,
        "knowledge.search": service.search_knowledge,
        "knowledge.get": service.get_knowledge,
        "skill_catalog.search": service.search_skill_catalog,
        "skill_catalog.get": service.get_skill_catalog,
        "skill_catalog.validate": service.validate_skill_selection,
        "skill_catalog.validate_input": service.validate_skill_input,
        "skill_catalog.validate_output": service.validate_skill_output,
        "skill_catalog.validate_contract_inputs": service.validate_contract_inputs,
        "skill_catalog.review_route": service.get_review_catalog_route,
        "trace.start": service.start_trace,
        "trace.record_step": service.record_trace_step,
        "trace.finish": service.finish_trace,
        "trace.get": service.get_trace,
        "trace.audit_authority": service.audit_authority_trace,
        "agent.start": service.start_agent_run,
        "agent.finish": service.finish_agent_run,
        "agent.get": service.get_agent_run,
        "agent.list": service.list_agent_runs,
        "review.record": record_review,
        "review.record_from_run": service.record_review_from_run,
        "review.get": service.get_review,
        "projection.get_snapshot": service.get_projection_snapshot,
        "projection.render_project_folder": service.render_project_projection,
        "projection.verify_manifest": service.verify_project_projection,
    }

    def reconcile_project_wizard_archetypes(
        selected_archetypes: list[dict[str, Any]],
        project_setup: dict[str, Any],
        display_name: str,
    ) -> dict[str, Any]:
        return service.reconcile_project_wizard_archetypes(
            selected_archetypes,
            project_setup,
            display_name,
        )
    for name, handler in tools.items():
        server.tool(name=name)(handler)

    server.tool(
        name="project.wizard.submit",
        title="提交项目创建向导",
        description="校验作者签名与项目向导选择，原子创建项目和绑定并刷新项目投影。",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
        # Authorize the rendered MCP App to call this app-only tool through the
        # host proxy.  Without it, the browser can render the form but its
        # `tools/call` request is rejected before reaching the handler.
        meta={
            "ui": {"visibility": ["app"]},
            "openai/widgetAccessible": True,
        },
    )(submit_project_wizard)
    server.tool(
        name="project.wizard.reconcile_archetypes",
        title="融合项目向导多原型选择",
        description=(
            "把项目向导产出的多原型 selected_archetypes 与项目 setup 确定性融合为"
            "合规的单 parent derive 结构，供 project.wizard.submit 直接使用。"
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        meta={
            "ui": {"visibility": ["app"]},
            "openai/widgetAccessible": True,
        },
    )(reconcile_project_wizard_archetypes)
    @server.resource("novelos://resource/{resource_id}")
    def resource(resource_id: str) -> str:
        return service.get_resource(resource_id)

    @server.resource("novelos://knowledge/{table}/{record_id}")
    def knowledge_resource(table: str, record_id: str) -> str:
        return service.knowledge.get_resource(table, record_id)

    @server.resource("novelos://catalog/{name}/{artifact}")
    def catalog_resource(name: str, artifact: str) -> str:
        return service.catalog.get_resource(name, artifact)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="运行统一 NovelOS MCP Server")
    parser.add_argument("--database", default=os.environ.get("NOVELOS_DB_PATH", "data/novelos-v2.db"))
    parser.add_argument("--seed-database", default=os.environ.get("NOVELOS_SEED_DB_PATH"))
    parser.add_argument("--seed-inventory", default=os.environ.get("NOVELOS_SEED_INVENTORY_PATH"))
    parser.add_argument("--catalog", default=os.environ.get("NOVELOS_CATALOG_PATH"))
    parser.add_argument("--agent-contracts", default=os.environ.get("NOVELOS_AGENT_CONTRACT_PATH"))
    args = parser.parse_args()
    create_server(
        database_path=args.database,
        seed_database_path=args.seed_database,
        catalog_path=args.catalog,
        agent_contract_path=args.agent_contracts,
        seed_inventory_path=args.seed_inventory,
    ).run(transport="stdio")


if __name__ == "__main__":
    main()
