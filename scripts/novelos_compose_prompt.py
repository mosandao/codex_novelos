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
    "kernel-fusion": ROOT / "catalog/skills/onboarding/author-kernel-fusion",
    "architecture": ROOT / "catalog/skills/planning/story-architecture",
    "architecture-review": ROOT / "catalog/skills/review/planning-architecture-review",
    "strategy": ROOT / "catalog/skills/planning/story-strategy",
    "strategy-review": ROOT / "catalog/skills/review/planning-strategy-review",
    "world-contract": ROOT / "catalog/skills/planning/world-contract",
    "world-contract-review": ROOT / "catalog/skills/review/planning-world-contract-review",
    "character-contract": ROOT / "catalog/skills/planning/character-contract",
    "character-contract-review": ROOT / "catalog/skills/review/planning-character-contract-review",
    "story-arc": ROOT / "catalog/skills/planning/story-arc",
    "story-arc-review": ROOT / "catalog/skills/review/planning-story-arc-review",
    "volume-outline": ROOT / "catalog/skills/planning/volume-outline",
    "volume-outline-review": ROOT / "catalog/skills/review/planning-volume-outline-review",
    "chapter-plan": ROOT / "catalog/skills/planning/chapter-plan-execution-card",
    "chapter-plan-review": ROOT / "catalog/skills/review/planning-chapter-plan-review",
    "chapter-draft": ROOT / "catalog/skills/writing/chapter-draft-generation",
    "prose-review": ROOT / "catalog/skills/review/prose-quality-review",
    "continuity-extraction": ROOT / "catalog/skills/continuity/continuity-candidate-extraction",
    "continuity-review": ROOT / "catalog/skills/review/continuity-quality-review",
    "cross-consistency-review": ROOT / "catalog/skills/review/planning-cross-consistency-review",
    "entity-authority-review": ROOT / "catalog/skills/review/entity-authority-review",
    "planning-quality-review": ROOT / "catalog/skills/review/planning-quality-review",
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
    kernel_row = conn.execute(
        "SELECT kernel_version_id FROM project_creator_bindings WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    return {"setup": setup, "has_kernel": bool(kernel_row and kernel_row[0])}


def build_context_fusion(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "setup": payload["setup"],
        "persona_library_count": _persona_library_count(conn),
    }


def build_context_kernel_fusion(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    mode = "revise" if payload.get("request_type") == "novelos.kernel.revise.v1" else "create"
    return {
        "setup": payload.get("setup", {}),
        "mode": mode,
        "persona_library_count": _persona_library_count(conn),
    }


def validate_kernel_fusion_payload(payload: dict[str, Any]) -> None:
    """内核融合载荷结构门：create = v3 向导载荷；revise = novelos.kernel.revise.v1 信封。

    create 的完整 schema 校验在落库脚本（novelos_create_project.py）入口执行；
    组装侧只锁 request_type 与内核素材路径，保证槽位可解析。
    """
    request_type = payload.get("request_type")
    if request_type == "novelos.kernel.revise.v1":
        base = payload.get("base_version")
        if not isinstance(base, str) or not base:
            raise SystemExit("revise 载荷缺 base_version（格式权威在 kernel-candidate schema，存在性由库反查）")
        return
    if request_type == "novelos.project.create.v3":
        kernel = (payload.get("setup") or {}).get("author_kernel")
        if not isinstance(kernel, dict):
            raise SystemExit("create 载荷缺 setup.author_kernel（内核取代原型的 v3 结构）")
        return
    raise SystemExit(f"kernel-fusion 载荷 request_type 不认识: {request_type!r}")


# ---------------------------------------------------------------- 槽位注册表
# slot id → resolver(conn, project_id, payload) -> (title, body)。
# 项目域槽位（direction 系）用 project_id；融合域槽位（fusion）用 payload（已过
# project-create-request schema（v3，author_kernel 结构）校验）。

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
    setup = (payload or {}).get("setup")
    if setup is None:
        return ("project_setup v2 快照", "（无 setup——内核修订独立于项目语境时合法，题材词禁入内核）")
    return ("project_setup v2 快照", json.dumps(setup, ensure_ascii=False, indent=1))


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


def _slot_kernel_full(conn: sqlite3.Connection, project_id: str | None,
                      payload: dict[str, Any] | None,
                      subject_id: str | None = None) -> tuple[str, str]:
    """内核全文：项目域走绑定 kernel_version_id；融合域走 payload.author_kernel（select 形态）。

    无内核来源（v2 原型直连的旧项目 / 未缝合载荷）给占位不阻断——v2 分身自带
    完整人格七字段，按无内核路径执行。
    """
    version_id: str | None = None
    if project_id is not None:
        row0 = conn.execute(
            "SELECT kernel_version_id FROM project_creator_bindings WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        version_id = row0[0] if row0 else None
    elif payload:
        ak = (payload.get("setup") or {}).get("author_kernel") or {}
        if ak.get("mode") == "select":
            version_id = ak.get("kernel_version_id")
    if version_id is None:
        return ("作者内核（kernel 全文）",
                "（无内核来源——v2 原型直连项目或未缝合载荷；分身自带完整人格，按无内核路径执行）")
    row = conn.execute(
        "SELECT CAST(r.content AS TEXT), v.subject_hash FROM creator_profile_versions v "
        "JOIN resources r ON r.id = v.content_resource_id WHERE v.id = ?",
        (version_id,),
    ).fetchone()
    if row is None:
        raise SystemExit(f"内核版本库中不存在: {version_id}")
    return ("作者内核（第一因的根，kernel 全文——内核层继承不变，表达层按本书适配）",
            f"subject_hash: {row[1]}\n" + row[0])


def _slot_archetype_roster(conn: sqlite3.Connection, project_id: str | None,
                           payload: dict[str, Any] | None,
                           subject_id: str | None = None) -> tuple[str, str]:
    roster = "\n".join(f"- {a['id']}：{a['display_name']}" for a in _load_archetypes())
    return ("系统原型全库一行式清单（仅作语境：库里还有什么；禁止从清单外原型取材）", roster)


def _slot_kernel_hints(conn: sqlite3.Connection, project_id: str | None,
                       payload: dict[str, Any] | None,
                       subject_id: str | None = None) -> tuple[str, str]:
    """内核素材：create 取 setup.author_kernel.kernel_hints；revise 取顶层 kernel_hints。"""
    hints: Any = None
    if payload.get("request_type") == "novelos.kernel.revise.v1":
        hints = payload.get("kernel_hints")
    else:
        hints = (payload.get("setup") or {}).get("author_kernel", {}).get("kernel_hints")
    if hints:
        return ("kernel_hints（内核素材——间接养料，不是照抄的答案）",
                json.dumps(hints, ensure_ascii=False, indent=1))
    return ("kernel_hints（内核素材）", "（无内核素材——完全由生活基底反推，rationale 须标注反推字段）")


def _slot_kernel_subject(conn: sqlite3.Connection, project_id: str | None,
                         payload: dict[str, Any] | None,
                         subject_id: str | None = None) -> tuple[str, str]:
    """修订基底：按 payload.base_version 直读内核版本全文（内核独立于项目存在）。"""
    base = payload.get("base_version") if payload else None
    if not base:
        return ("kernel_subject（修订基底内核全文）", "（新建内核——无基底版本，按 mode-create 模块执行）")
    row = conn.execute(
        "SELECT CAST(r.content AS TEXT), v.subject_hash FROM creator_profile_versions v "
        "JOIN resources r ON r.id = v.content_resource_id WHERE v.id = ?",
        (base,),
    ).fetchone()
    if row is None:
        raise SystemExit(f"base_version 在库中不存在: {base}")
    return ("kernel_subject（修订基底内核全文——演化的起点，不整体重写）",
            f"subject_hash: {row[1]}\n" + row[0])


def _slot_persona_fingerprints(conn: sqlite3.Connection, project_id: str | None,
                               payload: dict[str, Any] | None,
                               subject_id: str | None = None) -> tuple[str, str]:
    fingerprints = _persona_fingerprints_query(conn, [])
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
    if row is not None:
        header = (f"asset_type: {row[0]} | scope: {row[1]} | revision: {row[2]} | "
                  f"status: {row[3]}")
        meta = row[5] or "{}"
        return (f"被审对象全文（subject: {subject_id}）",
                f"{header}\n\n{row[4]}\n\n--- metadata ---\n{meta}")
    # 章节正文（chapter:xxx）——prose 审查的对象
    row = conn.execute(
        "SELECT c.number, c.title, c.status, c.version, CAST(r.content AS TEXT) AS body, "
        "       c.metadata_json FROM chapters c JOIN resources r ON r.id = c.content_resource_id "
        "WHERE c.id = ?",
        (subject_id,),
    ).fetchone()
    if row is not None:
        header = f"chapter no.{row[0]}《{row[1]}》 | status: {row[2]} | version: {row[3]}"
        return (f"被审章节正文（subject: {subject_id}）",
                f"{header}\n\n{row[4]}\n\n--- metadata ---\n{row[5] or '{}'}")
    raise SystemExit(f"被审对象不存在（planning_assets 与 chapters 均未命中）: {subject_id}")


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


def _slot_genre_pack(conn: sqlite3.Connection, project_id: str | None,
                     payload: dict[str, Any] | None,
                     subject_id: str | None = None,
                     context: dict[str, Any] | None = None) -> tuple[str, str]:
    """题材信息包升为一等节：setup.genre_profile 有则展开；无则显式声明缺位（尊重项目选择，不回填）。"""
    setup = (context or {}).get("setup", {})
    pack = setup.get("genre_profile")
    if pack:
        return ("题材信息包（genre_profile，硬输入）",
                json.dumps(pack, ensure_ascii=False, indent=1))
    return ("题材信息包", "（本项目未声明 genre_profile——按 genre-null 模块执行，不从 config 回填）")


def _slot_canon_minimal(conn: sqlite3.Connection, project_id: str | None,
                        subject_id: str | None = None) -> list[tuple[str, str]]:
    """canon 最小集：六类账本近端条目 + 近期已接受章节摘要（SQL 与 sql-reference.md 模板同源）。

    账本描述统一存 resources（description_resource_id / state_resource_id 引用），
    列名以 db/migrations/schema.sql 为准；查询失败显式降级打 stderr，禁止静默吞错。
    """
    if project_id is None:
        raise SystemExit("canon_minimal 槽位需要 --project")
    queries = [
        ("facts（近 12 条）",
         "SELECT cf.fact_type, cf.subject, CAST(r.content AS TEXT) AS description "
         "FROM chapter_facts cf JOIN resources r ON r.id = cf.description_resource_id "
         "WHERE cf.project_id = ? AND cf.status = 'accepted' ORDER BY cf.rowid DESC LIMIT 12"),
        ("narrative_promises（未决近 8 条）",
         "SELECT np.promise_key, CAST(r.content AS TEXT) AS description, np.status "
         "FROM narrative_promises np JOIN resources r ON r.id = np.description_resource_id "
         "WHERE np.project_id = ? AND np.status = 'open' ORDER BY np.rowid DESC LIMIT 8"),
        ("expectations（近 6 条）",
         "SELECT el.expectation_key, CAST(r.content AS TEXT) AS description, el.status "
         "FROM expectation_ledgers el JOIN resources r ON r.id = el.description_resource_id "
         "WHERE el.project_id = ? ORDER BY el.rowid DESC LIMIT 6"),
        ("relationship_states（近 8 条）",
         "SELECT rs.subject_ref, rs.object_ref, CAST(r.content AS TEXT) AS state "
         "FROM relationship_states rs JOIN resources r ON r.id = rs.state_resource_id "
         "WHERE rs.project_id = ? ORDER BY rs.rowid DESC LIMIT 8"),
        ("arc_states（近 4 条）",
         "SELECT a.arc_ref, CAST(r.content AS TEXT) AS state "
         "FROM arc_states a JOIN resources r ON r.id = a.state_resource_id "
         "WHERE a.project_id = ? ORDER BY a.rowid DESC LIMIT 4"),
        ("近期已接受章节（近 5 章）",
         "SELECT c.number, c.title, c.summary FROM chapters c "
         "JOIN volumes v ON v.id = c.volume_id JOIN books b ON b.id = v.book_id "
         "WHERE b.project_id = ? AND c.status = 'accepted' "
         "ORDER BY c.updated_at DESC LIMIT 5"),
    ]
    sections: list[tuple[str, str]] = []
    for title, sql in queries:
        params = (project_id,) if "?" in sql else ()
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            print(f"[canon_minimal] 账本查询降级（{title}）：{exc}", file=sys.stderr)
            rows = []
        body = "\n".join(json.dumps(list(r), ensure_ascii=False) for r in rows) or "（空）"
        sections.append((f"canon 最小集 · {title}", body))
    return sections


def _slot_review_feedback(feedback: dict[str, Any] | None) -> tuple[str, str] | None:
    """上轮审查回执：仅 blocking + warning 全量注入（note 不进）——修复重组装的受控重试通道。"""
    if feedback is None:
        return None
    findings = [f for f in feedback.get("findings", [])
                if f.get("severity") in ("blocking", "warning")]
    lines = [f"[{f.get('severity')}] {f.get('message', '')}"
             + (f"（证据: {f.get('evidence_refs')}）" if f.get("evidence_refs") else "")
             for f in findings]
    return ("上轮审查回执（review_feedback——本轮修复必须逐条回应，未解决项将再次 blocking）",
            f"verdict: {feedback.get('verdict', '?')}\n" + "\n".join(lines))


SLOT_REGISTRY: dict[str, Any] = {
    "project_setup": _slot_project_setup,
    "persona_full": _slot_persona_full,
    "archetype_roster": _slot_archetype_roster,
    "persona_fingerprints": _slot_persona_fingerprints,
    "kernel_hints": _slot_kernel_hints,
    "kernel_subject": _slot_kernel_subject,
    "kernel_full": _slot_kernel_full,
    "subject": _slot_subject,
    "genre_pack": _slot_genre_pack,
}


def resolve_slots(conn: sqlite3.Connection, skill_dir: Path, *,
                  project_id: str | None = None,
                  payload: dict[str, Any] | None = None,
                  subject_id: str | None = None,
                  context: dict[str, Any] | None = None,
                  review_feedback: dict[str, Any] | None = None) -> list[tuple[str, str]]:
    """按 manifest 的 data_slots 声明顺序解析注入槽位。未注册槽位即报错。

    upstream:<asset_type> 为前缀族槽位，展开为多节（每 scope 一节）；
    canon_minimal 同为多节；review_feedback 仅在 CLI 提供回执时注入；
    craft_refs 为 manifest 顶层声明，craft 方法卡逐字注入（数字阈值唯一权威源）。
    """
    manifest = load_manifest(skill_dir)
    sections: list[tuple[str, str]] = []
    for slot in manifest.get("data_slots", []):
        if slot.startswith("upstream:"):
            sections.extend(_slot_upstream(conn, slot[len("upstream:"):], project_id))
            continue
        if slot == "canon_minimal":
            sections.extend(_slot_canon_minimal(conn, project_id, subject_id))
            continue
        if slot == "review_feedback":
            feedback = _slot_review_feedback(review_feedback)
            if feedback is not None:
                sections.append(feedback)
            continue
        resolver = SLOT_REGISTRY.get(slot)
        if resolver is None:
            raise SystemExit(f"未注册的槽位: {slot}（{skill_dir.name}）")
        sections.append(resolver(conn, project_id, payload, subject_id, context)
                        if slot == "genre_pack"
                        else resolver(conn, project_id, payload, subject_id))
    for craft in manifest.get("craft_refs", []):
        craft_path = ROOT / "catalog/skills/craft" / craft / "prompt.md"
        if not craft_path.exists():
            raise SystemExit(f"craft_refs 引用不存在的 craft 卡: {craft}（{skill_dir.name}）")
        sections.append((f"craft 方法卡（{craft}，逐字注入——数字阈值唯一权威源）",
                         craft_path.read_text(encoding="utf-8").strip()))
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
                          proposal: dict[str, Any] | None = None,
                          review_round: int | None = None) -> Path:
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
        "review_round": review_round,
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
    parser.add_argument("--review-feedback", help="上轮审查回执 JSON 路径（修复重组装：blocking+warning 注入 review_feedback 槽）")
    parser.add_argument("--round", type=int, default=None,
                        help="审查-修复循环轮次号（记入组装日志；≥3 时主控须核对升级条件）")
    args = parser.parse_args()

    skill_dir = ASSET_DIRS[args.asset]
    conn = sqlite3.connect(DB_PATH)
    try:
        if args.asset in ("fusion", "kernel-fusion"):
            if not args.payload:
                parser.error(f"--asset {args.asset} 需要 --payload")
            payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
            if args.asset == "fusion":
                validate_fusion_payload(payload)
                context = build_context_fusion(conn, payload)
            else:
                validate_kernel_fusion_payload(payload)
                context = build_context_kernel_fusion(conn, payload)
            data = resolve_slots(conn, skill_dir, payload=payload)
        else:
            if not args.project:
                parser.error(f"--asset {args.asset} 需要 --project")
            context = build_context_direction(conn, args.project)
            feedback = None
            if args.review_feedback:
                feedback = json.loads(Path(args.review_feedback).read_text(encoding="utf-8"))
            data = resolve_slots(conn, skill_dir, project_id=args.project,
                                 subject_id=args.subject, context=context,
                                 review_feedback=feedback)
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
                                       scope, output, context, proposal=proposal,
                                       review_round=args.round)
        print(f"[compose] logged: {logged}", file=sys.stderr)
    sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
