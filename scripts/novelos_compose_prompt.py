"""方法论 prompt 模块化组装器。

按项目 setup 取值与运行时状态（人格库规模、选中原型数）路由条件模块，
把「主干方法论 + 条件模块 + 输入数据区 + 自检汇总」组装成单一注入文本。
路由是确定性的：LLM sub agent 只消费组装结果，主控不再手工拼 prompt。

用法：
  # 阶段 1（查库取 setup + persona）
  python scripts/novelos_compose_prompt.py --asset direction --project project:xxx

  # 方向审查 rubric（同一套路由维度，审查端模块）
  python scripts/novelos_compose_prompt.py --asset direction-review --project project:xxx

  # 作者人格融合（项目未建，路由依据 = 向导 payload + 人格库计数）
  python scripts/novelos_compose_prompt.py --asset fusion --payload <向导JSON路径>

输出组装后的完整注入文本到 stdout。U 型排布：主干（普适方法论）→
输入数据区（可回读原料）→ 条件模块（高信号约束贴近生成点）→ 自检汇总（尾部确认）。
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "novelos-v2.db"
ARCHETYPE_CONFIG = ROOT / "config" / "system_archetypes.json"

# asset → skill 目录（prompt.md 所在目录；modules/ 在同目录下）
ASSET_DIRS = {
    "direction": ROOT / "catalog/skills/planning/story-direction",
    "direction-review": ROOT / "catalog/skills/review/planning-direction-review",
    "fusion": ROOT / "catalog/skills/onboarding/creator-signature-fusion",
}

# 主干自检节标题（匹配行首；该节被剪切到输出尾部，模块附加自检附于其后）
_CHECKLIST_HEADING = re.compile(r"^##\s+交付前自检.*$", re.MULTILINE)
_NEXT_HEADING = re.compile(r"^##\s+", re.MULTILINE)
_MODULE_CHECKLIST_HEADING = re.compile(r"^##\s+附加自检\s*$", re.MULTILINE)


# ---------------------------------------------------------------- when 求值

def _get_field(context: dict[str, Any], path: str) -> Any:
    """按点路径从 context 取值，取不到返回 None。"""
    node: Any = context
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def evaluate_when(rule: dict[str, Any], context: dict[str, Any]) -> bool:
    """求值单个 when 条件；{"all": [...]} 表示与组合。"""
    if "all" in rule:
        return all(evaluate_when(r, context) for r in rule["all"])
    if "field" in rule:
        value = _get_field(context, rule["field"])
        if rule.get("not_null"):
            return value is not None
        if rule.get("is_null"):
            return value is None
        if rule.get("non_empty"):
            return bool(value)
        return value == rule.get("equals")
    if "query" in rule:
        value = context.get(rule["query"])
        op = rule.get("op")
        target = rule.get("value")
        if value is None:
            return False
        if op == "==":
            return value == target
        if op == "!=":
            return value != target
        if op == "<":
            return value < target
        if op == "<=":
            return value <= target
        if op == ">":
            return value > target
        if op == ">=":
            return value >= target
        raise ValueError(f"未知 op: {op}")
    raise ValueError(f"未知 when 规则: {rule}")


# ---------------------------------------------------------------- 模块选择

def load_manifest(skill_dir: Path) -> list[dict[str, Any]]:
    manifest_path = skill_dir / "modules" / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return data["modules"]


def select_modules(skill_dir: Path, context: dict[str, Any]) -> list[tuple[str, str]]:
    """按 manifest 触发条件选取模块，返回 (id, 正文) 列表（manifest 声明序）。"""
    picked: list[tuple[str, str]] = []
    for entry in load_manifest(skill_dir):
        if not evaluate_when(entry.get("when", {}), context):
            continue
        body = (skill_dir / "modules" / entry["file"]).read_text(encoding="utf-8").strip()
        picked.append((entry["id"], body))
    return picked


# ---------------------------------------------------------------- 组装

def _extract_checklist(main_prompt: str) -> tuple[str, str]:
    """把主干「## 交付前自检」节剪切出来，返回 (剩余主干, 自检节)。"""
    match = _CHECKLIST_HEADING.search(main_prompt)
    if match is None:
        return main_prompt, ""
    start = match.start()
    next_h = _NEXT_HEADING.search(main_prompt, match.end())
    end = next_h.start() if next_h else len(main_prompt)
    checklist = main_prompt[start:end].rstrip()
    remainder = (main_prompt[:start] + main_prompt[end:]).rstrip()
    return remainder, checklist


