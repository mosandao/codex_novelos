from __future__ import annotations

from typing import Any

from ._helpers import _require_sha256, _require_text
from .archetype_recommendation import generate_derivation_draft, recommend_archetypes
from .contracts import SIGNATURE_FIELDS, CreativeContractStore
from .errors import NovelOSError


def reconcile_project_wizard_archetypes(
    selected_archetypes: list[dict[str, Any]],
    project_setup: dict[str, Any],
    display_name: str,
    archetypes_config: list[dict[str, Any]],
    creative_contracts: CreativeContractStore,
    fused_parent_version_id: str | None = None,
    fused_signature: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """把项目向导产出的多原型选择融合成合规的单 parent derive 结构（纯读不写）。

    两条路径：
    - 单原型 / 默认（``fused_*`` 均缺省）：用 ``recommend_archetypes`` 在选中子集内打分
      确定 parent，用 ``generate_derivation_draft`` 生成基础 overrides，再把其余选中
      原型的 ``reader_promise`` 追加到 ``recurring_attention`` 作为辅风格融合。
    - 多原型 LLM 融合（``fused_*`` 同传）：parent 由 onboarding_agent 判定，通过
      ``fused_parent_version_id`` 传入，``fused_signature`` 是深度融合后的完整签名。
      本函数跳过打分，直接把完整签名折算成相对 parent 的 overrides diff。

    最后都用 ``derive_signature`` 预校验合并签名合法。返回值带 ``parent_source``
    （``"scored"`` 或 ``"fused"``）。
    """
    normalized_name = _require_text(display_name, "display_name")
    if not isinstance(selected_archetypes, list) or not selected_archetypes:
        raise NovelOSError(
            "invalid_project_setup",
            "selected_archetypes 必须是非空数组",
        )

    # fused 入参必须同传同缺：只给一个会被拒。
    if (fused_parent_version_id is None) != (fused_signature is None):
        raise NovelOSError(
            "invalid_project_setup",
            "fused_parent_version_id 与 fused_signature 必须同时提供或同时缺省",
        )

    # 1. 反查每个选中原型并校验 subject_hash 与 config 一致。
    resolved: list[dict[str, Any]] = []
    for entry in selected_archetypes:
        if not isinstance(entry, dict):
            raise NovelOSError("invalid_project_setup", "selected_archetypes 项必须是对象")
        version_id = _require_text(entry.get("profile_version_id"), "profile_version_id")
        parts = version_id.split(":")
        # 期望格式 creator-profile-version:{archetype_id}:{revision}
        if len(parts) < 3 or parts[0] != "creator-profile-version":
            raise NovelOSError(
                "invalid_project_setup",
                "profile_version_id 格式非法",
                {"value": version_id},
            )
        archetype_id = ":".join(parts[1:-1])
        revision = parts[-1]
        match = next((a for a in archetypes_config if a["id"] == archetype_id), None)
        if match is None:
            raise NovelOSError(
                "invalid_project_setup",
                "找不到选中的系统叙事原型",
                {"profile_version_id": version_id},
            )
        subject_hash = _require_sha256(entry.get("subject_hash"), "subject_hash")
        if subject_hash != match["subject_hash"]:
            raise NovelOSError(
                "hash_mismatch",
                "选中原型的 subject_hash 与配置不一致",
                {"profile_version_id": version_id},
            )
        resolved.append(
            {
                **match,
                "profile_version_id": f"creator-profile-version:{archetype_id}:{revision}",
                "user_display_name": _require_text(entry.get("display_name"), "display_name"),
            }
        )

    # 2. 确定 parent 与 overrides。
    if fused_parent_version_id is not None and fused_signature is not None:
        parent, overrides, parent_source = _reconcile_fused(
            resolved, fused_parent_version_id, fused_signature, creative_contracts
        )
    else:
        parent, overrides, parent_source = _reconcile_scored(resolved, project_setup)

    if not overrides:
        raise NovelOSError(
            "invalid_creator_signature",
            "融合后未产生任何作者签名差异",
        )

    # 3. 预校验合并签名合法（overrides 是相对 parent 的真实 diff 且字段合法）。
    creative_contracts.derive_signature(parent["signature"], overrides)

    secondary_names = [a["display_name"] for a in resolved if a["id"] != parent["id"]]
    return {
        "creator": {
            "mode": "derive",
            "parent_version_id": parent["profile_version_id"],
            "parent_subject_hash": parent["subject_hash"],
            "display_name": normalized_name,
            "overrides": overrides,
        },
        "parent_archetype": {
            "id": parent["id"],
            "display_name": parent["display_name"],
            "reader_promise": parent.get("reader_promise", ""),
        },
        "merged_secondary_archetypes": secondary_names,
        "parent_source": parent_source,
    }


def _reconcile_scored(
    resolved: list[dict[str, Any]],
    project_setup: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, list[str]], str]:
    """单原型路径：打分选 parent + generate_derivation_draft + 辅风格融合。"""
    creation_context = project_setup.get("creation_context", {}) if isinstance(project_setup, dict) else {}
    taxonomy = project_setup.get("taxonomy", {}) if isinstance(project_setup, dict) else {}
    primary_genre = creation_context.get("primary_genre", "")
    secondary_directions = creation_context.get("secondary_directions", [])
    emotional_tones = taxonomy.get("emotional_tones", [])
    aesthetic_styles = taxonomy.get("aesthetic_styles", [])
    ranked_ids = recommend_archetypes(
        primary_genre,
        secondary_directions,
        emotional_tones,
        aesthetic_styles,
        resolved,
    )
    parent = next(a for a in resolved if a["id"] == ranked_ids[0])
    overrides = generate_derivation_draft(parent, project_setup)

    merged_promises: list[str] = []
    for archetype in resolved:
        if archetype["id"] == parent["id"]:
            continue
        promise = archetype.get("reader_promise", "").strip()
        if promise:
            merged_promises.append(f"参考《{archetype['display_name']}》的辅风格：{promise}")
    if merged_promises:
        existing = list(
            overrides.get(
                "recurring_attention",
                list(parent["signature"].get("recurring_attention", [])),
            )
        )
        for item in merged_promises:
            if item not in existing:
                existing.append(item)
        overrides["recurring_attention"] = existing
    return parent, overrides, "scored"


