import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "tasks" / "07_prompt_catalog" / "quality_results"

REQUIRED_DIMENSIONS = {"relevance", "coherence", "depth", "boundary_compliance", "safety"}

def validate_case_evidence(case: dict, receipts_dir: Path) -> str | None:
    required_fields = [
        "case_id", "category", "input_hash", "baseline_hash", "candidate_hash",
        "package_hash", "anonymous_ab_map", "reviewer_run_id", "receipt_ref", "scores"
    ]
    for field in required_fields:
        if field not in case or not case[field]:
            return f"案例 {case.get('case_id')} 缺少必要的证据字段: {field}"

    if case["category"] not in {"World", "Plot", "Writing"}:
        return f"案例 {case.get('case_id')} 的 category 非法: {case['category']}"

    scores = case["scores"]
    if not isinstance(scores, dict) or set(scores.keys()) != REQUIRED_DIMENSIONS:
        return f"案例 {case.get('case_id')} 的 scores 必须精确包含 5 个维度: {REQUIRED_DIMENSIONS}"
    for dim, score in scores.items():
        if type(score) is not int or not (1 <= score <= 5):
            return f"案例 {case.get('case_id')} 维度 {dim} 的评分非法: {score}"

    ab_map = case["anonymous_ab_map"]
    if not isinstance(ab_map, dict) or set(ab_map.keys()) < {"A", "B", "unblinded_selection"}:
        return f"案例 {case.get('case_id')} 的 anonymous_ab_map 缺失 A/B 或解盲信息"

    receipt_ref = case["receipt_ref"]
    receipt_file = receipts_dir / f"{receipt_ref}.json"
    if not receipt_file.is_file():
        return f"案例 {case.get('case_id')} 找不到对应的 Review Receipt 文件: {receipt_file}"

    try:
        receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
        if receipt_data.get("reviewer_run_id") != case["reviewer_run_id"]:
            return f"案例 {case.get('case_id')} 的 reviewer_run_id 与 Receipt 记录不匹配"
        if receipt_data.get("subject_hash") != case["candidate_hash"]:
            return f"案例 {case.get('case_id')} 的 candidate_hash 与 Receipt 记录不匹配"
        if receipt_data.get("verdict") not in {"pass", "fail", "block"}:
            return f"案例 {case.get('case_id')} 的 Receipt verdict 非法"
        if not isinstance(receipt_data.get("findings"), list):
            return f"案例 {case.get('case_id')} 的 Receipt 缺失 findings 列表"

        rec_scores = receipt_data.get("scores")
        if not isinstance(rec_scores, dict) or set(rec_scores.keys()) != REQUIRED_DIMENSIONS:
            return f"案例 {case.get('case_id')} 的 Receipt scores 缺失 5 维评分"
        for dim in REQUIRED_DIMENSIONS:
            if rec_scores[dim] != scores[dim]:
                return f"案例 {case.get('case_id')} 维度 {dim} 的评分与 Receipt 记录不一致"

        calc_blocking = sum(1 for f in receipt_data.get("findings", []) if isinstance(f, dict) and f.get("severity") == "blocking")
        if case.get("blocking_count", 0) != calc_blocking or receipt_data.get("blocking_count", 0) != calc_blocking:
            return f"案例 {case.get('case_id')} 的 blocking_count 与 findings 统计不符合"
    except Exception as e:
        return f"读取 Receipt 异常: {e}"

    return None

def main():
    cases_file = RESULTS_DIR / "cases.json"
    receipts_dir = RESULTS_DIR / "receipts"

    def _block(reason: str):
        summary = {
            "dataset_version": 1,
            "case_count": 0,
            "blind_eval_verdict": "BLOCKED",
            "evaluated_packages": [],
            "status_reason": reason,
            "summary": {
                "blocking_issues_count": 0,
                "quality_degradation_detected": False,
                "target_dimension_improved": False,
                "recommendation": "blocked_due_to_missing_llm_eval_environment"
            }
        }
        output_path = RESULTS_DIR / "eval_results.json"
        output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Generated BLOCKED eval_results.json at {output_path}")

    if not cases_file.is_file() or not receipts_dir.is_dir():
        _block("当前环境缺乏真实 LLM 模型输出 API、匿名 A/B 映射与独立 Reviewer run 证据")
        return

    try:
        data = json.loads(cases_file.read_text(encoding="utf-8"))
        cases = data.get("cases", [])
        if len(cases) != 12:
            _block(f"12-case 质量评估案例数量必须恰好为 12 个 (当前 {len(cases)} case)，拒绝生成伪造结果")
            return

        categories = [c.get("category") for c in cases]
        if categories.count("World") != 4 or categories.count("Plot") != 4 or categories.count("Writing") != 4:
            _block(f"12-case 分类分布必须恰好为 4 World / 4 Plot / 4 Writing (当前: {categories})")
            return

        case_ids = [c.get("case_id") for c in cases]
        reviewer_runs = [c.get("reviewer_run_id") for c in cases]
        receipt_refs = [c.get("receipt_ref") for c in cases]
        if len(set(case_ids)) != 12 or len(set(reviewer_runs)) != 12 or len(set(receipt_refs)) != 12:
            _block("case_id、reviewer_run_id 与 receipt_ref 在 12 案中必须全局唯一")
            return

        for case in cases:
            err = validate_case_evidence(case, receipts_dir)
            if err:
                _block(f"证据校验失败: {err}")
                return
    except Exception as e:
        _block(f"解析案例文件异常: {e}")
        return

    # 完整证据通过后的汇总计算
    all_pkgs = sorted(list({c["package_name"] for c in cases}))
    total_blocking = sum(c.get("blocking_count", 0) for c in cases)
    any_degradation = any(min(c.get("scores", {}).values(), default=0) < 3 for c in cases)
    all_improved = all(c.get("improved", False) for c in cases)

    verdict = "passed_for_experiment" if (total_blocking == 0 and not any_degradation and all_improved) else "failed"
    recommendation = "keep_as_experiment_candidate" if verdict == "passed_for_experiment" else "reject"

    summary = {
        "dataset_version": 1,
        "case_count": len(cases),
        "blind_eval_verdict": verdict,
        "evaluated_packages": all_pkgs,
        "summary": {
            "blocking_issues_count": total_blocking,
            "quality_degradation_detected": any_degradation,
            "target_dimension_improved": all_improved,
            "recommendation": recommendation
        }
    }
    output_path = RESULTS_DIR / "eval_results.json"
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Successfully generated {output_path}")

if __name__ == "__main__":
    main()