def _extract_module_checklist(module_body: str) -> tuple[str, str]:
    """抽取模块「## 附加自检」节正文，返回 (模块剩余, 自检正文)。"""
    match = _MODULE_CHECKLIST_HEADING.search(module_body)
    if match is None:
        return module_body, ""
    next_h = _NEXT_HEADING.search(module_body, match.end())
    end = next_h.start() if next_h else len(module_body)
    checklist_body = module_body[match.end():end].strip()
    remainder = (module_body[:match.start()] + module_body[end:]).rstrip()
    return remainder, checklist_body


def compose(skill_dir: Path, context: dict[str, Any],
            data_sections: list[tuple[str, str]]) -> str:
    """组装完整注入文本（U 型：主干 → 数据区 → 条件模块 → 自检汇总）。"""
    main_prompt = (skill_dir / "prompt.md").read_text(encoding="utf-8").strip()
    main_body, main_checklist = _extract_checklist(main_prompt)

    parts: list[str] = [main_body]

    if data_sections:
        block = "\n\n".join(f"### {title}\n{body.strip()}" for title, body in data_sections)
        parts.append("## 输入数据（权威源，正文引用以此为准）\n\n" + block)

    extra_checklists: list[str] = []
    for module_id, body in select_modules(skill_dir, context):
        body_rest, checklist = _extract_module_checklist(body)
        parts.append(body_rest)
        if checklist:
            extra_checklists.append(f"（模块 {module_id}）\n{checklist}")

    tail = ["## 交付前自检（普适项 + 条件模块附加项，逐项通过才返回）", ""]
    if main_checklist:
        # 保留原节标题行之后的内容
        tail.append(main_checklist.split("\n", 1)[1].strip())
    for extra in extra_checklists:
        tail.append(extra)
    parts.append("\n\n".join(tail))

    return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------- context 构建

def _persona_library_count(conn: sqlite3.Connection) -> int:
    """用户人格库计数（排除系统原型）。"""
    row = conn.execute(
        "SELECT COUNT(*) FROM creator_profile_versions v "
        "JOIN creator_profiles p ON p.id = v.profile_id "
        "WHERE p.ownership = 'user'"
    ).fetchone()
    return int(row[0])


def _persona_fingerprints(conn: sqlite3.Connection, selected_ids: list[str]) -> list[dict[str, Any]]:
    """跨批次比对基准人格指纹，按量化范围取数：库 ≤10 全量；>10 最近 10 份 + 全部同 parent。"""
    rows = conn.execute(
        "SELECT v.id, v.parent_version_id, v.created_at, "
        "       CAST(r.content AS TEXT) AS sig, p.display_name "
        "FROM creator_profile_versions v "
        "JOIN creator_profiles p ON p.id = v.profile_id "
        "JOIN resources r ON r.id = v.content_resource_id "
        "WHERE p.ownership = 'user' ORDER BY v.created_at DESC"
    ).fetchall()
    if len(rows) <= 10:
        picked = rows
    else:
        picked = rows[:10]
        picked += [r for r in rows[10:] if r[1] in set(selected_ids)]
    fingerprints = []
    for row in picked:
        sig = json.loads(row[3])
        anchors = sig.get("persona", {}).get("anchors", {})
        fingerprints.append({
            "display_name": row[4],
            "parent_version_id": row[1],
            "life_trajectory": anchors.get("five_dimensions", {}).get("life_trajectory", ""),
            "career_track": anchors.get("five_dimensions", {}).get("career_track", ""),
            "trait_profile": anchors.get("trait_profile", []),
            "inner_tension": anchors.get("inner_tension", ""),
            "theme_dominant": anchors.get("theme_orientation", {}).get("dominant", ""),
            "narrative_main_principle": (sig.get("narrative_principles") or [""])[0],
            "forbidden_conveniences": sig.get("forbidden_conveniences", []),
        })
    return fingerprints


