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
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "novelos-v2.db"
ARCHETYPE_CONFIG = ROOT / "config" / "system_archetypes.json"
MANIFEST_SCHEMA = ROOT / "config" / "schemas" / "compose-manifest.schema.json"
CREATE_REQUEST_SCHEMA = ROOT / "config" / "schemas" / "project-create-request.schema.json"

# asset → skill 目录（prompt.md 所在目录；modules/ 在同目录下）。
# 除 fusion（--payload 向导载荷域）外全部为项目域（--project）；
# 审查资产另需 --subject（被审对象 planning_asset ID）。
ASSET_DIRS = {
    "direction": ROOT / "catalog/skills/planning/story-direction",
    "direction-review": ROOT / "catalog/skills/review/planning-direction-review",
    "fusion": ROOT / "catalog/skills/onboarding/creator-signature-fusion",
    "architecture": ROOT / "catalog/skills/planning/story-architecture",
    "architecture-review": ROOT / "catalog/skills/review/planning-architecture-review",
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

def load_manifest(skill_dir: Path) -> dict[str, Any]:
    """加载并校验 manifest（compose-manifest schema v2），返回完整声明。

    结构：modules（when 路由）+ 可选 data_slots / divergence / decision_scope。
    """
    manifest_path = skill_dir / "modules" / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    import jsonschema

    jsonschema.validate(data, schema)
    return data


def select_modules(skill_dir: Path, context: dict[str, Any]) -> list[tuple[str, str]]:
    """按 manifest 触发条件选取模块，返回 (id, 正文) 列表（manifest 声明序）。"""
    picked: list[tuple[str, str]] = []
    for entry in load_manifest(skill_dir)["modules"]:
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


def resolve_proposal(skill_dir: Path, proposal: dict[str, Any]) -> list[tuple[str, str]]:
    """校验并解析模型提议模块：id 必须在 manifest 注册（结构性门槛），返回 (id, 正文)。

    提议是模型路由智能进入系统的唯一形态——数据工件，可校验、进日志；
    与规则命中重复的项由 compose 去重。正文永远逐字拼接，不经模型改写。
    """
    entries = {m["id"]: m for m in load_manifest(skill_dir)["modules"]}
    picked: list[tuple[str, str]] = []
    for item in proposal.get("modules", []):
        mid = item.get("id")
        if mid not in entries:
            raise SystemExit(f"提议引用未注册模块: {mid!r}（{skill_dir.name}）——manifest 未注册即拒绝")
        body = (skill_dir / "modules" / entries[mid]["file"]).read_text(encoding="utf-8").strip()
        picked.append((mid, body))
    return picked


def compose(skill_dir: Path, context: dict[str, Any],
            data_sections: list[tuple[str, str]],
            proposal_modules: list[tuple[str, str]] | None = None) -> str:
    """组装完整注入文本（U 型：主干 → 数据区 → 条件模块 → 自检汇总）。"""
    main_prompt = (skill_dir / "prompt.md").read_text(encoding="utf-8").strip()
    main_body, main_checklist = _extract_checklist(main_prompt)

    parts: list[str] = [main_body]

    if data_sections:
        block = "\n\n".join(f"### {title}\n{body.strip()}" for title, body in data_sections)
        parts.append("## 输入数据（权威源，正文引用以此为准）\n\n" + block)

    picked = select_modules(skill_dir, context)
    if proposal_modules:
        rule_ids = {mid for mid, _ in picked}
        picked = picked + [(mid, body) for mid, body in proposal_modules if mid not in rule_ids]

    extra_checklists: list[str] = []
    for module_id, body in picked:
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


def _persona_fingerprints_query(conn: sqlite3.Connection, selected_ids: list[str]) -> list[dict[str, Any]]:
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
    selected = payload["setup"]["creator"]["selected_archetypes"]
    return {
        "setup": payload["setup"],
        "selected_count": len(selected),
        "persona_library_count": _persona_library_count(conn),
    }


# ---------------------------------------------------------------- 槽位注册表
# slot id → resolver(conn, project_id, payload) -> (title, body)。
# 项目域槽位（direction 系）用 project_id；融合域槽位（fusion）用 payload（已过
# project-create-request schema 校验，selected_archetypes 等在 setup.creator 内）。

def _load_archetypes() -> list[dict[str, Any]]:
    return json.loads(ARCHETYPE_CONFIG.read_text(encoding="utf-8"))


def _slot_project_setup(conn: sqlite3.Connection, project_id: str | None,
                        payload: dict[str, Any] | None,
                        subject_id: str | None = None) -> tuple[str, str]:
    if project_id is not None:
        row = conn.execute(
            "SELECT metadata_json FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if row is None:
            raise SystemExit(f"项目不存在: {project_id}")
        setup = json.loads(row[0]).get("setup", {})
        return ("project_setup v2 快照（硬输入）", json.dumps(setup, ensure_ascii=False, indent=1))
    return ("project_setup v2 快照", json.dumps(payload["setup"], ensure_ascii=False, indent=1))


def _slot_persona_full(conn: sqlite3.Connection, project_id: str | None,
                       payload: dict[str, Any] | None,
                       subject_id: str | None = None) -> tuple[str, str]:
    row = conn.execute(
        "SELECT CAST(r.content AS TEXT), v.subject_hash FROM project_creator_bindings b "
        "JOIN creator_profile_versions v ON v.id = b.profile_version_id "
        "JOIN resources r ON r.id = v.content_resource_id "
        "WHERE b.project_id = ?",
        (project_id,),
    ).fetchone()
    if row is not None:
        return ("创作者人格签名（第一因，persona 全文）",
                f"subject_hash: {row[1]}\n" + row[0])
    return ("创作者人格签名", "（未查到项目绑定——停下来上报，禁止无签名生成方向）")


def _fusion_selected_ids(payload: dict[str, Any]) -> list[str]:
    return [a["profile_version_id"] for a in payload["setup"]["creator"]["selected_archetypes"]]


def _slot_selected_archetypes(conn: sqlite3.Connection, project_id: str | None,
                              payload: dict[str, Any] | None,
                              subject_id: str | None = None) -> tuple[str, str]:
    archetypes = _load_archetypes()
    by_key = {f"creator-profile-version:{a['id']}:{a['revision']}": a for a in archetypes}
    selected_ids = _fusion_selected_ids(payload)
    chosen = [by_key[i] for i in selected_ids if i in by_key]
    missing = [i for i in selected_ids if i not in by_key]
    if missing:
        raise SystemExit(f"选中原型不在 config/system_archetypes.json: {missing}")
    return ("selected_archetypes（选中条目全文——parent 判定与气质溯因只用这些）",
            json.dumps(chosen, ensure_ascii=False, indent=1))


def _slot_archetype_roster(conn: sqlite3.Connection, project_id: str | None,
                           payload: dict[str, Any] | None,
                           subject_id: str | None = None) -> tuple[str, str]:
    roster = "\n".join(f"- {a['id']}：{a['display_name']}" for a in _load_archetypes())
    return ("系统原型全库一行式清单（仅作语境：库里还有什么；禁止从清单外原型取材）", roster)


def _slot_persona_hints(conn: sqlite3.Connection, project_id: str | None,
                        payload: dict[str, Any] | None,
                        subject_id: str | None = None) -> tuple[str, str]:
    hints = payload["setup"]["creator"]["user_persona_hints"]
    return ("user_persona_hints（人格素材）", json.dumps(hints, ensure_ascii=False, indent=1))


def _slot_persona_fingerprints(conn: sqlite3.Connection, project_id: str | None,
                               payload: dict[str, Any] | None,
                               subject_id: str | None = None) -> tuple[str, str]:
    fingerprints = _persona_fingerprints_query(conn, _fusion_selected_ids(payload))
    if fingerprints:
        return ("跨批次比对基准人格（existing_persona_fingerprints，按量化范围取数）",
                json.dumps(fingerprints, ensure_ascii=False, indent=1))
    return ("跨批次比对基准人格", "（人格库为空——首个人格，按空库模块执行）")


def _slot_subject(conn: sqlite3.Connection, project_id: str | None,
                  payload: dict[str, Any] | None,
                  subject_id: str | None) -> tuple[str, str]:
    """被审对象全文（candidate/locked 资产正文 + metadata）——审查组装的必需槽。"""
    if subject_id is None:
        raise SystemExit("该资产声明 subject 槽位，CLI 需要 --subject <planning_asset_id>")
    row = conn.execute(
        "SELECT pa.asset_type, pa.scope_ref, pa.revision, pa.status, "
        "       CAST(r.content AS TEXT) AS body, pa.metadata_json "
        "FROM planning_assets pa JOIN resources r ON r.id = pa.content_resource_id "
        "WHERE pa.id = ?",
        (subject_id,),
    ).fetchone()
    if row is None:
        raise SystemExit(f"被审对象不存在: {subject_id}")
    header = (f"asset_type: {row[0]} | scope: {row[1]} | revision: {row[2]} | "
              f"status: {row[3]}")
    meta = row[5] or "{}"
    return (f"被审对象全文（subject: {subject_id}）",
            f"{header}\n\n{row[4]}\n\n--- metadata ---\n{meta}")


def _slot_upstream(conn: sqlite3.Connection, asset_type: str,
                   project_id: str | None) -> list[tuple[str, str]]:
    """locked 上游资产原文，按 scope 分节（每 scope 取最高 revision）。缺失即停。"""
    rows = conn.execute(
        "SELECT pa.scope_ref, pa.revision, CAST(r.content AS TEXT) AS body "
        "FROM planning_assets pa JOIN resources r ON r.id = pa.content_resource_id "
        "WHERE pa.project_id = ? AND pa.asset_type = ? AND pa.status = 'locked' "
        "ORDER BY pa.scope_ref, pa.revision",
        (project_id, asset_type),
    ).fetchall()
    if not rows:
        raise SystemExit(f"无 locked 上游 {asset_type}——上游缺失即停止，禁止无上游生成")
    latest: dict[str, tuple[int, str]] = {}
    for scope, revision, body in rows:
        if scope not in latest or revision > latest[scope][0]:
            latest[scope] = (revision, body)
    return [(f"上游 {asset_type}（scope: {scope}，locked rev {rev}，原文）", body)
            for scope, (rev, body) in sorted(latest.items())]


SLOT_REGISTRY: dict[str, Any] = {
    "project_setup": _slot_project_setup,
    "persona_full": _slot_persona_full,
    "selected_archetypes": _slot_selected_archetypes,
    "archetype_roster": _slot_archetype_roster,
    "persona_hints": _slot_persona_hints,
    "persona_fingerprints": _slot_persona_fingerprints,
    "subject": _slot_subject,
}


def resolve_slots(conn: sqlite3.Connection, skill_dir: Path, *,
                  project_id: str | None = None,
                  payload: dict[str, Any] | None = None,
                  subject_id: str | None = None) -> list[tuple[str, str]]:
    """按 manifest 的 data_slots 声明顺序解析注入槽位。未注册槽位即报错。

    upstream:<asset_type> 为前缀族槽位，展开为多节（每 scope 一节）。
    """
    manifest = load_manifest(skill_dir)
    sections: list[tuple[str, str]] = []
    for slot in manifest.get("data_slots", []):
        if slot.startswith("upstream:"):
            sections.extend(_slot_upstream(conn, slot[len("upstream:"):], project_id))
            continue
        resolver = SLOT_REGISTRY.get(slot)
        if resolver is None:
            raise SystemExit(f"未注册的槽位: {slot}（{skill_dir.name}）")
        sections.append(resolver(conn, project_id, payload, subject_id))
    return sections


def validate_fusion_payload(payload: dict[str, Any]) -> None:
    """向导载荷过 project-create-request schema——与 create 脚本同一契约，防两处解析漂移。"""
    import jsonschema

    schema = json.loads(CREATE_REQUEST_SCHEMA.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(payload, schema)
    except jsonschema.ValidationError as exc:
        raise SystemExit(f"向导载荷不符合 project-create-request schema: {exc.message}")


# ---------------------------------------------------------------- 组装日志
# 每次组装落盘完整注入文本 + 追加 index.jsonl（content_hash / 命中模块 / 声明槽位 /
# 发散档位 / 决策权限）——「这次生成看到了什么」可回查，精细 stale 与审查取证的地基。

COMPOSITIONS_DIR = ROOT / "data" / "compositions"


def content_hash(text: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_composition_log(log_dir: Path, skill_dir: Path, asset: str, scope: str,
                          text: str, context: dict[str, Any],
                          proposal: dict[str, Any] | None = None) -> Path:
    """把一次组装的产物与路由事实记入日志目录，返回产物文件路径。"""
    manifest = load_manifest(skill_dir)
    module_ids = [mid for mid, _ in select_modules(skill_dir, context)]
    proposal_modules = []
    if proposal:
        for item in proposal.get("modules", []):
            mid = item["id"]
            proposal_modules.append({"id": mid, "reason": item.get("reason", ""),
                                     "merged": mid in module_ids})
            if mid not in module_ids:
                module_ids.append(mid)
    digest = content_hash(text)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    safe_scope = re.sub(r"[^A-Za-z0-9._-]", "_", scope)
    rel = Path(safe_scope) / asset / f"{ts}-{digest[7:19]}.md"
    dest = log_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    entry = {
        "ts": ts,
        "asset": asset,
        "scope": scope,
        "content_hash": digest,
        "modules": module_ids,
        "data_slots": manifest.get("data_slots", []),
        "divergence": manifest.get("divergence"),
        "decision_scope": manifest.get("decision_scope"),
        "proposal": proposal_modules,
        "file": str(rel),
    }
    index = log_dir / "index.jsonl"
    with index.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return dest


# ---------------------------------------------------------------- CLI

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--asset", required=True, choices=sorted(ASSET_DIRS))
    parser.add_argument("--project", help="项目 ID（除 fusion 外的全部资产）")
    parser.add_argument("--subject", help="被审对象 planning_asset ID（声明 subject 槽的审查资产必需）")
    parser.add_argument("--payload", help="向导 JSON 路径（fusion 模式）")
    parser.add_argument("--log-dir", default=str(COMPOSITIONS_DIR),
                        help="组装日志目录（default: data/compositions/）")
    parser.add_argument("--no-log", action="store_true", help="不写组装日志")
    parser.add_argument("--proposal", help="模型提议路由 JSON 路径（{modules:[{id,reason}]}），语义条件的第二路由通道")
    args = parser.parse_args()

    skill_dir = ASSET_DIRS[args.asset]
    conn = sqlite3.connect(DB_PATH)
    try:
        if args.asset == "fusion":
            if not args.payload:
                parser.error("--asset fusion 需要 --payload")
            payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
            validate_fusion_payload(payload)
            context = build_context_fusion(conn, payload)
            data = resolve_slots(conn, skill_dir, payload=payload)
        else:
            if not args.project:
                parser.error(f"--asset {args.asset} 需要 --project")
            context = build_context_direction(conn, args.project)
            data = resolve_slots(conn, skill_dir, project_id=args.project,
                                 subject_id=args.subject)
    finally:
        conn.close()

    proposal = None
    proposal_modules: list[tuple[str, str]] = []
    if args.proposal:
        proposal = json.loads(Path(args.proposal).read_text(encoding="utf-8"))
        proposal_modules = resolve_proposal(skill_dir, proposal)

    output = compose(skill_dir, context, data, proposal_modules)
    if not args.no_log:
        scope = args.project or "wizard"
        logged = write_composition_log(Path(args.log_dir), skill_dir, args.asset,
                                       scope, output, context, proposal=proposal)
        print(f"[compose] logged: {logged}", file=sys.stderr)
    sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
