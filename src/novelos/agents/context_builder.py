from __future__ import annotations

from novelos.domain import ContextPacket
from novelos.skills import MemorySkill


class ContextBuilderAgent:
    """Temporary reasoning role for context-heavy requests."""

    def __init__(self, memory_skill: MemorySkill) -> None:
        self.memory_skill = memory_skill

    def build(self, topic: str) -> ContextPacket:
        return self.memory_skill.build_context(topic)