def build_context_direction(conn: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT metadata_json FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        raise SystemExit(f"项目不存在: {project_id}")
    metadata = json.loads(row[0])
    setup = metadata.get("setup", {})
    return {"setup": setup}


def build_context_fusion(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    setup = payload.get("project_setup") or payload.get("setup") or {}
    selected = payload.get("selected_archetypes", [])
    return {
        "setup": setup,
        "selected_count": len(selected),
        "persona_library_count": _persona_library_count(conn),
    }


def _direction_data_sections(conn: sqlite3.Connection, project_id: str) -> list[tuple[str, str]]:
    setup_row = conn.execute(
        "SELECT metadata_json FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if setup_row is None:
        raise SystemExit(f"项目不存在: {project_id}")
    setup = json.loads(setup_row[0]).get("setup", {})

    sig_row = conn.execute(
        "SELECT CAST(r.content AS TEXT), v.subject_hash FROM project_creator_bindings b "
        "JOIN creator_profile_versions v ON v.id = b.profile_version_id "
        "JOIN resources r ON r.id = v.content_resource_id "
        "WHERE b.project_id = ?", (project_id,)
    ).fetchone()
    sections: list[tuple[str, str]] = [
        ("project_setup v2 快照（硬输入）", json.dumps(setup, ensure_ascii=False, indent=1)),
    ]
    if sig_row is not None:
        sections.append((
            "创作者人格签名（第一因，persona 全文）",
            f"subject_hash: {sig_row[1]}\n" + sig_row[0],
        ))
    else:
        sections.append(("创作者人格签名", "（未查到项目绑定——停下来上报，禁止无签名生成方向）"))
    return sections


def _fusion_data_sections(conn: sqlite3.Connection, payload: dict[str, Any]) -> list[tuple[str, str]]:
    setup = payload.get("project_setup") or payload.get("setup") or {}
    selected = payload.get("selected_archetypes", [])
    selected_ids = [a.get("profile_version_id", "") for a in selected]
    hints = payload.get("user_persona_hints") or {}

    archetypes = json.loads(ARCHETYPE_CONFIG.read_text(encoding="utf-8"))
    by_key = {f"creator-profile-version:{a['id']}:{a['revision']}": a for a in archetypes}
    chosen = [by_key[i] for i in selected_ids if i in by_key]
    missing = [i for i in selected_ids if i not in by_key]
    if missing:
        raise SystemExit(f"选中原型不在 config/system_archetypes.json: {missing}")

    roster = "\n".join(f"- {a['id']}：{a['display_name']}" for a in archetypes)
    sections = [
        ("selected_archetypes（选中条目全文——parent 判定与气质溯因只用这些）",
         json.dumps(chosen, ensure_ascii=False, indent=1)),
        ("系统原型全库一行式清单（仅作语境：库里还有什么；禁止从清单外原型取材）", roster),
        ("user_persona_hints（人格素材）", json.dumps(hints, ensure_ascii=False, indent=1)),
        ("project_setup v2 快照", json.dumps(setup, ensure_ascii=False, indent=1)),
    ]
    fingerprints = _persona_fingerprints(conn, selected_ids)
    if fingerprints:
        sections.append((
            "跨批次比对基准人格（existing_persona_fingerprints，按量化范围取数）",
            json.dumps(fingerprints, ensure_ascii=False, indent=1),
        ))
    else:
        sections.append(("跨批次比对基准人格", "（人格库为空——首个人格，按空库模块执行）"))
    return sections


# ---------------------------------------------------------------- CLI

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--asset", required=True, choices=sorted(ASSET_DIRS))
    parser.add_argument("--project", help="项目 ID（direction / direction-review 模式）")
    parser.add_argument("--payload", help="向导 JSON 路径（fusion 模式）")
    args = parser.parse_args()

    skill_dir = ASSET_DIRS[args.asset]
    conn = sqlite3.connect(DB_PATH)
    try:
        if args.asset in ("direction", "direction-review"):
            if not args.project:
                parser.error(f"--asset {args.asset} 需要 --project")
            context = build_context_direction(conn, args.project)
            data = _direction_data_sections(conn, args.project)
        else:
            if not args.payload:
                parser.error("--asset fusion 需要 --payload")
            payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
            context = build_context_fusion(conn, payload)
            data = _fusion_data_sections(conn, payload)
    finally:
        conn.close()

    sys.stdout.write(compose(skill_dir, context, data) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
