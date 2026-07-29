from __future__ import annotations

from typing import Protocol, Sequence

from novelos.domain import Chapter, Entity, MemoryHit


class MemoryGateway(Protocol):
    """MCP-facing contract consumed by Skills."""

    def initialize(self) -> None: ...

    def chapter_count(self) -> int: ...

    def latest_chapters(self, limit: int) -> Sequence[Chapter]: ...

    def search(self, query: str, limit: int = 12) -> Sequence[MemoryHit]: ...

    def list_entities(self, names: Sequence[str] = ()) -> Sequence[Entity]: ...

    def save_chapter(self, chapter: Chapter) -> None: ...

    def upsert_entity(self, entity: Entity) -> None: ...

    def add_memory(
        self,
        category: str,
        label: str,
        content: str,
        chapter_number: int | None = None,
    ) -> int: ...


class TextModel(Protocol):
    """Text generation port implemented by local fakes or an API adapter."""

    def complete(self, system: str, prompt: str) -> str: ...

