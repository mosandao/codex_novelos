#!/usr/bin/env python
"""项目创建固化管线：入口校验 → 原型反查 → 融合候选校验门 → 单事务落库。

向导产出的 `novelos.project.create.v2` JSON 不再靠主控眼审，本脚本一次完成：

1. **入口校验**（--payload，必跑）：jsonschema 结构校验
   （config/schemas/project-create-request.schema.json）+ 词表级联校验
   （channel×platform×题材×二级方向×基调池×美学，全部对照
   ui/project-wizard-data.js 静态权威数据）+ platform_traits/genre_profile
   随行快照与词表一致性 + 表里互斥规则（表层 light/dark 互斥、内核恰 1）。
2. **原型三方比对**（--payload 阶段）：payload × config/system_archetypes.json
   × 向导镜像逐项比对（hash/display_name），并全量检测 18 原型镜像漂移。
3. **校验门**（--candidate，融合后）：候选 JSON 容错解析（去代码围栏/括号
   平衡修复，修复必报告）→ jsonschema 信封（creator-derivation-candidate）
   → 签名 v2 深层（creator-signature）→ parent_subject_hash 反查 config
   → parent 属于用户勾选集 → 7 字段无逐字复制父值 → 条数 2-4 → hash 计算。
4. **落库**（默认；--dry-run 关闭）：BEGIN IMMEDIATE 单事务 + foreign_keys=ON
   + 失败整体回滚，六表一次写入（签名资源 / 派生资源 / creator_profiles /
   creator_profile_versions / projects 含 setup 快照 / project_creator_bindings）。
   派生资源内嵌**完整用户输入快照**（selected_archetypes + user_persona_hints
   + setup 全文），setup 快照带 setup_schema_version 标记。

判定策略：FAIL 阻断落库（退出码 1）；WARN 只提示不阻断。
parent_rationale 含错配警告字样时脚本提示「须呈报用户裁决后方可落库」（协议
见 AGENTS.md「项目创建向导」）。

用法::

    # 第一步：收到向导 JSON 后立即做入口校验
    python scripts/novelos_create_project.py --payload payload.json

    # 第二步：融合候选返回后，校验门 + 落库（一步完成）
    python scripts/novelos_create_project.py --payload payload.json \\
        --candidate candidate.json

    # 只校验不落库
    python scripts/novelos_create_project.py --payload payload.json \\
        --candidate candidate.json --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "data/novelos-v2.db"
WIZARD_DATA_FILE = REPO_ROOT / "ui/project-wizard-data.js"
ARCHETYPE_CONFIG = REPO_ROOT / "config/system_archetypes.json"
SCHEMA_DIR = REPO_ROOT / "config/schemas"

SCALES = (
    "短篇（30万字以下）",
    "中篇（30-100万字）",
    "长篇（100-300万字）",
    "超长篇（300万字以上）",
)
SIGNATURE_FIELDS = (
    "sympathies",
    "distrusts",
    "recurring_attention",
    "narrative_principles",
    "forbidden_conveniences",
    "expression_preferences",
    "negative_constraints",
)
HINT_KEYS = {"taste_anchors", "people_and_scenes", "hard_nos", "obsessions"}
MISMATCH_MARKERS = ("错配警告", "mismatch", "根本冲突", "根本相斥", "调和建议")


def content_hash(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def load_wizard_data() -> dict[str, Any]:
    raw = WIZARD_DATA_FILE.read_text(encoding="utf-8")
    return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])


def load_config_archetypes() -> list[dict[str, Any]]:
    return json.loads(ARCHETYPE_CONFIG.read_text(encoding="utf-8"))


def _candidate_shape_ok(obj: Any) -> bool:
    """括号修复后的顶层形状校验：中段缺括号会在尾部补齐后「解析成功但内容
    错位」（字段被嵌进错误的层级），必须靠形状检查兜住。"""
    return (
        isinstance(obj, dict)
        and {"parent_version_id", "signature"} <= set(obj)
        and isinstance(obj["signature"], dict)
        and "sympathies" in obj["signature"]
    )


def parse_candidate_text(raw: str) -> tuple[dict[str, Any], list[str]]:
    """容错解析融合候选：裸 JSON → 去围栏 → 尾部截断修复。修复必须报告。

    只做**安全**修复：去围栏、给尾部截断补闭合括号。中段缺括号（解析成功但
    字段错位）无法安全自动修复——形状校验不过即判解析失败，要求 agent 重出。
    """
    notes: list[str] = []
    text = raw.strip()
    try:
        return json.loads(text), notes
    except json.JSONDecodeError:
        pass
    if text.startswith("```"):
        text = "\n".join(
            line for line in text.splitlines()
            if not line.strip().startswith("```")
        ).strip()
        notes.append("去除 Markdown 代码围栏")
        try:
            return json.loads(text), notes
        except json.JSONDecodeError:
            pass
    _fail = SystemExit(
        "候选 JSON 解析失败或字段错位：按协议要求融合智能体重新输出，"
        "禁止主控手工改写候选内容（去围栏/尾部补括号等结构性修复除外）。"
    )
    unclosed: list[str] = []
    in_str = False
    esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            unclosed.append(ch)
        elif ch == "}":
            if unclosed and unclosed[-1] == "{":
                unclosed.pop()
        elif ch == "]":
            if unclosed and unclosed[-1] == "[":
                unclosed.pop()
    if unclosed:
        closer = "".join("}" if c == "{" else "]" for c in reversed(unclosed))
        try:
            obj = json.loads(text + closer)
        except json.JSONDecodeError as exc:
            raise _fail from exc
        if not _candidate_shape_ok(obj):
            raise _fail
        notes.append(f"补齐尾部未闭合括号 {closer!r}（结构修复不改动内容）")
        return obj, notes
    raise _fail


def validate_request(
    payload: dict[str, Any],
    wizard: dict[str, Any],
    cfg: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    import jsonschema

    errors: list[str] = []
    warns: list[str] = []

    schema = json.loads(
        (SCHEMA_DIR / "project-create-request.schema.json").read_text(encoding="utf-8")
    )
    try:
        jsonschema.validate(payload, schema)
    except jsonschema.ValidationError as exc:
        path = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        errors.append(f"结构校验 FAIL [{path}]: {exc.message}")
        return errors, warns  # 结构坏了，后续词表校验无意义

    s = payload["setup"]
    ch = s["channel"]

    # 词表级联
    if s["platform"] not in wizard["channels"][ch]["platforms"]:
        errors.append(
            f"platform={s['platform']!r} 不属于 {ch} 平台列表 "
            f"{wizard['channels'][ch]['platforms']}"
        )
    pt = wizard["platform_traits"].get(s["platform"])
    if pt is not None and s["platform_traits"] != pt:
        errors.append("platform_traits 与词表快照不一致（伪造或数据旧版）")
    if s["scale"] not in SCALES:
        errors.append(f"scale={s['scale']!r} 非四档之一")
    genres = wizard["genres"].get(ch, [])
    if isinstance(genres, dict):
        genres = list(genres.keys())
    if s["primary_genre"] not in genres:
        errors.append(f"primary_genre={s['primary_genre']!r} 不在 {ch} 题材库")
    sd_map = wizard["secondary_directions"].get(ch, {})
    sd_list = sd_map.get(s["primary_genre"], []) if isinstance(sd_map, dict) else []
    unknown = [d for d in s["secondary_directions"] if d not in sd_list]
    if unknown:
        warns.append(f"secondary_directions 超出词表（{unknown}）——自由发挥或词表需更新")

    # 表里基调
    pool = {t["value"]: t["pole"] for t in wizard["tone_pools"].get(ch, [])}
    bad = [v for v in s["emotional_surface"] if v not in pool]
    if bad:
        errors.append(f"emotional_surface 不在 {ch} 基调池: {bad}")
    poles = [pool.get(v) for v in s["emotional_surface"] if v in pool]
    if "light" in poles and "dark" in poles:
        errors.append(
            f"emotional_surface 同层 light+dark 互斥: {list(zip(s['emotional_surface'], poles))}"
        )
    if s["emotional_core"] not in pool:
        errors.append(f"emotional_core={s['emotional_core']!r} 不在 {ch} 基调池")
    if s["emotional_core"] in s["emotional_surface"]:
        errors.append("emotional_core 与 surface 重复")

    # 美学
    bad_aes = [a for a in s["aesthetic_styles"] if a not in wizard["aesthetic_styles"]]
    if bad_aes:
        errors.append(f"aesthetic_styles 超出词表: {bad_aes}")

    # 题材信息包快照核对
    gp = wizard["genre_profiles"].get(f"{ch}|{s['primary_genre']}")
    if s["genre_profile"] is None and gp is not None:
        warns.append("genre_profile=null 但词表已有该题材包，快照漏带")
    if s["genre_profile"] is not None and s["genre_profile"] != gp:
        errors.append("genre_profile 与词表快照不一致")

    # 原型三方比对（payload × config × 镜像）
    mirror = {a["profile_version_id"]: a for a in wizard["system_archetypes"]}
    for i, sa in enumerate(s["creator"]["selected_archetypes"], 1):
        tag = f"[{i}] {sa['display_name']}"
        a = cfg.get(sa["profile_version_id"])
        if a is None:
            errors.append(f"{tag} profile_version_id={sa['profile_version_id']} 在 config 中不存在")
            continue
        if a["subject_hash"] != sa["subject_hash"]:
            errors.append(f"{tag} subject_hash 与 config 不符")
        if a["display_name"] != sa["display_name"]:
            errors.append(f"{tag} display_name 与 config 不符（应为 {a['display_name']!r}）")
        m = mirror.get(sa["profile_version_id"])
        if m is None:
            errors.append(f"{tag} 向导镜像缺失")
        elif m["subject_hash"] != a["subject_hash"]:
            errors.append(f"{tag} 向导镜像 hash 漂移")
        aff = a.get("channel_affinity")
        if ch in ("男频", "女频") and aff not in (ch, "通吃"):
            warns.append(f"{tag} channel_affinity={aff}，在 {ch} 通道下为负分项")
    drift = [
        pvid for pvid, m in mirror.items()
        if pvid in cfg and m["subject_hash"] != cfg[pvid]["subject_hash"]
    ]
    if drift:
        errors.append(f"向导镜像漂移 {len(drift)} 个原型（{drift}）——先同步镜像再创建")
    return errors, warns


def validate_candidate(
    candidate: dict[str, Any],
    payload: dict[str, Any],
    cfg: dict[str, dict[str, Any]],
) -> tuple[list[str], str]:
    import jsonschema

    errors: list[str] = []
    env_schema = json.loads(
        (SCHEMA_DIR / "creator-derivation-candidate.schema.json").read_text(encoding="utf-8")
    )
    try:
        jsonschema.validate(candidate, env_schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"候选信封 schema FAIL: {exc.message}")

    sig = candidate.get("signature", {})
    sig_schema = json.loads(
        (SCHEMA_DIR / "creator-signature.schema.json").read_text(encoding="utf-8")
    )
    try:
        jsonschema.validate(sig, sig_schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"签名 schema v2 FAIL: {exc.message}")

    parent = cfg.get(candidate.get("parent_version_id", ""))
    if parent is None:
        errors.append(f"parent_version_id={candidate.get('parent_version_id')!r} 不在 config")
    else:
        if parent["subject_hash"] != candidate.get("parent_subject_hash"):
            errors.append("parent_subject_hash 与 config 反查不符")
        if candidate.get("display_name") == parent["display_name"]:
            errors.append("display_name 逐字复制父原型名——须凝聚为本书人格名")

    selected = {
        a["profile_version_id"] for a in payload["setup"]["creator"]["selected_archetypes"]
    }
    if candidate.get("parent_version_id") not in selected:
        errors.append("parent 不属于用户勾选集")

    if parent is not None:
        for field in SIGNATURE_FIELDS:
            for item in sig.get(field, []):
                if any(
                    item in parent["signature"].get(pf, [])
                    for pf in SIGNATURE_FIELDS
                ):
                    errors.append(f"逐字复制父值 [{field}]: {item[:30]}…")
            n = len(sig.get(field, []))
            if not 2 <= n <= 4:
                errors.append(f"{field} 条数 {n} 超出 2-4")

    sig_json = json.dumps(sig, ensure_ascii=False, indent=2)
    sig_hash = content_hash(sig_json)
    return errors, sig_hash


def persist(
    db_path: Path,
    payload: dict[str, Any],
    candidate: dict[str, Any],
    sig_hash: str,
) -> dict[str, str]:
    setup = payload["setup"]
    sig = candidate["signature"]
    sig_json = json.dumps(sig, ensure_ascii=False, indent=2)

    aux = sorted(
        a["profile_version_id"]
        for a in setup["creator"]["selected_archetypes"]
        if a["profile_version_id"] != candidate["parent_version_id"]
    )
    parent_name = next(
        (
            a["display_name"]
            for a in setup["creator"]["selected_archetypes"]
            if a["profile_version_id"] == candidate["parent_version_id"]
        ),
        "",
    )
    deriv = {
        "parent_version_id": candidate["parent_version_id"],
        "parent_display_name": parent_name,
        "parent_subject_hash": candidate["parent_subject_hash"],
        "auxiliary_archetypes": aux,
        "rationale": candidate["parent_rationale"],
        "user_input_snapshot": {
            "selected_archetypes": setup["creator"]["selected_archetypes"],
            "user_persona_hints": setup["creator"]["user_persona_hints"],
            "setup": {k: v for k, v in setup.items() if k != "creator"},
        },
    }
    deriv_json = json.dumps(deriv, ensure_ascii=False, indent=2)

    ids = {
        "resource_sig": f"resource:{uuid.uuid4()}",
        "resource_deriv": f"resource:{uuid.uuid4()}",
        "profile": f"creator-profile:{uuid.uuid4()}",
        "profile_version": f"creator-profile-version:{uuid.uuid4()}",
        "project": f"project:{uuid.uuid4()}",
    }
    meta = {
        "setup_schema_version": 2,
        "setup": {k: v for k, v in setup.items() if k != "creator"},
    }
    description = (
        f"{setup['channel']}·{setup['primary_genre']} | "
        f"{setup['platform']}·{(setup['platform_traits'] or {}).get('model', '')} | "
        f"{setup['scale']}"
    )

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO resources (id, media_type, content, content_hash) "
            "VALUES (?, 'application/json', CAST(? AS BLOB), ?)",
            (ids["resource_sig"], sig_json, sig_hash),
        )
        conn.execute(
            "INSERT INTO resources (id, media_type, content, content_hash) "
            "VALUES (?, 'application/json', CAST(? AS BLOB), ?)",
            (ids["resource_deriv"], deriv_json, content_hash(deriv_json)),
        )
        conn.execute(
            "INSERT INTO creator_profiles (id, display_name, ownership) VALUES (?, ?, 'user')",
            (ids["profile"], candidate["display_name"]),
        )
        conn.execute(
            "INSERT INTO creator_profile_versions "
            "(id, profile_id, revision, content_resource_id, subject_hash, "
            " parent_version_id, derivation_resource_id) VALUES (?, ?, 1, ?, ?, ?, ?)",
            (
                ids["profile_version"], ids["profile"], ids["resource_sig"],
                sig_hash, candidate["parent_version_id"], ids["resource_deriv"],
            ),
        )
        conn.execute(
            "INSERT INTO projects (id, name, description, version, metadata_json) "
            "VALUES (?, ?, ?, 1, ?)",
            (ids["project"], setup["title"], description,
             json.dumps(meta, ensure_ascii=False)),
        )
        conn.execute(
            "INSERT INTO project_creator_bindings "
            "(project_id, profile_id, profile_version_id, profile_revision, "
            " subject_hash, binding_mode) VALUES (?, ?, ?, 1, ?, 'derive')",
            (ids["project"], ids["profile"], ids["profile_version"], sig_hash),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    ids["sig_hash"] = sig_hash
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--payload", required=True, help="向导 novelos.project.create.v2 JSON 路径")
    parser.add_argument("--candidate", help="融合智能体产出的 creator_derivation_candidate JSON 路径")
    parser.add_argument("--dry-run", action="store_true", help="只校验，不落库")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()

    wizard = load_wizard_data()
    cfg_list = load_config_archetypes()
    cfg = {
        f"creator-profile-version:{a['id']}:{a['revision']}": a for a in cfg_list
    }

    try:
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"payload 读取失败: {exc}")
        return 2

    errors, warns = validate_request(payload, wizard, cfg)
    for w in warns:
        print(f"WARN {w}")
    if errors:
        for e in errors:
            print(f"FAIL {e}")
        print(f"\n入口校验失败（{len(errors)} FAIL / {len(warns)} WARN），拒绝继续。")
        return 1
    print(f"入口校验通过（0 FAIL / {len(warns)} WARN）。")

    if not args.candidate:
        print("未提供 --candidate：入口校验完成。可注入融合智能体，产出后带 --candidate 重跑。")
        return 0

    raw = Path(args.candidate).read_text(encoding="utf-8")
    candidate, notes = parse_candidate_text(raw)
    for n in notes:
        print(f"NOTE 候选解析修复: {n}")

    gate_errors, sig_hash = validate_candidate(candidate, payload, cfg)
    if gate_errors:
        for e in gate_errors:
            print(f"FAIL {e}")
        print(f"\n校验门失败（{len(gate_errors)} FAIL），拒绝落库。")
        return 1
    print("校验门通过（信封 + 签名 v2 + parent 反查 + 勾集 + 逐字复制 + 条数）。")

    rationale = candidate.get("parent_rationale", "")
    if any(m in rationale for m in MISMATCH_MARKERS):
        print(
            "\n!! parent_rationale 含错配警告字样——按协议必须把冲突与调和建议"
            "呈报用户裁决，未获裁决不得落库。"
        )

    if args.dry_run:
        print(f"\n--dry-run：未落库。融合签名 hash = {sig_hash}")
        return 0

    if not Path(args.db).exists():
        print(f"数据库不存在: {args.db}")
        return 2
    ids = persist(Path(args.db), payload, candidate, sig_hash)
    print("\n落库成功（单事务提交，六表一次写入）。")
    print(f"  project          {ids['project']}")
    print(f"  creator_profile  {ids['profile']}")
    print(f"  profile_version  {ids['profile_version']}")
    print(f"  resource_sig     {ids['resource_sig']} ({ids['sig_hash']})")
    print(f"  resource_deriv   {ids['resource_deriv']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
