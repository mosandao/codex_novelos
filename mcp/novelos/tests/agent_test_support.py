from __future__ import annotations

from typing import Any


def complete_agent_run(
    service: Any,
    trace_id: str,
    role_id: str,
    output_type: str,
    output: Any,
    input_overrides: dict[str, Any] | None = None,
    isolation_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    role = service.agent_contracts.get(role_id)
    bindings = {name: f"test:{name}" for name in role["minimum_inputs"]}
    bindings.update(input_overrides or {})
    # 测试 harness 默认声明隔离凭据；真实运行由 主控智能体 传入 Codex Task 的 agentId。
    evidence = isolation_evidence if isolation_evidence is not None else {"source": "test_harness"}
    run = service.start_agent_run(trace_id, role_id, bindings, isolation_evidence=evidence)
    return service.finish_agent_run(run["id"], "completed", output_type, output)


def complete_review_run(
    service: Any,
    trace_id: str,
    subject_type: str,
    subject_ref: str,
    subject_hash: str,
    reviewer_profile: str,
    verdict: str = "approved",
    findings: list[dict[str, Any]] | None = None,
    evidence_refs: list[str] | None = None,
    assessment: dict[str, Any] | None = None,
    isolation_evidence: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_findings = findings or []
    normalized_evidence = evidence_refs or []
    output = {
        "subject_type": subject_type,
        "subject_ref": subject_ref,
        "subject_hash": subject_hash,
        "verdict": verdict,
        "findings": normalized_findings,
        "reviewer_profile": reviewer_profile,
        "evidence_refs": normalized_evidence,
    }
    if subject_type == "review_subject":
        output["assessment"] = assessment
    run = complete_agent_run(
        service,
        trace_id,
        "review_agent",
        "review_receipt_candidate",
        output,
        {
            "immutable_subject_ref": subject_ref,
            "subject_hash": subject_hash,
            "review_profile": reviewer_profile,
            "authority_context_refs": normalized_evidence or [subject_ref],
        },
        isolation_evidence=isolation_evidence,
    )
    review = service.record_review_from_run(run["id"])
    return run, review
