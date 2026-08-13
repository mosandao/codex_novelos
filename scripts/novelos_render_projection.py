#!/usr/bin/env python
"""项目投影渲染（裸 sqlite3，零 novelos_mcp 依赖）。

把权威数据库 ``data/novelos-v2.db`` 的内容单向渲染为 Markdown 文件目录
``novels/<项目目录>/``。只渲染当前权威视图（locked 规划 + accepted 正文），
不再渲染依赖已退役门禁表（authority_commits / agent_runs / traces）的
候选诊断、全部产出与溯源档案。

用法::

    python scripts/novelos_render_projection.py --project project:xxx
    python scripts/novelos_render_projection.py --project project:xxx --output novels/
    python scripts/novelos_render_projection.py --project project:xxx --verify   # 渲染后校验 manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any

PROJECTION_FORMAT_VERSION = 1
GENERATOR_VERSION = "2.0.0"

_ILLEGAL_CHAR = re.compile(r'[\x00-\x1f\x7f\\/:*?"<>|]')
_CN_DIGITS = "零一二三四五六七八九"


def content_hash(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def cn_num(n: int) -> str:
    """正整数转中文数字（1->一, 10->十, 21->二十一）。"""
    if n < 0:
        return str(n)
    if n == 0:
        return "零"
    if n < 10:
        return _CN_DIGITS[n]
    if n < 20:
        return "十" if n == 10 else "十" + _CN_DIGITS[n - 10]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _CN_DIGITS[tens] + "十" + (_CN_DIGITS[ones] if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        result = _CN_DIGITS[hundreds] + "百"
        if rest == 0:
            return result
        if rest < 10:
            return result + "零" + _CN_DIGITS[rest]
        return result + cn_num(rest)
    return str(n)


def sanitize_filename(name: str, default: str = "untitled") -> str:
    if not name:
        return default
    cleaned = _ILLEGAL_CHAR.sub("_", name).strip().strip(". ")
    if not cleaned or cleaned in ("..", ".") or ".." in cleaned:
        return default
    return cleaned


# --------------------------------------------------------------------------- #
# 读取层：裸 sqlite3 直连，组装权威快照
# --------------------------------------------------------------------------- #


def _read_resource(conn: sqlite3.Connection, resource_id: str) -> str:
    """读 resources.content（BLOB/TEXT）为 UTF-8 文本。"""
    row = conn.execute("SELECT content FROM resources WHERE id=?", (resource_id,)).fetchone()
    if row is None:
        return ""
    blob = row[0]
    if isinstance(blob, bytes):
        return blob.decode("utf-8", errors="replace")
    return str(blob) if blob is not None else ""


def _row(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict[str, Any] | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r is not None else None


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_snapshot(conn: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    project = _row(conn, "SELECT * FROM projects WHERE id=?", (project_id,))
    if project is None:
        raise SystemExit(f"找不到项目 {project_id}")

    # locked 规划资产
    planning: dict[str, dict[str, Any]] = {}
    volume_outlines: list[dict[str, Any]] = []
    chapter_plans: list[dict[str, Any]] = []
    for r in _rows(
        conn,
        "SELECT * FROM planning_assets WHERE project_id=? AND status='locked' ORDER BY asset_type",
        (project_id,),
    ):
        r["content"] = _read_resource(conn, r["content_resource_id"])
        r["metadata"] = json.loads(r["metadata_json"]) if r.get("metadata_json") else {}
        planning[r["asset_type"]] = r
        if r["asset_type"] == "volume_outline":
            volume_outlines.append(r)
        elif r["asset_type"] == "chapter_plan":
            chapter_plans.append(r)

    # creator 签名（binding → profile_version → resource）
    binding = _row(conn, "SELECT * FROM project_creator_bindings WHERE project_id=?", (project_id,))
    creator_signature: dict[str, Any] | None = None
    if binding is not None:
        pv = _row(conn, "SELECT * FROM creator_profile_versions WHERE id=?", (binding["profile_version_id"],))
        profile = _row(conn, "SELECT * FROM creator_profiles WHERE id=?", (binding["profile_id"],))
        if pv is not None and profile is not None:
            signature = json.loads(_read_resource(conn, pv["content_resource_id"]))
            creator_signature = {
                "profile_id": binding["profile_id"],
                "profile_display_name": profile["display_name"],
                "profile_version_id": binding["profile_version_id"],
                "profile_revision": binding["profile_revision"],
                "subject_hash": binding["subject_hash"],
                "binding_mode": binding["binding_mode"],
                "signature": signature,
            }

    # book_soul 从 locked direction 的 metadata 提取
    book_soul: dict[str, Any] | None = None
    direction = planning.get("direction")
    if direction is not None and "book_soul" in direction["metadata"]:
        book_soul = {
            "direction_id": direction["id"],
            "direction_version": direction["version"],
            "direction_subject_hash": direction.get("subject_hash", ""),
            "book_soul": direction["metadata"]["book_soul"],
        }

    # accepted 正文（JOIN volumes/books）
    chapters = _rows(
        conn,
        """
        SELECT c.*, v.number AS volume_number, v.title AS volume_title
        FROM chapters c
        JOIN volumes v ON c.volume_id = v.id
        JOIN books b ON v.book_id = b.id
        WHERE b.project_id=? AND c.status='accepted'
        ORDER BY v.number, c.number
        """,
        (project_id,),
    )
    for c in chapters:
        c["content"] = _read_resource(conn, c["content_resource_id"])

    # 卷号/标题映射（volume_outline / chapter_plan 的 scope_ref 是 volume:{id}）
    volumes_by_id = {
        v["id"]: v
        for v in _rows(
            conn,
            """SELECT v.* FROM volumes v JOIN books b ON v.book_id=b.id WHERE b.project_id=?""",
            (project_id,),
        )
    }

    # 实体
    characters = _rows(conn, "SELECT * FROM characters WHERE project_id=? ORDER BY name", (project_id,))
    for ch in characters:
        if ch.get("description_resource_id"):
            ch["description"] = _read_resource(conn, ch["description_resource_id"])
    worlds = _rows(conn, "SELECT * FROM worlds WHERE project_id=? ORDER BY name", (project_id,))
    for w in worlds:
        if w.get("description_resource_id"):
            w["description"] = _read_resource(conn, w["description_resource_id"])

    # 连续性账本
    continuity = {
        "narrative_promises": _rows(
            conn, "SELECT * FROM narrative_promises WHERE project_id=? ORDER BY id", (project_id,)
        ),
        "expectation_ledgers": _rows(
            conn, "SELECT * FROM expectation_ledgers WHERE project_id=? ORDER BY id", (project_id,)
        ),
        "relationship_states": _rows(
            conn, "SELECT * FROM relationship_states WHERE project_id=? ORDER BY id", (project_id,)
        ),
        "arc_states": _rows(
            conn, "SELECT * FROM arc_states WHERE project_id=? ORDER BY id", (project_id,)
        ),
        "timelines": _rows(
            conn, "SELECT * FROM timelines WHERE project_id=? ORDER BY sequence, label", (project_id,)
        ),
        "chapter_facts": _rows(
            conn,
            "SELECT * FROM chapter_facts WHERE project_id=? AND status='accepted' ORDER BY id",
            (project_id,),
        ),
    }

    # active 创作种子
    seed = _row(conn, "SELECT * FROM creation_seeds WHERE project_id=? AND is_active=1", (project_id,))

    # 权威快照 hash（只覆盖权威内容，确定性可重现）
    snapshot_payload = {
        "project": project,
        "creator_signature": creator_signature,
        "book_soul": book_soul,
        "planning_assets": {k: v["content"] for k, v in planning.items()},
        "chapters": [{"id": c["id"], "content": c["content"]} for c in chapters],
    }
    authority_snapshot_hash = content_hash(json.dumps(snapshot_payload, sort_keys=True, ensure_ascii=False))

    return {
        "project": project,
        "creator_signature": creator_signature,
        "book_soul": book_soul,
        "planning": planning,
        "volume_outlines": volume_outlines,
        "chapter_plans": chapter_plans,
        "chapters": chapters,
        "volumes_by_id": volumes_by_id,
        "characters": characters,
        "worlds": worlds,
        "continuity": continuity,
        "seed": seed,
        "authority_snapshot_hash": authority_snapshot_hash,
    }


# --------------------------------------------------------------------------- #
# 渲染层
# --------------------------------------------------------------------------- #

_SIGNATURE_LABELS = {
    "sympathies": "天然同情",
    "distrusts": "持续警惕",
    "recurring_attention": "反复关注",
    "narrative_principles": "叙事原则",
    "forbidden_conveniences": "禁止的便利解法",
    "expression_preferences": "表达偏好",
    "negative_constraints": "负面约束",
}
_SOUL_LABELS = {
    "unresolved_claims": "未决追问",
    "central_contradiction": "核心矛盾",
    "costly_commitments": "有代价的承诺",
    "protected_dignity": "受保护的尊严",
    "forbidden_resolutions": "禁止的解决方式",
    "recurring_tests": "重复检验",
    "narrative_mercy": "叙事仁慈",
    "narrative_cruelty": "叙事残酷",
    "deliberate_silences": "刻意留白",
}
_PLANNING_MAP = {
    "direction": "01-故事方向.md",
    "architecture": "02-故事架构.md",
    "strategy": "03-全书战略.md",
    "world_contract": "05-世界契约.md",
    "story_arc": "06-故事弧.md",
}
# character_contract 不走 _PLANNING_MAP 单文件，改由 _split_character_contract
# 拆成「人物契约/」目录（00-总览 + 每人物一份），见 render() E2 段。

# 人物档案二级标题：## 人物档案：{角色}｜{名字}（兼容中英冒号与中英竖线）。
_CHARACTER_HEADING = re.compile(r"^##\s+人物档案[:：]\s*(.+?)\s*[|｜]\s*(.+?)\s*$")
_H2_HEADING = re.compile(r"^##\s")


def _split_character_contract(content: str) -> dict[str, Any] | None:
    """按「## 人物档案：角色｜名字」把人物契约拆成总览 + 各人物。

    返回 ``{"overview": str, "characters": [{"role","name","body"}]}``，
    ``body`` 含该人物的标题行及其下全部内容（到下一个二级标题前）。
    非人物档案的二级标题段与文档顶部内容归入 ``overview``。
    主角（角色含「主角」）排第一，其余按出现顺序。

    识别不到任何人物档案标题时返回 ``None``，调用方据此走单文件兜底。
    """
    # 按 H2 把文档切成段：首段标题为 None（文档顶部），其余为该 H2 标题行。
    segments: list[tuple[list[str], list[str]]] = [([], [])]
    for line in content.splitlines():
        if _H2_HEADING.match(line):
            segments.append(([line], []))
        else:
            segments[-1][1].append(line)

    overview_parts: list[str] = []
    characters: list[dict[str, str]] = []
    for title_lines, body_lines in segments:
        title_line = title_lines[0] if title_lines else None
        body = "\n".join([*title_lines, *body_lines]).strip()
        match = _CHARACTER_HEADING.match(title_line) if title_line else None
        if match:
            characters.append(
                {"role": match.group(1).strip(), "name": match.group(2).strip(), "body": body}
            )
        elif body:
            overview_parts.append(body)

    if not characters:
        return None

    protagonists = [c for c in characters if "主角" in c["role"]]
    others = [c for c in characters if "主角" not in c["role"]]
    return {"overview": "\n\n".join(overview_parts).strip(), "characters": protagonists + others}


def render(snapshot: dict[str, Any], project_id: str, output_root: str) -> dict[str, Any]:
    project = snapshot["project"]
    project_title = project.get("name") or project.get("title") or "Untitled"
    project_version = project["version"]
    authority_hash = snapshot["authority_snapshot_hash"]

    root_dir = Path(output_root).resolve()
    dir_name = sanitize_filename(project_title, default=f"project_{project_id}")
    target_dir = (root_dir / dir_name).resolve()
    try:
        target_dir.relative_to(root_dir)
    except ValueError as exc:
        raise SystemExit(f"目标渲染路径超出许可根目录范围: {target_dir}") from exc

    # 目标目录归属校验（防覆盖其他项目）
    if target_dir.exists():
        manifest_file = target_dir / "manifest.json"
        if manifest_file.is_file():
            try:
                old = json.loads(manifest_file.read_text(encoding="utf-8"))
                if old.get("project_id") and old["project_id"] != project_id:
                    raise SystemExit(
                        f"目标目录已存在且属于其他项目 {old['project_id']}，拒绝覆盖"
                    )
            except json.JSONDecodeError:
                pass

    root_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = root_dir / f".tmp_{dir_name}_{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    files_manifest: list[dict[str, Any]] = []

    def write_markdown(rel_path: str, title: str, body: str, source: dict[str, Any]) -> None:
        safe_parts = [sanitize_filename(p) for p in rel_path.split("/")]
        rel = Path(*safe_parts)
        abs_path = tmp_dir / rel
        try:
            abs_path.resolve().relative_to(tmp_dir.resolve())
        except ValueError as exc:
            raise SystemExit(f"渲染路径非法逃逸: {rel}") from exc
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        text = f"# {title}\n\n{body}\n" if title else f"{body}\n"
        data = text.encode("utf-8")
        abs_path.write_bytes(data)
        digest = content_hash(data)
        files_manifest.append(
            {
                "relative_path": rel.as_posix(),
                "sha256": digest,
                "source_type": source.get("source_type", "derived"),
                "source_id": source.get("source_id", ""),
                "source_version": source.get("source_version", 1),
                "source_hash": source.get("source_hash") or digest,
            }
        )

    # A. README
    readme_body = (
        f"此文件夹为 NovelOS 项目《{project_title}》派生的用户只读投影。\n\n"
        "> [!IMPORTANT]\n"
        "> **只读提示**：本目录由权威数据库单向渲染，可随时安全删除并重新生成。"
        "直接修改其中 Markdown 文件**不会回写**数据库。\n\n"
        f"- **项目 ID**：`{project_id}`\n"
        f"- **项目版本**：`v{project_version}`\n"
        f"- **权威快照 Hash**：`{authority_hash}`\n"
    )
    write_markdown("README.md", f"《{project_title}》项目展示视图", readme_body,
                   {"source_type": "project_readme", "source_id": project_id})

    # B. 创作约束/作者签名
    creator = snapshot["creator_signature"]
    if creator:
        sig = creator["signature"]
        lines = [
            f"- **Profile**：{creator['profile_display_name']} (`{creator['profile_id']}`)",
            f"- **版本**：revision {creator['profile_revision']} (`{creator['profile_version_id']}`)",
            f"- **Hash**：`{creator['subject_hash']}`",
            f"- **绑定模式**：`{creator['binding_mode']}`",
        ]
        for field, label in _SIGNATURE_LABELS.items():
            lines.extend(["", f"## {label}"])
            lines.extend(f"- {item}" for item in sig.get(field, []))
        body = "\n".join(lines)
        src = {"source_type": "creator_signature", "source_id": creator["profile_version_id"],
               "source_version": creator["profile_revision"], "source_hash": creator["subject_hash"]}
    else:
        body = "*当前项目尚未绑定 Creator Profile。*"
        src = {"source_type": "creator_signature_absent", "source_id": project_id}
    write_markdown("创作约束/作者签名.md", "作者签名", body, src)

    # C. 创作约束/本书创作灵魂
    soul = snapshot["book_soul"]
    if soul:
        sv = soul["book_soul"]
        lines = [
            f"- **Direction**：`{soul['direction_id']}`，version {soul['direction_version']}",
            f"- **Hash**：`{soul['direction_subject_hash']}`",
        ]
        for field, label in _SOUL_LABELS.items():
            lines.extend(["", f"## {label}"])
            value = sv.get(field)
            if isinstance(value, list):
                lines.extend(f"- {item}" for item in value)
            else:
                lines.append(str(value) if value is not None else "")
        body = "\n".join(lines)
        src = {"source_type": "book_soul", "source_id": soul["direction_id"],
               "source_version": soul["direction_version"], "source_hash": soul["direction_subject_hash"]}
    else:
        body = "*当前没有包含有效 `book_soul` 的 locked Story Direction。*"
        src = {"source_type": "book_soul_absent", "source_id": project_id}
    write_markdown("创作约束/本书创作灵魂.md", "本书创作灵魂", body, src)

    # D. 创作约束/创作种子
    seed = snapshot["seed"]
    if seed:
        body = "\n".join([
            f"- **版本**：v{seed['version']}",
            "", "## 主角雏形", seed["protagonist_seed"] or "*（未填写）*",
            "", "## 世界感觉", seed["world_seed"] or "*（未填写）*",
            "", "## 爽点偏好", seed["hook_seed"] or "*（未填写）*",
            "", "## 其他备注", seed["notes"] or "*（未填写）*",
        ])
        src = {"source_type": "creation_seed", "source_id": seed["id"], "source_version": seed["version"]}
    else:
        body = "*当前项目尚未填写创作种子。*"
        src = {"source_type": "creation_seed_absent", "source_id": project_id}
    write_markdown("创作约束/创作种子.md", "创作种子", body, src)

    # E. 规划/（locked 资产，character_contract 除外——见 E2）
    planning = snapshot["planning"]
    for asset_type, filename in _PLANNING_MAP.items():
        asset = planning.get(asset_type)
        if asset:
            write_markdown(
                f"规划/{filename}", f"规划：{asset_type}", asset["content"],
                {"source_type": "planning_asset", "source_id": asset["id"],
                 "source_version": asset["version"], "source_hash": asset.get("subject_hash", "")},
            )

    # E2. 人物契约特殊渲染：按「## 人物档案：角色｜名字」拆成 规划/人物契约/ 目录。
    # 识别不到该结构（如尚未按新约定整理的残缺契约）时退化为单文件并警告。
    cc = planning.get("character_contract")
    if cc:
        cc_source = {"source_type": "planning_asset", "source_id": cc["id"],
                     "source_version": cc["version"], "source_hash": cc.get("subject_hash", "")}
        split = _split_character_contract(cc["content"])
        if split is None:
            print(
                "警告: character_contract 未按「## 人物档案：角色｜名字」结构组织，"
                "退化为单文件 规划/04-人物契约.md",
                file=sys.stderr,
            )
            write_markdown("规划/04-人物契约.md", "规划：character_contract", cc["content"], cc_source)
        else:
            write_markdown(
                "规划/人物契约/00-总览.md", "人物契约·总览", split["overview"], cc_source
            )
            for idx, ch in enumerate(split["characters"]):
                nn = f"{idx + 1:02d}"
                fname = (
                    f"规划/人物契约/{nn}-{sanitize_filename(ch['role'])}"
                    f"-{sanitize_filename(ch['name'])}.md"
                )
                write_markdown(fname, f"{ch['role']}｜{ch['name']}", ch["body"], cc_source)

    # F. 大纲/（卷纲 + 章纲）
    volumes_by_id = snapshot["volumes_by_id"]
    for vol in snapshot["volume_outlines"]:
        scope = vol.get("scope_ref", "")
        vid = scope.split(":", 1)[1] if scope.startswith("volume:") else scope
        vol_row = volumes_by_id.get(vid, {})
        v_num = int(vol_row.get("number", 1) or 1)
        v_cn = cn_num(v_num)
        v_title = vol_row.get("title") or vol.get("title") or f"第{v_cn}卷"
        write_markdown(
            f"大纲/第{v_cn}卷/卷纲.md", f"第 {v_cn} 卷卷纲：{v_title}", vol.get("content", ""),
            {"source_type": "volume_outline", "source_id": vol["id"],
             "source_version": vol["version"], "source_hash": vol.get("subject_hash", "")},
        )
    for plan in snapshot["chapter_plans"]:
        scope = plan.get("scope_ref", "")
        chap_match = re.search(r":chapter_(\d+)$", scope)
        if not chap_match:
            continue
        c_num = int(chap_match.group(1))
        vol_match = re.match(r"^(volume:[^:]+):", scope)
        v_num = 1
        if vol_match:
            vid = vol_match.group(1)
            v_num = int(volumes_by_id.get(vid, {}).get("number", 1) or 1)
        v_cn = cn_num(v_num)
        c_title = plan.get("title", f"第{c_num:03d}章")
        write_markdown(
            f"大纲/第{v_cn}卷/第{c_num:03d}章-章纲.md",
            f"第 {v_cn} 卷第 {c_num} 章执行卡：{c_title}",
            plan.get("content", ""),
            {"source_type": "chapter_plan", "source_id": plan["id"],
             "source_version": plan["version"], "source_hash": plan.get("subject_hash", "")},
        )

    # G. 正文/（accepted 章节）
    for ch in snapshot["chapters"]:
        v_num = int(ch.get("volume_number") or 1)
        v_cn = cn_num(v_num)
        c_num = int(ch.get("number") or 1)
        c_title = sanitize_filename(ch.get("title", "未命名章节"))
        write_markdown(
            f"正文/第{v_cn}卷/第{c_num:03d}章-{c_title}.md",
            ch.get("title", f"第 {c_num} 章"),
            ch.get("content", ""),
            {"source_type": "chapter", "source_id": ch["id"],
             "source_version": ch.get("version", 1), "source_hash": ch.get("subject_hash", "")},
        )

    # H. 人物/ & 世界/
    for char in snapshot["characters"]:
        name = sanitize_filename(char["name"])
        body = f"**描述**：{char.get('description', '')}\n\n**状态**：{char.get('state_json', '')}"
        write_markdown(f"人物/{name}.md", char["name"], body,
                       {"source_type": "character", "source_id": char["id"], "source_version": char["version"]})
    for world in snapshot["worlds"]:
        name = sanitize_filename(world["name"])
        body = f"**设定**：{world.get('description', '')}\n\n**状态**：{world.get('state_json', '')}"
        write_markdown(f"世界/{name}.md", world["name"], body,
                       {"source_type": "world", "source_id": world["id"], "source_version": world["version"]})

    # I. 连续性/账本
    cont_files = [
        ("伏笔与叙事承诺.md", "叙事承诺账本", "narrative_promises"),
        ("读者期待.md", "读者期待账本", "expectation_ledgers"),
        ("人物关系.md", "人物关系状态", "relationship_states"),
        ("故事弧状态.md", "故事弧状态账本", "arc_states"),
        ("时间线.md", "时间线账本", "timelines"),
        ("正文事实.md", "正文事实与逻辑账本", "chapter_facts"),
    ]
    for fname, title, key in cont_files:
        data = snapshot["continuity"].get(key, [])
        body = json.dumps(data, indent=2, ensure_ascii=False) if data else "*尚无相关记录*"
        write_markdown(f"连续性/{fname}", title, body,
                       {"source_type": "continuity_ledger", "source_id": fname})

    # J. manifest.json
    manifest_payload = {
        "projection_format_version": PROJECTION_FORMAT_VERSION,
        "project_id": project_id,
        "project_title": project_title,
        "project_version": project_version,
        "authority_snapshot_hash": authority_hash,
        "generator_version": GENERATOR_VERSION,
        "file_count": len(files_manifest),
        "files": sorted(files_manifest, key=lambda x: x["relative_path"]),
    }
    (tmp_dir / "manifest.json").write_bytes(
        json.dumps(manifest_payload, indent=2, ensure_ascii=False).encode("utf-8")
    )

    # 原子替换
    if target_dir.exists():
        shutil.rmtree(target_dir)
    tmp_dir.rename(target_dir)

    return {
        "project_id": project_id,
        "project_title": project_title,
        "output_directory": str(target_dir),
        "authority_snapshot_hash": authority_hash,
        "rendered_file_count": len(files_manifest) + 1,
    }


def verify_manifest(project_directory: str) -> dict[str, Any]:
    """逐文件校验 manifest：重算 SHA-256 比对。"""
    project_path = Path(project_directory)
    manifest_path = project_path / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"目标目录缺少 manifest.json: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    verified = 0
    for entry in manifest.get("files", []):
        rel = entry.get("relative_path", "")
        fp = project_path / rel
        try:
            fp.resolve().relative_to(project_path.resolve())
        except ValueError:
            errors.append(f"路径逃逸: {rel}")
            continue
        if not fp.is_file():
            errors.append(f"缺失文件: {rel}")
            continue
        if content_hash(fp.read_bytes()) != entry.get("sha256", ""):
            errors.append(f"SHA-256 不匹配: {rel}")
        verified += 1
    return {"verified_file_count": verified, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description="渲染 NovelOS 项目投影（裸 sqlite3）")
    parser.add_argument("--project", required=True, help="项目 ID (如 project:xxx)")
    parser.add_argument("--output", default="novels", help="输出根目录 (default: novels)")
    parser.add_argument("--db", default="data/novelos-v2.db", help="数据库路径")
    parser.add_argument("--verify", action="store_true", help="渲染后校验 manifest")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        snapshot = load_snapshot(conn, args.project)
        result = render(snapshot, args.project, args.output)
        print(f"渲染完成: {result['output_directory']}")
        print(f"文件数: {result['rendered_file_count']}")
        print(f"权威快照 Hash: {result['authority_snapshot_hash']}")
        if args.verify:
            vr = verify_manifest(result["output_directory"])
            if vr["errors"]:
                print(f"校验失败 ({len(vr['errors'])} 项):")
                for e in vr["errors"]:
                    print(f"  - {e}")
            else:
                print(f"manifest 校验通过: {vr['verified_file_count']} 个文件")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
