from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

import jsonschema

from novelos_mcp.errors import NovelOSError


SIGNATURE_FIELDS = frozenset(
    {
        "sympathies",
        "distrusts",
        "recurring_attention",
        "narrative_principles",
        "forbidden_conveniences",
        "expression_preferences",
        "negative_constraints",
    }
)

# A signature may prohibit imitation, but it cannot preserve an instruction to
# imitate a named or otherwise identifiable author's style.
_AUTHOR_IMITATION_TERMS = ("模仿", "仿写", "复刻", "照搬", "复现", "临摹")
_NEGATION_TERMS = ("不", "勿", "别", "禁止", "避免", "拒绝", "不要", "不得", "杜绝", "抵制", "反对")


def _default_schema_root() -> Path:
    candidates = (
        Path.cwd() / "config" / "schemas",
        Path(__file__).resolve().parents[4] / "config" / "schemas",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise NovelOSError(
        "configuration_error",
        "找不到创作约束 Schema",
        {"candidates": [str(candidate) for candidate in candidates]},
    )


class CreativeContractStore:
    def __init__(self, schema_root: str | Path | None = None) -> None:
        root = Path(schema_root) if schema_root is not None else _default_schema_root()
        try:
            signature_schema = json.loads((root / "creator-signature.schema.json").read_text(encoding="utf-8"))
            soul_schema = json.loads((root / "book-soul.schema.json").read_text(encoding="utf-8"))
            chapter_soul_schema = json.loads((root / "chapter-soul-contract.schema.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise NovelOSError("configuration_error", "创作约束 Schema 无法读取", {"root": str(root)}) from exc
        self.signature_validator = jsonschema.Draft202012Validator(signature_schema)
        self.book_soul_validator = jsonschema.Draft202012Validator(soul_schema)
        self.chapter_soul_validator = jsonschema.Draft202012Validator(chapter_soul_schema)

    def validate_signature(self, value: Any) -> dict[str, Any]:
        normalized = self._validate(self.signature_validator, value, "invalid_creator_signature", "作者签名")
        self._reject_positive_author_imitation(normalized)
        return normalized

    def validate_book_soul(self, value: Any) -> dict[str, Any]:
        return self._validate(self.book_soul_validator, value, "invalid_book_soul", "书级创作灵魂")

    def validate_chapter_soul(self, value: Any) -> dict[str, Any]:
        return self._validate(
            self.chapter_soul_validator,
            value,
            "invalid_chapter_soul_contract",
            "章节思想压力契约",
        )

    def derive_signature(self, base: dict[str, Any], overrides: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        self.validate_signature(base)
        if not isinstance(overrides, dict) or not overrides:
            raise NovelOSError("invalid_creator_signature", "派生作者签名必须提供至少一个显式差异")
        invalid = sorted(set(overrides) - SIGNATURE_FIELDS)
        if invalid:
            raise NovelOSError(
                "invalid_creator_signature",
                "派生作者签名包含越界字段",
                {"fields": invalid},
            )
        materialized = copy.deepcopy(base)
        materialized.update(copy.deepcopy(overrides))
        self.validate_signature(materialized)
        unchanged = sorted(key for key in overrides if overrides[key] == base[key])
        if unchanged:
            raise NovelOSError(
                "invalid_creator_signature",
                "派生差异不得重复父版本原值",
                {"fields": unchanged},
            )
        return materialized, copy.deepcopy(overrides)

    @staticmethod
    def _validate(
        validator: jsonschema.Draft202012Validator,
        value: Any,
        code: str,
        label: str,
    ) -> dict[str, Any]:
        try:
            validator.validate(value)
        except jsonschema.ValidationError as exc:
            raise NovelOSError(code, f"{label}不符合 Schema", {"path": list(exc.path)}) from exc
        return copy.deepcopy(value)

    @staticmethod
    def _reject_positive_author_imitation(signature: dict[str, Any]) -> None:
        """Keep an explicit ban on imitation from becoming a stored imitation target."""
        for field in SIGNATURE_FIELDS:
            for index, statement in enumerate(signature[field]):
                for clause in re.split(r"[。；;，,、]", statement):
                    if not any(term in clause for term in _AUTHOR_IMITATION_TERMS):
                        continue
                    if any(negation in clause for negation in _NEGATION_TERMS):
                        continue
                    raise NovelOSError(
                        "invalid_creator_signature",
                        "作者签名不得保存具体作者模仿指令",
                        {"field": field, "index": index},
                    )


def creator_signature_ref(profile_id: str, revision: int, version_id: str, subject_hash: str) -> str:
    return "novelos://creator-signature/{}/{}/{}/{}".format(
        quote(profile_id, safe=""),
        revision,
        quote(version_id, safe=""),
        quote(subject_hash, safe=""),
    )


def parse_creator_signature_ref(value: str) -> dict[str, Any]:
    try:
        parsed = urlparse(value)
        parts = parsed.path.strip("/").split("/")
        if parsed.scheme != "novelos" or parsed.netloc != "creator-signature" or len(parts) != 4:
            raise ValueError
        revision = int(parts[1])
        if revision < 1:
            raise ValueError
        profile_id = unquote(parts[0])
        version_id = unquote(parts[2])
        subject_hash = unquote(parts[3])
        if not profile_id.startswith("creator-profile:") or not version_id.startswith("creator-profile-version:"):
            raise ValueError
        if len(subject_hash) != 71 or not subject_hash.startswith("sha256:"):
            raise ValueError
    except (AttributeError, TypeError, ValueError) as exc:
        raise NovelOSError("invalid_creator_signature_ref", "作者签名引用格式非法") from exc
    return {
        "profile_id": profile_id,
        "revision": revision,
        "profile_version_id": version_id,
        "subject_hash": subject_hash,
    }


def planning_constraint_ref(asset_id: str, version: int, subject_hash: str) -> str:
    return "novelos://planning-constraint/{}/{}/{}".format(
        quote(asset_id, safe=""),
        version,
        quote(subject_hash, safe=""),
    )
