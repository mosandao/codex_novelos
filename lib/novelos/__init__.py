"""NovelOS 轻量纯逻辑库。

从已退役的 NovelOS MCP 中提取的、被确定性脚本（reconcile / validate_book_soul 等）
依赖的零数据库纯逻辑：作者签名校验、原型打分、多原型确定性融合、系统原型加载。

本包不连接数据库、不调用 LLM，是零外部依赖的纯逻辑库（从已退役的 MCP 代码中提取）。
所有 schema 与原型配置仍读自顶层 ``config/schemas/`` 与 ``config/system_archetypes.json``。
"""

from .errors import NovelOSError
from .hashing import content_hash
from ._helpers import _id, _json, _require_sha256, _require_text
from .contracts import CreativeContractStore, SIGNATURE_FIELDS
from .archetype_recommendation import (
    GENRE_TEMPERAMENT_MAP,
    TONE_TEMPERAMENT_MAP,
    recommend_archetypes,
    generate_derivation_draft,
)
from .system_archetypes import load_system_archetypes_config
from .reconcile import reconcile_project_wizard_archetypes

__all__ = [
    "NovelOSError",
    "content_hash",
    "_id",
    "_json",
    "_require_sha256",
    "_require_text",
    "CreativeContractStore",
    "SIGNATURE_FIELDS",
    "GENRE_TEMPERAMENT_MAP",
    "TONE_TEMPERAMENT_MAP",
    "recommend_archetypes",
    "generate_derivation_draft",
    "load_system_archetypes_config",
    "reconcile_project_wizard_archetypes",
]
