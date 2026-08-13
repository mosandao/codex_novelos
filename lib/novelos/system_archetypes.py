from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import CreativeContractStore
from .errors import NovelOSError
from .hashing import content_hash


def _default_config_path() -> Path:
    candidates = (
        Path.cwd() / "config" / "system_archetypes.json",
        Path(__file__).resolve().parents[2] / "config" / "system_archetypes.json",
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
    """加载并校验 18 个系统叙事原型；返回带 signature/subject_hash/ownership 的 list。"""
    path = Path(config_path) if config_path is not None else _default_config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NovelOSError("configuration_error", "系统叙事原型配置无法读取", {"path": str(path)}) from exc

    if not isinstance(data, list) or len(data) != 18:
        raise NovelOSError(
            "configuration_error",
            "系统叙事原型必须包含 18 个预设定义",
            {"count": len(data) if isinstance(data, list) else 0},
        )

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
