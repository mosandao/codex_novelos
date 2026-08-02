from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from novelos_mcp.creative_contracts import CreativeContractStore
from novelos_mcp.errors import NovelOSError
from novelos_mcp.hashing import content_hash


def _default_config_path() -> Path:
    candidates = (
        Path.cwd() / "config" / "system_archetypes.json",
        Path(__file__).resolve().parents[3] / "config" / "system_archetypes.json",
        Path(__file__).resolve().parents[4] / "config" / "system_archetypes.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise NovelOSError(
        "configuration_error",
        "找不到系统叙事原型配置文件",
        {"candidates": [str(c) for c in candidates]},
    )



def load_system_archetypes_config(config_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(config_path) if config_path is not None else _default_config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NovelOSError("configuration_error", "系统叙事原型配置无法读取", {"path": str(path)}) from exc

    if not isinstance(data, list) or len(data) != 18:
        raise NovelOSError("configuration_error", "系统叙事原型必须包含 18 个预设定义", {"count": len(data) if isinstance(data, list) else 0})

    store = CreativeContractStore()
    validated: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict) or "id" not in item or "signature" not in item:
            raise NovelOSError("configuration_error", "系统叙事原型格式非法")
        sig = store.validate_signature(item["signature"])
        expected_hash = content_hash(json.dumps(sig, sort_keys=True, ensure_ascii=False))
        if item.get("subject_hash") != expected_hash:
            raise NovelOSError(
                "configuration_error",
                "系统叙事原型 subject_hash 不匹配",
                {"id": item["id"], "expected": expected_hash, "actual": item.get("subject_hash")},
            )
        entry = dict(item)
        entry["signature"] = sig
        entry["subject_hash"] = expected_hash
        entry["ownership"] = "system_archetype"
        validated.append(entry)

    return validated


def sync_system_archetypes_to_db(connection: sqlite3.Connection, archetypes: list[dict[str, Any]]) -> None:
    """
    保证 18 个系统叙事原型在数据库中初始化/同步为 ownership='system_archetype' 资源。
    同时向 resources、creator_profiles、creator_profile_versions 插入必要记录。
    """
    for archetype in archetypes:
        profile_id = f"creator-profile:{archetype['id']}"
        version_id = f"creator-profile-version:{archetype['id']}:1"
        display_name = archetype["display_name"]
        subject_hash = archetype["subject_hash"]
        signature_json = json.dumps(archetype["signature"], indent=2, ensure_ascii=False)
        content_res_id = f"resource:creator-signature:{archetype['id']}:1"

        # 1. 检查资源或插入资源
        res_row = connection.execute("SELECT id FROM resources WHERE id=?", (content_res_id,)).fetchone()
        if not res_row:
            connection.execute(
                "INSERT INTO resources(id, media_type, content, content_hash) VALUES (?, ?, ?, ?)",
                (content_res_id, "application/json", signature_json.encode("utf-8"), subject_hash),
            )


        # 2. 检查或插入 creator_profiles
        prof_row = connection.execute("SELECT id FROM creator_profiles WHERE id=?", (profile_id,)).fetchone()
        if not prof_row:
            connection.execute(
                "INSERT INTO creator_profiles(id, display_name, status, version, ownership) VALUES (?, ?, 'active', 1, 'system_archetype')",
                (profile_id, display_name),
            )
        else:
            # 升级已有的记录为 system_archetype (若旧版本库中尚无 ownership 列)
            connection.execute(
                "UPDATE creator_profiles SET ownership='system_archetype', display_name=? WHERE id=?",
                (display_name, profile_id),
            )

        # 3. 检查或插入 creator_profile_versions
        ver_row = connection.execute("SELECT id FROM creator_profile_versions WHERE id=?", (version_id,)).fetchone()
        if not ver_row:
            connection.execute(
                "INSERT INTO creator_profile_versions(id, profile_id, revision, content_resource_id, subject_hash) VALUES (?, ?, 1, ?, ?)",
                (version_id, profile_id, content_res_id, subject_hash),
            )
