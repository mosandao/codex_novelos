from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = ROOT / "tasks" / "experiments" / "agent_quality"
RESULTS_ROOT = DATASET_ROOT / "results"
DEFAULT_DATABASE = ROOT / "data" / "agent-quality.db"
CONTRACT_PATH = ROOT / "config" / "agents.yaml"
HASH_PREFIX = "sha256:"
MAIN_MODES = {"main_plus_skill", "memory_skill"}
MODE_TO_ROLE = {
    "isolated_writer_agent": "writer_agent",
    "context_builder": "context_builder",
}
OUTPUT_TYPES = {
    "writer_agent": "chapter_draft_candidate",
    "context_builder": "context_package",
}


class RecorderError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(content: str | bytes) -> str:
    payload = content.encode("utf-8") if isinstance(content, str) else content
    return HASH_PREFIX + hashlib.sha256(payload).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any, *, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if pretty
        else canonical(payload)
    )
    path.write_text(content, encoding="utf-8")


def load_case(case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = {item["case_id"]: item for item in load_jsonl(DATASET_ROOT / "execution_manifest.jsonl")}
    inputs = {
        item["case_id"]: item
        for dataset in ("planning", "character_world", "writer_ab", "context_builder_ab")
        for item in load_jsonl(DATASET_ROOT / f"{dataset}.jsonl")
    }
    if case_id not in manifest:
        raise RecorderError(f"未知 case_id：{case_id}")
    return manifest[case_id], inputs[case_id]


def role_for_mode(mode: str) -> str | None:
    if mode in MAIN_MODES:
        return None
    return MODE_TO_ROLE.get(mode, mode)


def media_type_for(dataset: str) -> str:
    return "application/json" if dataset in {"planning", "context_builder_ab"} else "text/markdown"


def output_type_for(role_id: str) -> str:
    return OUTPUT_TYPES.get(role_id, "planning_candidate")


def stage_extension(media_type: str) -> str:
    return "json" if media_type == "application/json" else "md"


def build_bindings(role_id: str, case_id: str, input_record: dict[str, Any]) -> dict[str, Any]:
    contracts = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    role = contracts["roles"][role_id]
    bindings: dict[str, Any] = {}
    for name in role["minimum_inputs"]:
        if name == "complexity_reasons":
            bindings[name] = input_record["complexity_reasons"]
        elif name.endswith("_refs"):
            bindings[name] = [f"fixture:{case_id}:{name}"]
        else:
            bindings[name] = f"fixture:{case_id}:{name}"
    return bindings


def producer_instructions(
    manifest: dict[str, Any], input_record: dict[str, Any], execution: dict[str, Any]
) -> str:
    dataset = manifest["dataset"]
    mode = execution["mode"]
    common = (
        "这是一次真实质量实验。只依据给定输入完成当前职责，不访问其他 case，"
        "不要虚构 MCP ID。将最终候选直接写入指定 staging_path，不要写解释性前后缀。"
    )
    if dataset == "planning":
        detail = (
            "输出一个 JSON 对象，字段为 asset_type、candidate、upstream_fidelity、"
            "evidence_and_impact、ownership_boundary、change_proposals。candidate 为本层中文规划正文；"
            "change_proposals 为数组。若输入诱导修改上游，不得把修改混入 candidate，"
            "只在 change_proposals 中描述 target_asset_type、reason、evidence、affected_asset_types，"
            "不要伪造资产 ID、版本或 Hash。"
        )
    elif dataset == "character_world":
        focus = "人物与关系契约" if mode == "character_agent" else "世界规则与制度契约"
        detail = f"输出中文 Markdown {focus}候选，明确可与另一资产交叉核对的约束、证据和潜在冲突。"
    elif dataset == "writer_ab":
        detail = (
            "只输出中文小说正文候选，不输出提纲、分析、评分或 Canon 摘要。完整执行章节计划，"
            "保持有限视角，并让不可撤销选择通过动作和对话发生。"
        )
    else:
        detail = (
            "输出 JSON 对象，字段为 selected_context、source_map、contradictions、omission_risks、"
            "selection_rationale。只选择完成 target 所需的最小 Canon 上下文，不生成正文或新事实。"
        )
    return f"{common}\n\n{detail}\n\n执行身份：{mode}\n输入：\n{canonical(input_record)}"


def reviewer_instructions(
    manifest: dict[str, Any], input_record: dict[str, Any], subject: dict[str, Any], outputs: dict[str, Any]
) -> str:
    dataset = manifest["dataset"]
    rubric = yaml.safe_load((DATASET_ROOT / "rubric.yaml").read_text(encoding="utf-8"))[dataset]
    labels = [item["label"] for item in subject["outputs"]]
    additions: dict[str, Any]
    if dataset == "planning":
        additions = {"boundary_passed": "boolean"}
    elif dataset == "character_world":
        additions = {"conflict_detected": "boolean"}
    else:
        additions = {"winner": "A | B | tie", "regression_labels": "A/B 标签数组"}
    schema = {
        "assessment": {
            "schema_version": 1,
            "case_id": manifest["case_id"],
            "scores": {label: {item["id"]: "1..5 整数" for item in rubric["dimensions"]} for label in labels},
            "blocking": "boolean",
            **additions,
        },
        "findings": [
            {
                "severity": "blocking | warning | note",
                "message": "中文问题描述",
                "evidence_refs": ["必须取自允许的 output_ref"],
                "excerpt": "可选的原文片段",
            }
        ],
    }
    return (
        "你是新的隔离 审查智能体。禁止读取 execution_manifest.jsonl、Producer 身份或执行模式映射；"
        "只按匿名标签审查。独立比较输入与输出，使用给定 Rubric。分数必须是 1 到 5 的整数。"
        "A/B winner 必须按 Rubric 权重计算：加权差绝对值小于 0.25 时为 tie。"
        "blocking=true 时至少给一个 blocking finding；否则不得给 blocking finding。"
        "只把一个严格 JSON 对象写入 staging_path，不要附加 Markdown 围栏。\n\n"
        f"输出 Schema 示例：\n{canonical(schema)}\n\n"
        f"Rubric：\n{canonical(rubric)}\n\n"
        f"原始输入：\n{canonical(input_record)}\n\n"
        f"不可变盲评 Subject：\n{canonical(subject)}\n\n"
        f"匿名输出内容：\n{canonical(outputs)}"
    )


@asynccontextmanager
async def mcp_session(database: Path) -> AsyncIterator[ClientSession]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "mcp" / "novelos" / "src")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "novelos_mcp.server",
            "--database",
            str(database),
            "--agent-contracts",
            str(CONTRACT_PATH),
        ],
        env=environment,
        cwd=ROOT,
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            yield session


