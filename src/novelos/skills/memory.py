from __future__ import annotations

from novelos.domain import ContextPacket
from novelos.ports import MemoryGateway


class MemorySkill:
    def __init__(self, gateway: MemoryGateway, chapter_limit: int = 5) -> None:
        self.gateway = gateway
        self.chapter_limit = chapter_limit

    def chapter_count(self) -> int:
        return self.gateway.chapter_count()

    def build_context(self, topic: str) -> ContextPacket:
        chapters = tuple(self.gateway.latest_chapters(self.chapter_limit))
        entities = tuple(self.gateway.list_entities())
        memories = tuple(self.gateway.search(topic, limit=12))
        risks: list[str] = []
        if not chapters:
            risks.append("No previous chapter is stored; continuity cannot be verified.")
        if not entities:
            risks.append("No canonical entity state is stored.")
        return ContextPacket(chapters, entities, memories, tuple(risks))