def _reconcile_fused(
    resolved: list[dict[str, Any]],
    fused_parent_version_id: str,
    fused_signature: dict[str, Any],
    creative_contracts: CreativeContractStore,
) -> tuple[dict[str, Any], dict[str, list[str]], str]:
    """多原型路径：用 Agent 判定的 parent，把完整融合签名折算成 overrides diff。"""
    parent = next(
        (a for a in resolved if a["profile_version_id"] == fused_parent_version_id),
        None,
    )
    if parent is None:
        raise NovelOSError(
            "invalid_project_setup",
            "fused_parent_version_id 必须是已选中的原型之一",
            {"fused_parent_version_id": fused_parent_version_id},
        )
    if not isinstance(fused_signature, dict):
        raise NovelOSError(
            "invalid_project_setup",
            "fused_signature 必须是对象",
        )
    base_signature = parent["signature"]

    # 先校验融合签名本身合法（含 schema_version 等 8 字段），再折算 diff。
    creative_contracts.validate_signature(fused_signature)

    # 折算 overrides：只取 7 个签名字段，剔除等于父原值的字段；schema_version
    # 不在 SIGNATURE_FIELDS 内，天然被排除。
    overrides: dict[str, list[str]] = {}
    for field in SIGNATURE_FIELDS:
        fused_value = fused_signature.get(field)
        if fused_value is None:
            continue
        if fused_value != base_signature.get(field):
            overrides[field] = fused_value
    return parent, overrides, "fused"
