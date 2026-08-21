#!/usr/bin/env python
"""项目创建固化管线：入口校验 → 内核建核/绑定 → 分身候选校验门 → 单事务落库。

向导产出的 `novelos.project.create.v3` JSON 不再靠主控眼审，本脚本一次完成：

1. **入口校验**（--payload，必跑）：jsonschema 结构校验
   （config/schemas/project-create-request.schema.json，v2/v3 双分支）+
   词表级联校验（channel×platform×题材×二级方向×基调池×美学，全部对照
   ui/project-wizard-data.js 静态权威数据）+ 表里互斥规则。
   v3 内核分支：mode=select 时**库内反查**（kernel_version_id 存在、
   profile ownership='author_kernel'、status='active'、subject_hash 相符）；
   mode=create 时 kernel_hints 由 schema 约束。
   v2 过渡分支：原型三方比对照旧（向导 v3 上线后移除）。
2. **内核阶段**（--kernel-candidate，mode=create 首次建核或独立修订）：
   候选容错解析 → kernel-candidate 信封 + author-kernel 深层两步校验 →
   revise 基底库内反查 + display_name 连续性 + growth_log 非空 →
   单事务落库（内核资源 / 派生资源 / creator_profiles[author_kernel] /
   creator_profile_versions）。`--emit-payload <path>` 输出缝合后的
   select 形态 payload（mode=create 建核后自动回填 kernel_version_id）。
3. **校验门**（--candidate，分身融合后）：候选容错解析 →
   creator-derivation-candidate 信封 → 签名 v2 深层 → v3 下 parent=内核
   版本库内反查（v2 下 parent=config 原型反查）→ 逐字复制与条数检查 →
   hash 计算。
4. **落库**（默认；--dry-run 关闭）：BEGIN IMMEDIATE 单事务 + foreign_keys=ON
   + 失败整体回滚。v3 六表一次写入（签名资源 / 派生资源 / creator_profiles /
   creator_profile_versions[parent=内核版本] / projects 含 setup 快照 /
   project_creator_bindings[binding_mode='kernel_derive' + kernel_version_id]）。

判定策略：FAIL 阻断（退出码 1）；WARN 只提示不阻断。
parent_rationale 含错配警告字样时提示「须呈报用户裁决后方可落库」。

用法（v3 标准流）::

    # ① 入口校验
    python scripts/novelos_create_project.py --payload payload.json

    # ② mode=create：内核融合候选 → 建核 + 输出缝合 payload
    python scripts/novelos_create_project.py --payload payload.json \\
        --kernel-candidate kernel_candidate.json \\
        --emit-payload payload.bound.json

    # ③ 分身融合候选（用缝合 payload 或原 select payload）→ 项目落库
    python scripts/novelos_create_project.py --payload payload.bound.json \\
        --candidate persona_candidate.json

    # 内核独立修订（不建项目）
    python scripts/novelos_create_project.py --kernel-revise revise_payload.json \\
        --kernel-candidate kernel_candidate.json
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
DEFAULT_DB = REPO_ROOT / "data" / "novelos-v2.db"
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
# 内核 identity 中可与分身七字段发生逐字复制的清单字段（v3 逐字复制检查的比对面）。
KERNEL_IDENTITY_LIST_FIELDS = (
    "core_questions",
    "value_axioms",
    "aesthetic_commitments",
    "creative_axioms",
)
MISMATCH_MARKERS = ("错配警告", "mismatch", "根本冲突", "根本相斥", "调和建议")


def content_hash(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def load_wizard_data() -> dict[str, Any]:
    raw = WIZARD_DATA_FILE.read_text(encoding="utf-8")
    return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])


def load_config_archetypes() -> list[dict[str, Any]]:
    return json.loads(ARCHETYPE_CONFIG.read_text(encoding="utf-8"))


def is_v3(payload: dict[str, Any]) -> bool:
    return payload.get("request_type") == "novelos.project.create.v3"


def lookup_kernel_version(conn: sqlite3.Connection, version_id: str) -> sqlite3.Row | None:
    """库内反查内核版本（含 profile 归属校验所需列）。统一 Row 工厂便于按名取列。"""
    conn.row_factory = sqlite3.Row
    return conn.execute(
        "SELECT v.id, v.revision, v.subject_hash, v.profile_id, "
        "       p.display_name, p.status, p.ownership, "
        "       CAST(r.content AS TEXT) AS kernel_json "
        "FROM creator_profile_versions v "
        "JOIN creator_profiles p ON p.id = v.profile_id "
        "JOIN resources r ON r.id = v.content_resource_id "
        "WHERE v.id = ?",
        (version_id,),
    ).fetchone()


def _persona_shape_ok(obj: Any) -> bool:
    return (
        isinstance(obj, dict)
        and {"parent_version_id", "signature"} <= set(obj)
        and isinstance(obj["signature"], dict)
        and "sympathies" in obj["signature"]
    )


def _kernel_shape_ok(obj: Any) -> bool:
    return (
        isinstance(obj, dict)
        and {"mode", "display_name", "kernel"} <= set(obj)
        and isinstance(obj["kernel"], dict)
        and "identity" in obj["kernel"]
    )


def parse_candidate_text(raw: str, kind: str = "persona") -> tuple[dict[str, Any], list[str]]:
    """容错解析候选：裸 JSON → 去围栏 → 尾部截断修复。修复必须报告。

    只做**安全**修复：去围栏、给尾部截断补闭合括号。中段缺括号（解析成功但
    字段错位）无法安全自动修复——形状校验不过即判解析失败，要求 agent 重出。
    kind=persona 查分身形状（parent_version_id+signature）；
    kind=kernel 查内核形状（mode+display_name+kernel.identity）。
    """
    shape = _persona_shape_ok if kind == "persona" else _kernel_shape_ok
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
        if not shape(obj):
            raise _fail
        notes.append(f"补齐尾部未闭合括号 {closer!r}（结构修复不改动内容）")
        return obj, notes
    raise _fail


def validate_request(
    payload: dict[str, Any],
    wizard: dict[str, Any],
    cfg: dict[str, dict[str, Any]],
    conn: sqlite3.Connection,
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

    if is_v3(payload):
        ak = s["author_kernel"]
        if ak["mode"] == "select":
            row = lookup_kernel_version(conn, ak["kernel_version_id"])
            if row is None:
                errors.append(
                    f"kernel_version_id={ak['kernel_version_id']!r} 库中不存在"
                )
            else:
                if row["ownership"] != "author_kernel":
                    errors.append(
                        f"kernel_version_id 指向 ownership={row['ownership']!r} 的版本——"
                        "只能绑定 author_kernel 内核"
                    )
                if row["status"] != "active":
                    errors.append(f"内核 profile status={row['status']!r}，非 active")
                if row["subject_hash"] != ak["subject_hash"]:
                    errors.append("内核 subject_hash 与库内反查不符")
                if ak.get("display_name") and ak["display_name"] != row["display_name"]:
                    warns.append(
                        f"内核 display_name 与库不符（库内 {row['display_name']!r}）"
                    )
        return errors, warns

    # v2 过渡分支：原型三方比对（payload × config × 镜像）
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


def validate_kernel_candidate(
    candidate: dict[str, Any],
    conn: sqlite3.Connection,
) -> tuple[list[str], str]:
    """内核候选校验门：信封 + author-kernel 深层 + revise 基底反查。返回 (errors, kernel_hash)。"""
    import jsonschema

    errors: list[str] = []
    env_schema = json.loads(
        (SCHEMA_DIR / "kernel-candidate.schema.json").read_text(encoding="utf-8")
    )
    try:
        jsonschema.validate(candidate, env_schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"内核候选信封 schema FAIL: {exc.message}")

    kernel = candidate.get("kernel", {})
    kernel_schema = json.loads(
        (SCHEMA_DIR / "author-kernel.schema.json").read_text(encoding="utf-8")
    )
    try:
        jsonschema.validate(kernel, kernel_schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"author-kernel schema FAIL: {exc.message}")

    base_row = None
    if candidate.get("mode") == "revise":
        base_row = lookup_kernel_version(conn, candidate.get("base_version", ""))
        if base_row is None:
            errors.append(f"base_version={candidate.get('base_version')!r} 库中不存在")
        else:
            if base_row["ownership"] != "author_kernel":
                errors.append("base_version 指向非 author_kernel 版本——内核只能修订内核")
            base_identity = json.loads(base_row["kernel_json"]).get("identity", {})
            if kernel.get("identity", {}).get("display_name") != base_identity.get("display_name"):
                errors.append("revise 的 identity.display_name 与基底不一致——修订是演化不是重写")
            base_log = json.loads(base_row["kernel_json"]).get("growth_log", [])
            if len(kernel.get("growth_log", [])) <= len(base_log):
                errors.append("revise 的 growth_log 未追加新条目——每次修订必须带本次归因")
    else:
        dup = conn.execute(
            "SELECT COUNT(*) FROM creator_profiles "
            "WHERE ownership = 'author_kernel' AND display_name = ?",
            (candidate.get("display_name", ""),),
        ).fetchone()[0]
        if dup:
            errors.append("display_name 与既有内核重名——内核是跨书根，必须可区分")

    kernel_json = json.dumps(kernel, ensure_ascii=False, indent=2)
    return errors, content_hash(kernel_json)


def persist_kernel(
    db_path: Path,
    candidate: dict[str, Any],
    kernel_hash: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, str]:
    """内核落库（独立事务）：create 建新内核 profile；revise 在基底 profile 上出新 revision。"""
    kernel = candidate["kernel"]
    kernel_json = json.dumps(kernel, ensure_ascii=False, indent=2)

    snapshot = None
    if payload is not None and is_v3(payload):
        setup = payload["setup"]
        snapshot = {
            "author_kernel": setup["author_kernel"],
            "setup": {k: v for k, v in setup.items() if k != "author_kernel"},
        }
    deriv = {
        "mode": candidate["mode"],
        "rationale": candidate["rationale"],
        "user_input_snapshot": snapshot,
    }
    if candidate["mode"] == "revise":
        deriv["base_version"] = candidate["base_version"]
    deriv_json = json.dumps(deriv, ensure_ascii=False, indent=2)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        res_kernel = f"resource:{uuid.uuid4()}"
        res_deriv = f"resource:{uuid.uuid4()}"
        conn.execute(
            "INSERT INTO resources (id, media_type, content, content_hash) "
            "VALUES (?, 'application/json', CAST(? AS BLOB), ?)",
            (res_kernel, kernel_json, kernel_hash),
        )
        conn.execute(
            "INSERT INTO resources (id, media_type, content, content_hash) "
            "VALUES (?, 'application/json', CAST(? AS BLOB), ?)",
            (res_deriv, deriv_json, content_hash(deriv_json)),
        )
        if candidate["mode"] == "revise":
            base = lookup_kernel_version(conn, candidate["base_version"])
            profile_id = base["profile_id"]
            revision = conn.execute(
                "SELECT COALESCE(MAX(revision), 0) + 1 FROM creator_profile_versions "
                "WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()[0]
            version_id = f"creator-profile-version:{uuid.uuid4()}"
            conn.execute(
                "INSERT INTO creator_profile_versions "
                "(id, profile_id, revision, content_resource_id, subject_hash, "
                " parent_version_id, derivation_resource_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (version_id, profile_id, revision, res_kernel, kernel_hash,
                 candidate["base_version"], res_deriv),
            )
            conn.execute(
                "UPDATE creator_profiles SET version = version + 1, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (profile_id,),
            )
        else:
            profile_id = f"creator-profile:{uuid.uuid4()}"
            version_id = f"creator-profile-version:{uuid.uuid4()}"
            conn.execute(
                "INSERT INTO creator_profiles (id, display_name, ownership) "
                "VALUES (?, ?, 'author_kernel')",
                (profile_id, candidate["display_name"]),
            )
            conn.execute(
                "INSERT INTO creator_profile_versions "
                "(id, profile_id, revision, content_resource_id, subject_hash, "
                " parent_version_id, derivation_resource_id) VALUES (?, ?, 1, ?, ?, NULL, ?)",
                (version_id, profile_id, res_kernel, kernel_hash, res_deriv),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "kernel_profile": profile_id,
        "kernel_version": version_id,
        "resource_kernel": res_kernel,
        "resource_deriv": res_deriv,
        "subject_hash": kernel_hash,
    }


def validate_candidate(
    candidate: dict[str, Any],
    payload: dict[str, Any],
    cfg: dict[str, dict[str, Any]],
    conn: sqlite3.Connection,
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

    parent_lists: dict[str, list[str]] = {}
    if is_v3(payload):
        ak = payload["setup"]["author_kernel"]
        row = lookup_kernel_version(conn, ak["kernel_version_id"])
        if row is None:
            errors.append(f"parent 内核版本库中不存在: {ak['kernel_version_id']!r}")
        else:
            if candidate.get("parent_version_id") != ak["kernel_version_id"]:
                errors.append("parent_version_id 与 payload 绑定的内核版本不符")
            if candidate.get("parent_subject_hash") != row["subject_hash"]:
                errors.append("parent_subject_hash 与内核库内反查不符")
            if candidate.get("display_name") == row["display_name"]:
                errors.append("display_name 逐字复制内核名——分身须凝聚为本书人格名")
            identity = json.loads(row["kernel_json"]).get("identity", {})
            for field in KERNEL_IDENTITY_LIST_FIELDS:
                parent_lists[field] = list(identity.get(field, []))
    else:
        parent = cfg.get(candidate.get("parent_version_id", ""))
        if parent is None:
            errors.append(f"parent_version_id={candidate.get('parent_version_id')!r} 不在 config")
        else:
            if parent["subject_hash"] != candidate.get("parent_subject_hash"):
                errors.append("parent_subject_hash 与 config 反查不符")
            if candidate.get("display_name") == parent["display_name"]:
                errors.append("display_name 逐字复制父原型名——须凝聚为本书人格名")
            for field in SIGNATURE_FIELDS:
                parent_lists[field] = list(parent["signature"].get(field, []))
        selected = {
            a["profile_version_id"] for a in payload["setup"]["creator"]["selected_archetypes"]
        }
        if candidate.get("parent_version_id") not in selected:
            errors.append("parent 不属于用户勾选集")

    if parent_lists:
        for field in SIGNATURE_FIELDS:
            for item in sig.get(field, []):
                if any(
                    item in parent_list
                    for parent_list in parent_lists.values()
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

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")

        if is_v3(payload):
            ak = setup["author_kernel"]
            kernel_row = lookup_kernel_version(conn, ak["kernel_version_id"])
            if kernel_row is None or kernel_row["ownership"] != "author_kernel":
                raise SystemExit(
                    f"绑定的内核版本无效: {ak['kernel_version_id']!r}（落库前校验门应已拦截）"
                )
            deriv = {
                "parent_version_id": ak["kernel_version_id"],
                "parent_display_name": kernel_row["display_name"],
                "parent_subject_hash": kernel_row["subject_hash"],
                "auxiliary_archetypes": [],
                "rationale": candidate["parent_rationale"],
                "user_input_snapshot": {
                    "author_kernel": {k: v for k, v in ak.items() if k != "kernel_hints"},
                    "setup": {k: v for k, v in setup.items() if k != "author_kernel"},
                },
            }
            binding_mode = "kernel_derive"
            kernel_version_id = ak["kernel_version_id"]
        else:
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
            binding_mode = "derive"
            kernel_version_id = None
        deriv_json = json.dumps(deriv, ensure_ascii=False, indent=2)

        ids = {
            "resource_sig": f"resource:{uuid.uuid4()}",
            "resource_deriv": f"resource:{uuid.uuid4()}",
            "profile": f"creator-profile:{uuid.uuid4()}",
            "profile_version": f"creator-profile-version:{uuid.uuid4()}",
            "project": f"project:{uuid.uuid4()}",
        }
        meta = {
            "setup_schema_version": 3 if is_v3(payload) else 2,
            "setup": {
                k: v for k, v in setup.items()
                if k not in ("creator", "author_kernel")
            },
        }
        description = (
            f"{setup['channel']}·{setup['primary_genre']} | "
            f"{setup['platform']}·{(setup['platform_traits'] or {}).get('model', '')} | "
            f"{setup['scale']}"
        )

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
            " subject_hash, binding_mode, kernel_version_id) "
            "VALUES (?, ?, ?, 1, ?, ?, ?)",
            (ids["project"], ids["profile"], ids["profile_version"], sig_hash,
             binding_mode, kernel_version_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    ids["sig_hash"] = sig_hash
    return ids


def _emit_bound_payload(payload: dict[str, Any], kernel: dict[str, str], path: Path) -> None:
    """mode=create 建核后，把 payload 缝合为 select 形态（机械回填 id/hash，不改内容）。"""
    bound = json.loads(json.dumps(payload, ensure_ascii=False))
    ak = bound["setup"]["author_kernel"]
    stitched = {
        "mode": "select",
        "kernel_version_id": kernel["kernel_version"],
        "subject_hash": kernel["subject_hash"],
        "kernel_hints": ak.get("kernel_hints", {}),
    }
    if isinstance(ak.get("display_name"), str):
        stitched["display_name"] = ak["display_name"]
    bound["setup"]["author_kernel"] = stitched
    path.write_text(json.dumps(bound, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--payload", help="向导 novelos.project.create.v2/v3 JSON 路径（--kernel-revise 修订模式可省）")
    parser.add_argument("--kernel-candidate", help="内核融合智能体产出的 novelos.kernel.candidate.v1 JSON 路径")
    parser.add_argument("--kernel-revise", help="独立内核修订的 revise 载荷 JSON 路径（novelos.kernel.revise.v1，不需要 --payload）")
    parser.add_argument("--emit-payload", help="建核后输出缝合 select 形态 payload 的路径")
    parser.add_argument("--candidate", help="分身融合智能体产出的 creator_derivation_candidate JSON 路径")
    parser.add_argument("--dry-run", action="store_true", help="只校验，不落库")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()

    if not args.payload and not args.kernel_revise:
        parser.error("需要 --payload（向导载荷）或 --kernel-revise（独立内核修订）")

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"数据库不存在: {db_path}")
        return 2
    conn = sqlite3.connect(db_path)

    payload: dict[str, Any] | None = None
    try:
        if args.kernel_revise:
            # 独立内核修订：不需要项目 payload，直接进内核阶段
            payload = json.loads(Path(args.kernel_revise).read_text(encoding="utf-8"))
        elif args.payload:
            try:
                payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"payload 读取失败: {exc}")
                return 2

        if payload is not None and not args.kernel_revise:
            wizard = load_wizard_data()
            cfg_list = load_config_archetypes()
            cfg = {
                f"creator-profile-version:{a['id']}:{a['revision']}": a for a in cfg_list
            }
            errors, warns = validate_request(payload, wizard, cfg, conn)
            for w in warns:
                print(f"WARN {w}")
            if errors:
                for e in errors:
                    print(f"FAIL {e}")
                print(f"\n入口校验失败（{len(errors)} FAIL / {len(warns)} WARN），拒绝继续。")
                return 1
            print(f"入口校验通过（0 FAIL / {len(warns)} WARN）。")

        if args.kernel_candidate:
            raw = Path(args.kernel_candidate).read_text(encoding="utf-8")
            candidate, notes = parse_candidate_text(raw, kind="kernel")
            for n in notes:
                print(f"NOTE 内核候选解析修复: {n}")
            k_errors, kernel_hash = validate_kernel_candidate(candidate, conn)
            if k_errors:
                for e in k_errors:
                    print(f"FAIL {e}")
                print(f"\n内核校验门失败（{len(k_errors)} FAIL），拒绝落库。")
                return 1
            print("内核校验门通过（信封 + author-kernel 深层 + 基底反查）。")
            if args.dry_run:
                print(f"\n--dry-run：未落库。内核 hash = {kernel_hash}")
            else:
                kernel = persist_kernel(db_path, candidate, kernel_hash, payload)
                print("\n内核落库成功（单事务提交）。")
                print(f"  kernel_profile   {kernel['kernel_profile']}")
                print(f"  kernel_version   {kernel['kernel_version']}")
                print(f"  subject_hash     {kernel['subject_hash']}")
                if args.emit_payload and payload is not None and is_v3(payload):
                    if payload["setup"]["author_kernel"].get("mode") == "create":
                        _emit_bound_payload(payload, kernel, Path(args.emit_payload))
                        print(f"  bound payload    {args.emit_payload}（已缝合为 select 形态）")
            if not args.candidate:
                return 0

        if args.candidate:
            if payload is None or args.kernel_revise:
                parser.error("--candidate 需要与 --payload（项目创建）同用")
            raw = Path(args.candidate).read_text(encoding="utf-8")
            candidate, notes = parse_candidate_text(raw)
            for n in notes:
                print(f"NOTE 候选解析修复: {n}")

            wizard = load_wizard_data()
            cfg_list = load_config_archetypes()
            cfg = {
                f"creator-profile-version:{a['id']}:{a['revision']}": a for a in cfg_list
            }
            gate_errors, sig_hash = validate_candidate(candidate, payload, cfg, conn)
            if gate_errors:
                for e in gate_errors:
                    print(f"FAIL {e}")
                print(f"\n校验门失败（{len(gate_errors)} FAIL），拒绝落库。")
                return 1
            print("校验门通过（信封 + 签名 v2 + parent 反查 + 逐字复制 + 条数）。")

            rationale = candidate.get("parent_rationale", "")
            if any(m in rationale for m in MISMATCH_MARKERS):
                print(
                    "\n!! parent_rationale 含错配警告字样——按协议必须把冲突与调和建议"
                    "呈报用户裁决，未获裁决不得落库。"
                )

            if args.dry_run:
                print(f"\n--dry-run：未落库。融合签名 hash = {sig_hash}")
                return 0

            ids = persist(db_path, payload, candidate, sig_hash)
            print("\n落库成功（单事务提交，六表一次写入）。")
            print(f"  project          {ids['project']}")
            print(f"  creator_profile  {ids['profile']}")
            print(f"  profile_version  {ids['profile_version']}")
            print(f"  resource_sig     {ids['resource_sig']} ({ids['sig_hash']})")
            print(f"  resource_deriv   {ids['resource_deriv']}")
            return 0

        if args.kernel_revise:
            print("未提供 --kernel-candidate：revise 载荷本身无可校验项。")
            return 0

        print("未提供 --candidate：入口校验完成。可注入融合智能体，产出后带 --candidate 重跑。")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
