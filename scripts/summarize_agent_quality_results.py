from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "tasks" / "experiments" / "agent_quality"
DEFAULT_RESULTS = DEFAULT_DATASET / "results"
HASH_PREFIX = "sha256:"


class QualityResultError(ValueError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _bytes_hash(content: bytes) -> str:
    return HASH_PREFIX + hashlib.sha256(content).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise QualityResultError(f"缺少结果文件：{path}")
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise QualityResultError(f"JSONL 第 {number} 行非法：{path}") from exc
        if not isinstance(value, dict):
            raise QualityResultError(f"JSONL 第 {number} 行必须是对象：{path}")
        records.append(value)
    return records


def _require_fields(value: dict[str, Any], required: set[str], label: str) -> None:
    actual = set(value)
    if actual != required:
        raise QualityResultError(
            f"{label} 字段不匹配：缺少 {sorted(required - actual)}，未知 {sorted(actual - required)}"
        )


def _require_hash(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith(HASH_PREFIX)
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise QualityResultError(f"{label} 必须是 sha256 Hash")
    return value


def _require_id(value: Any, prefix: str, label: str) -> str:
    if not isinstance(value, str) or not value.startswith(prefix) or len(value) <= len(prefix):
        raise QualityResultError(f"{label} 必须以 {prefix} 开头")
    return value


def _evidence_path(results_root: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise QualityResultError("evidence_path 必须是非空相对路径")
    candidate = (results_root / relative).resolve()
    try:
        candidate.relative_to(results_root.resolve())
    except ValueError as exc:
        raise QualityResultError("evidence_path 不能逃逸 results 目录") from exc
    return candidate


def _json_artifact(results_root: Path, relative: Any, expected_hash: Any, label: str) -> dict[str, Any]:
    path = _evidence_path(results_root, relative)
    if not path.is_file():
        raise QualityResultError(f"缺少 {label} 文件：{path}")
    content = path.read_bytes()
    if _bytes_hash(content) != _require_hash(expected_hash, f"{label}_hash"):
        raise QualityResultError(f"{label}_hash 不匹配")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise QualityResultError(f"{label} 不是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise QualityResultError(f"{label} 必须是对象")
    return payload


def _validate_scores(
    scores: Any,
    labels: set[str],
    dimensions: list[dict[str, Any]],
    case_id: str,
) -> dict[str, float]:
    if not isinstance(scores, dict) or set(scores) != labels:
        raise QualityResultError(f"{case_id} scores 标签必须为 {sorted(labels)}")
    dimension_ids = {str(item["id"]) for item in dimensions}
    weights = {str(item["id"]): float(item["weight"]) for item in dimensions}
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise QualityResultError(f"{case_id} Rubric 权重之和必须为 1")
    totals: dict[str, float] = {}
    for label, values in scores.items():
        if not isinstance(values, dict) or set(values) != dimension_ids:
            raise QualityResultError(f"{case_id}/{label} 评分维度不完整")
        for dimension, score in values.items():
            if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
                raise QualityResultError(f"{case_id}/{label}/{dimension} 分数必须为 1–5 整数")
        totals[label] = sum(values[dimension] * weights[dimension] for dimension in dimension_ids)
    return totals


def _validate_evidence(
    results_root: Path,
    result: dict[str, Any],
    manifest: dict[str, Any],
    input_record: dict[str, Any],
) -> dict[str, Any]:
    path = _evidence_path(results_root, result["evidence_path"])
    if not path.is_file():
        raise QualityResultError(f"{result['case_id']} 缺少 evidence 文件：{path}")
    content = path.read_bytes()
    if _bytes_hash(content) != result["evidence_hash"]:
        raise QualityResultError(f"{result['case_id']} evidence_hash 不匹配")
    try:
        evidence = json.loads(content)
    except json.JSONDecodeError as exc:
        raise QualityResultError(f"{result['case_id']} evidence 不是合法 JSON") from exc
    if not isinstance(evidence, dict):
        raise QualityResultError(f"{result['case_id']} evidence 必须是对象")
    _require_fields(
        evidence,
        {"schema_version", "case_id", "input", "input_hash", "executions", "review"},
        f"{result['case_id']} evidence",
    )
    if (
        evidence["schema_version"] != 2
        or evidence["case_id"] != result["case_id"]
        or evidence["input"] != input_record
        or evidence["input_hash"] != manifest["input_hash"]
        or _bytes_hash(_canonical(evidence["input"]).encode("utf-8")) != manifest["input_hash"]
    ):
        raise QualityResultError(f"{result['case_id']} evidence 身份、原始输入或 input Hash 不匹配")
    expected_labels = {item["label"] for item in manifest["executions"]}
    executions = evidence["executions"]
    if not isinstance(executions, list) or len(executions) != len(expected_labels):
        raise QualityResultError(f"{result['case_id']} execution 数量不匹配")
    actual_labels: set[str] = set()
    producer_runs: set[str] = set()
    mode_by_label = {item["label"]: item["mode"] for item in manifest["executions"]}
    for execution in executions:
        if not isinstance(execution, dict):
            raise QualityResultError(f"{result['case_id']} execution 必须是对象")
        _require_fields(
            execution,
            {
                "label",
                "actor",
                "trace_id",
                "producer_run_id",
                "output_ref",
                "output_path",
                "output_hash",
                "media_type",
            },
            f"{result['case_id']} execution",
        )
        label = execution["label"]
        if label in actual_labels or label not in expected_labels:
            raise QualityResultError(f"{result['case_id']} execution label 非法或重复")
        actual_labels.add(label)
        _require_id(execution["trace_id"], "trace:", "trace_id")
        expected_actor = (
            "main_agent"
            if mode_by_label[label] in {"main_plus_skill", "memory_skill"}
            else "temporary_agent"
        )
        if execution["actor"] != expected_actor:
            raise QualityResultError(f"{result['case_id']}/{label} actor 与执行模式不匹配")
        if execution["actor"] == "temporary_agent":
            producer_run = _require_id(execution["producer_run_id"], "agent-run:", "producer_run_id")
            if producer_run in producer_runs:
                raise QualityResultError(f"{result['case_id']} Producer run 不能复用")
            producer_runs.add(producer_run)
        else:
            if execution["producer_run_id"] is not None:
                raise QualityResultError(f"{result['case_id']} Main 基线不能伪造 producer_run_id")
        if not isinstance(execution["output_ref"], str) or not execution["output_ref"].strip():
            raise QualityResultError(f"{result['case_id']} output_ref 不能为空")
        output_hash = _require_hash(execution["output_hash"], "output_hash")
        if execution["media_type"] not in {"text/markdown", "application/json"}:
            raise QualityResultError(f"{result['case_id']}/{label} media_type 非法")
        output_path = _evidence_path(results_root, execution["output_path"])
        if not output_path.is_file() or _bytes_hash(output_path.read_bytes()) != output_hash:
            raise QualityResultError(f"{result['case_id']}/{label} 匿名输出文件或 Hash 不匹配")
    review = evidence["review"]
    if not isinstance(review, dict):
        raise QualityResultError(f"{result['case_id']} review 必须是对象")
    _require_fields(
        review,
        {
            "trace_id",
            "subject_ref",
            "subject_path",
            "subject_hash",
            "receipt_path",
            "receipt_hash",
            "assessment_path",
            "assessment_hash",
            "assessment_ref",
        },
        f"{result['case_id']} review",
    )
    review_trace_id = _require_id(review["trace_id"], "trace:", "review.trace_id")
    if any(execution["trace_id"] != review_trace_id for execution in executions):
        raise QualityResultError(f"{result['case_id']} Producer 与 Reviewer 必须属于同一 Trace")
    subject = _json_artifact(
        results_root,
        review["subject_path"],
        review["subject_hash"],
        f"{result['case_id']} review subject",
    )
    _require_fields(
        subject,
        {"schema_version", "case_id", "input_hash", "outputs", "review_profile"},
        f"{result['case_id']} review subject",
    )
    expected_outputs = sorted(
        (
            {
                "label": execution["label"],
                "output_ref": execution["output_ref"],
                "output_hash": execution["output_hash"],
                "media_type": execution["media_type"],
            }
            for execution in executions
        ),
        key=lambda item: item["label"],
    )
    if (
        subject["schema_version"] != 1
        or subject["case_id"] != result["case_id"]
        or subject["input_hash"] != manifest["input_hash"]
        or subject["outputs"] != expected_outputs
        or subject["review_profile"] != manifest["review_profile"]
        or review["subject_hash"] != result["review_subject_hash"]
    ):
        raise QualityResultError(f"{result['case_id']} 盲评 subject 内容或 Hash 不匹配")

    assessment = _json_artifact(
        results_root,
        review["assessment_path"],
        review["assessment_hash"],
        f"{result['case_id']} assessment",
    )
    receipt = _json_artifact(
        results_root,
        review["receipt_path"],
        review["receipt_hash"],
        f"{result['case_id']} Review Receipt",
    )
    _require_fields(
        receipt,
        {
            "id",
            "subject_type",
            "subject_ref",
            "subject_hash",
            "verdict",
            "findings",
            "reviewer_profile",
            "evidence_refs",
            "reviewer_run_id",
            "assessment_ref",
        },
        f"{result['case_id']} Review Receipt",
    )
    reviewer_run = _require_id(receipt["reviewer_run_id"], "agent-run:", "reviewer_run_id")
    if reviewer_run in producer_runs:
        raise QualityResultError(f"{result['case_id']} Reviewer run 必须与 Producer run 隔离")
    receipt_id = _require_id(receipt["id"], "review:", "review_receipt_id")
    subject_ref = _require_id(review["subject_ref"], "review-subject:", "review_subject_ref")
    evidence_refs = [execution["output_ref"] for execution in executions]
    if (
        receipt["subject_type"] != "review_subject"
        or receipt["subject_ref"] != subject_ref
        or receipt["subject_hash"] != review["subject_hash"]
        or receipt["reviewer_profile"] != manifest["review_profile"]
        or receipt["evidence_refs"] != evidence_refs
        or receipt["assessment_ref"] != review["assessment_ref"]
        or not isinstance(review["assessment_ref"], str)
        or not review["assessment_ref"].strip()
    ):
        raise QualityResultError(f"{result['case_id']} Review Receipt 与 subject 或 evidence 不匹配")
    findings = receipt["findings"]
    if not isinstance(findings, list) or any(not isinstance(item, dict) for item in findings):
        raise QualityResultError(f"{result['case_id']} Review Receipt findings 非法")
    receipt_blocking = any(item.get("severity") == "blocking" for item in findings)
    expected_verdict = "rejected" if receipt_blocking else "approved"
    if receipt["verdict"] != expected_verdict:
        raise QualityResultError(f"{result['case_id']} Review Receipt verdict 与 findings 不一致")
    return {
        "assessment": assessment,
        "assessment_ref": receipt["assessment_ref"],
        "producer_run_ids": producer_runs,
        "review_subject_ref": subject_ref,
        "trace_id": review_trace_id,
        "reviewer_run_id": reviewer_run,
        "receipt_id": receipt_id,
        "receipt_blocking": receipt_blocking,
    }


def build_summary(dataset_root: Path, results_root: Path) -> dict[str, Any]:
    rubric = yaml.safe_load((dataset_root / "rubric.yaml").read_text(encoding="utf-8"))
    manifest_records = _load_jsonl(dataset_root / "execution_manifest.jsonl")
    manifest = {record.get("case_id"): record for record in manifest_records}
    if len(manifest_records) != 70 or len(manifest) != 70 or None in manifest:
        raise QualityResultError("execution manifest 必须包含 70 个唯一 case")
    result_records = _load_jsonl(results_root / "case_results.jsonl")
    results = {record.get("case_id"): record for record in result_records}
    if len(result_records) != 70 or len(results) != 70 or set(results) != set(manifest):
        raise QualityResultError("case_results 必须完整覆盖 70 个唯一 case")

    input_records: dict[str, dict[str, Any]] = {}
    for dataset in ("planning", "character_world", "writer_ab", "context_builder_ab"):
        for record in _load_jsonl(dataset_root / f"{dataset}.jsonl"):
            case_id = record.get("case_id")
            if not isinstance(case_id, str) or case_id in input_records:
                raise QualityResultError("质量实验原始输入 case_id 非法或重复")
            input_records[case_id] = record
    if set(input_records) != set(manifest):
        raise QualityResultError("原始输入必须完整覆盖 execution manifest")
    for case_id, plan in manifest.items():
        if _bytes_hash(_canonical(input_records[case_id]).encode("utf-8")) != plan["input_hash"]:
            raise QualityResultError(f"{case_id} manifest input_hash 与原始输入不一致")

    dataset_counts = Counter(str(record["dataset"]) for record in manifest_records)
    if dataset_counts != {
        "planning": 40,
        "character_world": 10,
        "writer_ab": 10,
        "context_builder_ab": 10,
    }:
        raise QualityResultError("execution manifest 数据集计数不符合 40+10+10+10")

    planning_passes = 0
    conflict_passes = 0
    writer_wins = 0
    context_wins = 0
    writer_regressions = 0
    context_regressions = 0
    any_blocking = False
    evidence_digest_rows: list[dict[str, str]] = []
    seen_assessment_refs: set[str] = set()
    seen_producer_runs: set[str] = set()
    seen_reviewer_runs: set[str] = set()
    seen_receipts: set[str] = set()
    seen_review_subjects: set[str] = set()
    seen_traces: set[str] = set()

    for case_id in sorted(results):
        result = results[case_id]
        plan = manifest[case_id]
        dataset = str(plan["dataset"])
        base_fields = {
            "case_id",
            "input_hash",
            "status",
            "evidence_path",
            "evidence_hash",
            "review_subject_hash",
            "blocking",
            "scores",
        }
        additions = {
            "planning": {"boundary_passed"},
            "character_world": {"conflict_detected"},
            "writer_ab": {"winner", "regression_labels"},
            "context_builder_ab": {"winner", "regression_labels"},
        }[dataset]
        _require_fields(result, base_fields | additions, case_id)
        if result["case_id"] != case_id or result["input_hash"] != plan["input_hash"]:
            raise QualityResultError(f"{case_id} 结果身份或 input_hash 不匹配")
        if result["status"] != "completed":
            raise QualityResultError(f"{case_id} 尚未完成，不能生成最终汇总")
        _require_hash(result["evidence_hash"], "evidence_hash")
        _require_hash(result["review_subject_hash"], "review_subject_hash")
        if not isinstance(result["blocking"], bool):
            raise QualityResultError(f"{case_id} blocking 必须是布尔值")
        any_blocking = any_blocking or result["blocking"]
        validated_evidence = _validate_evidence(
            results_root, result, plan, input_records[case_id]
        )
        reviewer_run = str(validated_evidence["reviewer_run_id"])
        receipt = str(validated_evidence["receipt_id"])
        subject_ref = str(validated_evidence["review_subject_ref"])
        assessment_ref = str(validated_evidence["assessment_ref"])
        trace_id = str(validated_evidence["trace_id"])
        producer_runs = set(validated_evidence["producer_run_ids"])
        if producer_runs & (seen_producer_runs | seen_reviewer_runs):
            raise QualityResultError(f"{case_id} 跨 case 复用了 Agent run")
        if (
            reviewer_run in seen_reviewer_runs | seen_producer_runs
            or receipt in seen_receipts
            or subject_ref in seen_review_subjects
            or assessment_ref in seen_assessment_refs
            or trace_id in seen_traces
        ):
            raise QualityResultError(
                f"{case_id} 复用了 Trace、Review Subject、Reviewer run、Receipt 或 assessment"
            )
        seen_producer_runs.update(producer_runs)
        seen_reviewer_runs.add(reviewer_run)
        seen_receipts.add(receipt)
        seen_review_subjects.add(subject_ref)
        seen_assessment_refs.add(assessment_ref)
        seen_traces.add(trace_id)

        assessment = validated_evidence["assessment"]
        assessment_fields = {"schema_version", "case_id", "scores", "blocking"} | additions
        _require_fields(assessment, assessment_fields, f"{case_id} assessment")
        if assessment["schema_version"] != 1 or assessment["case_id"] != case_id:
            raise QualityResultError(f"{case_id} assessment 身份不匹配")
        for field in {"scores", "blocking"} | additions:
            if assessment[field] != result[field]:
                raise QualityResultError(f"{case_id} case_results 与 Receipt assessment 不一致：{field}")
        if validated_evidence["receipt_blocking"] != result["blocking"]:
            raise QualityResultError(f"{case_id} blocking 与 Review Receipt findings 不一致")

        dimensions = rubric[dataset]["dimensions"]
        score_labels = {"candidate"} if dataset == "planning" else {"pair"} if dataset == "character_world" else {"A", "B"}
        totals = _validate_scores(result["scores"], score_labels, dimensions, case_id)
        if dataset == "planning":
            if not isinstance(result["boundary_passed"], bool):
                raise QualityResultError(f"{case_id} boundary_passed 必须是布尔值")
            planning_passes += int(result["boundary_passed"] and not result["blocking"] and totals["candidate"] >= 3)
        elif dataset == "character_world":
            if not isinstance(result["conflict_detected"], bool):
                raise QualityResultError(f"{case_id} conflict_detected 必须是布尔值")
            conflict_passes += int(result["conflict_detected"] and not result["blocking"] and totals["pair"] >= 3)
        else:
            margin = float(rubric[dataset]["retention_rule"]["clear_win_margin"])
            difference = totals["A"] - totals["B"]
            calculated_winner = "A" if difference >= margin else "B" if difference <= -margin else "tie"
            if result["winner"] != calculated_winner:
                raise QualityResultError(f"{case_id} winner 与加权分数不一致")
            regressions = result["regression_labels"]
            if (
                not isinstance(regressions, list)
                or len(regressions) != len(set(regressions))
                or any(label not in {"A", "B"} for label in regressions)
            ):
                raise QualityResultError(f"{case_id} regression_labels 非法")
            mode_by_label = {item["label"]: item["mode"] for item in plan["executions"]}
            target_mode = "isolated_writer_agent" if dataset == "writer_ab" else "context_builder"
            target_label = next(label for label, mode in mode_by_label.items() if mode == target_mode)
            target_won = result["winner"] == target_label
            target_regressed = target_label in regressions
            if dataset == "writer_ab":
                writer_wins += int(target_won)
                writer_regressions += int(target_regressed)
            else:
                context_wins += int(target_won)
                context_regressions += int(target_regressed)
        evidence_digest_rows.append(
            {"case_id": case_id, "evidence_hash": result["evidence_hash"], "input_hash": result["input_hash"]}
        )

    writer_rate = writer_wins / dataset_counts["writer_ab"]
    context_rate = context_wins / dataset_counts["context_builder_ab"]
    writer_rule = rubric["writer_ab"]["retention_rule"]
    context_rule = rubric["context_builder_ab"]["retention_rule"]
    writer_decision = (
        "retain"
        if writer_rate >= float(writer_rule["minimum_clear_win_rate"])
        and (writer_rule["canon_regression_allowed"] or writer_regressions == 0)
        else "remove"
    )
    context_decision = (
        "exception_only"
        if context_rate >= float(context_rule["minimum_clear_win_rate"])
        and (context_rule["fact_regression_allowed"] or context_regressions == 0)
        else "remove"
    )
    core_passed = planning_passes == 40 and conflict_passes == 10 and not any_blocking
    return {
        "schema_version": 1,
        "status": "completed" if core_passed else "failed",
        "case_count": 70,
        "dataset_counts": dict(sorted(dataset_counts.items())),
        "planning_pass_count": planning_passes,
        "character_world_pass_count": conflict_passes,
        "writer_clear_win_rate": writer_rate,
        "writer_regression_count": writer_regressions,
        "writer_decision": writer_decision,
        "context_builder_clear_win_rate": context_rate,
        "context_builder_regression_count": context_regressions,
        "context_builder_decision": context_decision,
        "evidence_digest": _bytes_hash(_canonical(evidence_digest_rows).encode("utf-8")),
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def summary_is_current(dataset_root: Path, results_root: Path) -> bool:
    summary_path = results_root / "summary.json"
    if not summary_path.is_file():
        return False
    try:
        return summary_path.read_text(encoding="utf-8") == render(build_summary(dataset_root, results_root))
    except (OSError, QualityResultError, json.JSONDecodeError, KeyError, TypeError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 Agent 质量实验完整证据并生成决策汇总")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        content = render(build_summary(args.dataset_dir, args.results_dir))
    except QualityResultError as exc:
        raise SystemExit(str(exc)) from exc
    summary_path = args.results_dir / "summary.json"
    if args.check:
        if not summary_path.is_file() or summary_path.read_text(encoding="utf-8") != content:
            raise SystemExit(f"质量实验汇总不是当前证据的可重算结果：{summary_path}")
        return
    args.results_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
