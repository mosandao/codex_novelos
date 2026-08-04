from __future__ import annotations

from typing import Any

PLANNING_UPSTREAM_TYPES: dict[str, frozenset[str]] = {
    "direction": frozenset(),
    "architecture": frozenset({"direction"}),
    "strategy": frozenset({"direction", "architecture"}),
    "character_contract": frozenset({"architecture", "strategy"}),
    "world_contract": frozenset({"architecture", "strategy"}),
    "story_arc": frozenset({"strategy", "character_contract", "world_contract"}),
    "volume_outline": frozenset({"story_arc"}),
    "chapter_plan": frozenset({"volume_outline"}),
}

PLANNING_PRODUCERS = {
    "direction": "方向智能体",
    "architecture": "架构智能体",
    "strategy": "策略智能体",
    "character_contract": "人物智能体",
    "world_contract": "世界观智能体",
    "story_arc": "故事弧智能体",
    "volume_outline": "卷规划智能体",
    "chapter_plan": "章节规划智能体",
}

CONTINUITY_OWNERS = {"canon", "expectation", "relationship", "arc"}

ENTITY_AUTHORITY_ASSETS = {
    "character": {"character_contract"},
    "world": {"world_contract"},
    "faction": {"world_contract"},
    "rule": {"world_contract"},
    "timeline": {"world_contract", "story_arc"},
}
