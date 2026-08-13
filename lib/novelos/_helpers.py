import json
import uuid
from typing import Any

from .errors import NovelOSError


def _id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4()}"


def _json(value: dict[str, Any] | list[Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _require_text(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise NovelOSError("invalid_argument", f"{field} 必须是字符串", {"field": field})
    normalized = value.strip()
    if not normalized:
        raise NovelOSError("invalid_argument", f"{field} 不能为空", {"field": field})
    return normalized


def _require_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise NovelOSError(
            "invalid_argument",
            f"{field} 必须是 sha256: 格式的 64 位十六进制字符串",
            {"field": field},
        )
    return value