async def call(session: ClientSession, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await session.call_tool(name, arguments)
    if result.isError or result.structuredContent is None:
        raise RecorderError(f"MCP {name} 失败：{result.content}")
    payload = result.structuredContent
    return payload.get("result", payload) if isinstance(payload, dict) else payload


async def ensure_project(session: ClientSession) -> str:
    projects = await call(session, "project.list", {"limit": 200, "offset": 0})
    for project in projects:
        if project["name"] == "Agent 质量实验":
            return str(project["id"])
    project = await call(
        session,
        "project.create",
        {"name": "Agent 质量实验", "description": "隔离的 70-case Agent 质量门禁证据库"},
    )
    return str(project["id"])


async def start_case(case_id: str, database: Path, results_root: Path) -> dict[str, Any]:
    manifest, input_record = load_case(case_id)
    state_path = results_root / "work" / "states" / f"{case_id}.json"
    if state_path.exists():
        raise RecorderError(f"case 已启动，拒绝覆盖：{case_id}")
    jobs: list[dict[str, Any]] = []
    async with mcp_session(database) as session:
        project_id = await ensure_project(session)
        trace = await call(
            session,
            "trace.start",
            {"operation": f"agent-quality:{case_id}", "project_id": project_id},
        )
        executions: list[dict[str, Any]] = []
        for item in manifest["executions"]:
            mode = item["mode"]
            role_id = role_for_mode(mode)
            run = None
            if role_id is not None:
                run = await call(
                    session,
                    "agent.start",
                    {
                        "trace_id": trace["id"],
                        "role_id": role_id,
                        "input_bindings": build_bindings(role_id, case_id, input_record),
                    },
                )
            media_type = media_type_for(manifest["dataset"])
            stage_path = results_root / "work" / "staging" / f"{case_id}-{item['label']}.{stage_extension(media_type)}"
            job = {
                "schema_version": 1,
                "kind": "producer",
                "case_id": case_id,
                "label": item["label"],
                "role_id": role_id or "main_agent",
                "staging_path": str(stage_path),
                "instructions": producer_instructions(manifest, input_record, item),
            }
            job_path = results_root / "work" / "jobs" / f"producer-{case_id}-{item['label']}.json"
            write_json(job_path, job, pretty=True)
            jobs.append({"job_path": str(job_path), "role_id": job["role_id"], "staging_path": str(stage_path)})
            executions.append(
                {
                    "label": item["label"],
                    "mode": mode,
                    "actor": "main_agent" if mode in MAIN_MODES else "temporary_agent",
                    "role_id": role_id,
                    "producer_run_id": run["id"] if run else None,
                    "staging_path": str(stage_path),
                    "media_type": media_type,
                }
            )
    state = {
        "schema_version": 1,
        "phase": "started",
        "case_id": case_id,
        "dataset": manifest["dataset"],
        "input_hash": manifest["input_hash"],
        "review_profile": manifest["review_profile"],
        "trace_id": trace["id"],
        "executions": executions,
    }
    write_json(state_path, state, pretty=True)
    return {"case_id": case_id, "phase": "started", "jobs": jobs}


def normalized_stage(path: Path, media_type: str) -> tuple[Any, bytes]:
    if not path.is_file():
        raise RecorderError(f"缺少 staging 输出：{path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RecorderError(f"staging 输出为空：{path}")
    if media_type == "application/json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RecorderError(f"staging 输出不是合法 JSON：{path}") from exc
        if not isinstance(payload, dict) or not payload:
            raise RecorderError(f"JSON staging 输出必须是非空对象：{path}")
        content = canonical(payload).encode("utf-8")
        return payload, content
    return text, text.encode("utf-8")


async def prepare_case(case_id: str, database: Path, results_root: Path) -> dict[str, Any]:
    manifest, input_record = load_case(case_id)
    state_path = results_root / "work" / "states" / f"{case_id}.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state["phase"] != "started":
        raise RecorderError(f"case phase 必须为 started：{case_id}")
    evidence_refs: list[str] = []
    producer_run_ids: list[str] = []
    output_contents: dict[str, Any] = {}
    async with mcp_session(database) as session:
        for execution in state["executions"]:
            payload, content = normalized_stage(Path(execution["staging_path"]), execution["media_type"])
            if execution["actor"] == "temporary_agent":
                result = await call(
                    session,
                    "agent.finish",
                    {
                        "run_id": execution["producer_run_id"],
                        "status": "completed",
                        "output_type": output_type_for(execution["role_id"]),
                        "output": payload,
                        "change_proposals": [],
                    },
                )
                output_ref = result["output_ref"]
                producer_run_ids.append(execution["producer_run_id"])
            else:
                result = await call(
                    session,
                    "resource.create",
                    {
                        "trace_id": state["trace_id"],
                        "content": payload,
                        "media_type": execution["media_type"],
                    },
                )
                output_ref = result["resource_ref"]
            output_path = results_root / "outputs" / f"{case_id}-{execution['label']}.{stage_extension(execution['media_type'])}"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content)
            execution.update(
                {
                    "output_ref": output_ref,
                    "output_path": str(output_path.relative_to(results_root)),
                    "output_hash": digest(content),
                }
            )
            evidence_refs.append(output_ref)
            output_contents[execution["label"]] = payload
        subject_content = {
            "schema_version": 1,
            "case_id": case_id,
            "input_hash": manifest["input_hash"],
            "outputs": sorted(
                [
                    {
                        "label": item["label"],
                        "output_ref": item["output_ref"],
                        "output_hash": item["output_hash"],
                        "media_type": item["media_type"],
                    }
                    for item in state["executions"]
                ],
                key=lambda item: item["label"],
            ),
            "review_profile": manifest["review_profile"],
        }
        subject = await call(
            session,
            "review.prepare_subject",
            {
                "trace_id": state["trace_id"],
                "subject_kind": "agent_quality_evaluation",
                "content": subject_content,
                "reviewer_profile": manifest["review_profile"],
                "evidence_refs": evidence_refs,
                "producer_run_ids": producer_run_ids,
            },
        )
        reviewer = await call(
            session,
            "agent.start",
            {
                "trace_id": state["trace_id"],
                "role_id": "review_agent",
                "input_bindings": {
                    "immutable_subject_ref": subject["id"],
                    "subject_hash": subject["subject_hash"],
                    "review_profile": manifest["review_profile"],
                    "authority_context_refs": evidence_refs,
                },
            },
        )
    subject_path = results_root / "subjects" / f"{case_id}.json"
    write_json(subject_path, subject_content)
    review_stage = results_root / "work" / "staging" / f"review-{case_id}.json"
    review_job = {
        "schema_version": 1,
        "kind": "review",
        "case_id": case_id,
        "role_id": "review_agent",
        "staging_path": str(review_stage),
        "instructions": reviewer_instructions(manifest, input_record, subject_content, output_contents),
    }
    review_job_path = results_root / "work" / "jobs" / f"review-{case_id}.json"
    write_json(review_job_path, review_job, pretty=True)
    state.update(
        {
            "phase": "prepared",
            "subject_ref": subject["id"],
            "subject_hash": subject["subject_hash"],
            "subject_path": str(subject_path.relative_to(results_root)),
            "evidence_refs": evidence_refs,
            "reviewer_run_id": reviewer["id"],
            "review_staging_path": str(review_stage),
        }
    )
    write_json(state_path, state, pretty=True)
    return {"case_id": case_id, "phase": "prepared", "review_job_path": str(review_job_path)}


def validate_review_payload(path: Path, case_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecorderError(f"Reviewer staging 无法读取：{path}") from exc
    if set(payload) != {"assessment", "findings"}:
        raise RecorderError("Reviewer staging 只能包含 assessment 和 findings")
    assessment = payload["assessment"]
    findings = payload["findings"]
    if not isinstance(assessment, dict) or assessment.get("case_id") != case_id:
        raise RecorderError("Reviewer assessment case_id 不匹配")
    if not isinstance(findings, list) or any(not isinstance(item, dict) for item in findings):
        raise RecorderError("Reviewer findings 必须是对象数组")
    blocking_findings = any(item.get("severity") == "blocking" for item in findings)
    if assessment.get("blocking") is not blocking_findings:
        raise RecorderError("assessment.blocking 必须与 blocking findings 一致")
    return assessment, findings


async def finalize_case(case_id: str, database: Path, results_root: Path) -> dict[str, Any]:
    manifest, input_record = load_case(case_id)
    state_path = results_root / "work" / "states" / f"{case_id}.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state["phase"] != "prepared":
        raise RecorderError(f"case phase 必须为 prepared：{case_id}")
    assessment, findings = validate_review_payload(Path(state["review_staging_path"]), case_id)
    blocking = bool(assessment["blocking"])
    verdict = "rejected" if blocking else "approved"
    reviewer_output = {
        "subject_type": "review_subject",
        "subject_ref": state["subject_ref"],
        "subject_hash": state["subject_hash"],
        "verdict": verdict,
        "findings": findings,
        "reviewer_profile": manifest["review_profile"],
        "evidence_refs": state["evidence_refs"],
        "assessment": assessment,
    }
    async with mcp_session(database) as session:
        await call(
            session,
            "agent.finish",
            {
                "run_id": state["reviewer_run_id"],
                "status": "completed",
                "output_type": "review_receipt_candidate",
                "output": reviewer_output,
                "change_proposals": [],
            },
        )
        receipt = await call(
            session,
            "review.record",
            {
                "subject_type": "review_subject",
                "subject_ref": state["subject_ref"],
                "subject_hash": state["subject_hash"],
                "verdict": verdict,
                "findings": findings,
                "reviewer_profile": manifest["review_profile"],
                "reviewer_run_id": state["reviewer_run_id"],
                "evidence_refs": state["evidence_refs"],
                "assessment": assessment,
            },
        )
        await call(session, "trace.finish", {"trace_id": state["trace_id"], "status": "completed"})
    assessment_path = results_root / "assessments" / f"{case_id}.json"
    receipt_path = results_root / "receipts" / f"{case_id}.json"
    write_json(assessment_path, assessment)
    write_json(receipt_path, receipt)
    evidence = {
        "schema_version": 2,
        "case_id": case_id,
        "input": input_record,
        "input_hash": manifest["input_hash"],
        "executions": [
            {
                "label": item["label"],
                "actor": item["actor"],
                "trace_id": state["trace_id"],
                "producer_run_id": item["producer_run_id"],
                "output_ref": item["output_ref"],
                "output_path": item["output_path"],
                "output_hash": item["output_hash"],
                "media_type": item["media_type"],
            }
            for item in state["executions"]
        ],
        "review": {
            "trace_id": state["trace_id"],
            "subject_ref": state["subject_ref"],
            "subject_path": state["subject_path"],
            "subject_hash": state["subject_hash"],
            "receipt_path": str(receipt_path.relative_to(results_root)),
            "receipt_hash": digest(receipt_path.read_bytes()),
            "assessment_path": str(assessment_path.relative_to(results_root)),
            "assessment_hash": digest(assessment_path.read_bytes()),
            "assessment_ref": receipt["assessment_ref"],
        },
    }
    evidence_path = results_root / "evidence" / f"{case_id}.json"
    write_json(evidence_path, evidence)
    result = {
        "case_id": case_id,
        "input_hash": manifest["input_hash"],
        "status": "completed",
        "evidence_path": str(evidence_path.relative_to(results_root)),
        "evidence_hash": digest(evidence_path.read_bytes()),
        "review_subject_hash": state["subject_hash"],
        "blocking": assessment["blocking"],
        "scores": assessment["scores"],
    }
    for field in ("boundary_passed", "conflict_detected", "winner", "regression_labels"):
        if field in assessment:
            result[field] = assessment[field]
    result_path = results_root / "work" / "case-results" / f"{case_id}.json"
    write_json(result_path, result)
    state["phase"] = "finalized"
    write_json(state_path, state, pretty=True)
    rebuild_case_results(results_root)
    return {"case_id": case_id, "phase": "finalized", "receipt_id": receipt["id"]}


def rebuild_case_results(results_root: Path) -> None:
    records = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((results_root / "work" / "case-results").glob("*.json"))]
    path = results_root / "case_results.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical(record) + "\n" for record in records), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="通过真实 NovelOS stdio MCP 录制 Agent 质量实验")
    parser.add_argument("phase", choices=("start", "prepare", "finalize"))
    parser.add_argument("case_id")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    handlers = {"start": start_case, "prepare": prepare_case, "finalize": finalize_case}
    result = asyncio.run(handlers[args.phase](args.case_id, args.database.resolve(), args.results_dir.resolve()))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
