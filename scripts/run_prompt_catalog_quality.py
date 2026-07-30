from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "tasks" / "07_prompt_catalog" / "quality_results"


# 12-case 标准测试套件定义 (4 World, 4 Plot, 4 Writing)
QUALITY_TEST_SUITE = [
    # World (4)
    {"case_id": "world_1", "category": "World", "package_name": "world-rule-system", "input_prompt": "设计一套修仙法则与灵气消耗机制", "model": "gpt-4o", "temperature": 0.3},
    {"case_id": "world_2", "category": "World", "package_name": "world-growth-resource", "input_prompt": "设计单阶修仙突破资源与晋升代价", "model": "gpt-4o", "temperature": 0.3},
    {"case_id": "world_3", "category": "World", "package_name": "world-social-power", "input_prompt": "设计玄幻门阀垄断与阶层剥削结构", "model": "gpt-4o", "temperature": 0.3},
    {"case_id": "world_4", "category": "World", "package_name": "world-system-interaction", "input_prompt": "设计科技与魔法双体系碰撞边界", "model": "gpt-4o", "temperature": 0.3},
    # Plot (4)
    {"case_id": "plot_1", "category": "Plot", "package_name": "story-expectation-design", "input_prompt": "设计卷末迎敌爽点与读者期待钩子", "model": "gpt-4o", "temperature": 0.3},
    {"case_id": "plot_2", "category": "Plot", "package_name": "story-causal-structure", "input_prompt": "设计高潮战役因果链条与伏笔回收", "model": "gpt-4o", "temperature": 0.3},
    {"case_id": "plot_3", "category": "Plot", "package_name": "story-pov-tone-contract", "input_prompt": "设计第三人称限制视角与冷峻基调", "model": "gpt-4o", "temperature": 0.3},
    {"case_id": "plot_4", "category": "Plot", "package_name": "chapter-plan-execution-card", "input_prompt": "生成单章高潮战役章节执行卡", "model": "gpt-4o", "temperature": 0.3},
    # Writing (4)
    {"case_id": "writing_1", "category": "Writing", "package_name": "prose-revision", "input_prompt": "局部重写润色主角生死关头心理活动", "model": "gpt-4o", "temperature": 0.3},
    {"case_id": "writing_2", "category": "Writing", "package_name": "scene-dialogue", "input_prompt": "撰写师徒关头交锋对白", "model": "gpt-4o", "temperature": 0.3},
    {"case_id": "writing_3", "category": "Writing", "package_name": "scene-fight-craft", "input_prompt": "撰写见招拆招的近身搏杀长场景", "model": "gpt-4o", "temperature": 0.3},
    {"case_id": "writing_4", "category": "Writing", "package_name": "mobile-formatting", "input_prompt": "按移动端网文节奏组织高密度动作断句", "model": "gpt-4o", "temperature": 0.3},
]


def run():
    # 检查是否有真实 API 环境变量
    env_keys = ["OPENAI_" + "API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "LLM_API_KEY"]
    has_api = any(bool(os.environ.get(k)) for k in env_keys)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if not has_api:
        summary = {
            "dataset_version": 1,
            "case_count": 0,
            "blind_eval_verdict": "BLOCKED",
            "evaluated_packages": [],
            "status_reason": f"当前环境缺乏真实 LLM API Key ({', '.join(env_keys)} 未设置)，无法执行 12-case 具名测试集质量实验",
            "summary": {
                "blocking_issues_count": 0,
                "quality_degradation_detected": False,
                "target_dimension_improved": False,
                "recommendation": "blocked_due_to_missing_llm_eval_environment"
            }
        }
        output_path = RESULTS_DIR / "eval_results.json"
        output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[run_prompt_catalog_quality] LLM API Environment missing. Standard 12-case suite ({len(QUALITY_TEST_SUITE)} cases configured) safe BLOCKED verdict generated at {output_path}")
        return

    # 若具备真实 API 环境，提示需接入生产 LLM Provider 客户端执行，严禁生成伪造数据
    print(f"[run_prompt_catalog_quality] Real API environment detected ({len(QUALITY_TEST_SUITE)} benchmark cases configured). Live LLM invocation and blind eval client integration required before running full evaluation.")
    raise NotImplementedError("真实 API 评测环境需连接生产 LLM Provider 与盲评 Reviewer 节点，拒绝生成无实际推理的伪造证据")


if __name__ == "__main__":
    run()
