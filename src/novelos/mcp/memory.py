from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from novelos.domain import Chapter, Entity, MemoryHit
from novelos.storage import SQLiteRepository


class MemoryMCPService:
    """Tool handlers shared by stdio MCP and the in-process development gateway."""

    def __init__(self, database_path: str | Path) -> None:
        self.repository = SQLiteRepository(database_path)

    def initialize(self) -> dict[str, bool]:
        self.repository.initialize()
        return {"initialized": True}

    def chapter_count(self) -> int:
        return self.repository.chapter_count()

    def latest_chapters(self, limit: int = 5) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.repository.latest_chapters(limit)]

    def search_memory(self, query: str, limit: int = 12) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.repository.search(query, limit)]

    def list_entities(self, names: Sequence[str] = ()) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.repository.list_entities(names)]

    def save_chapter(
        self,
        number: int,
        title: str,
        content: str,
        summary: str = "",
    ) -> dict[str, Any]:
        self.repository.save_chapter(Chapter(number, title, content, summary))
        return {"saved": True, "chapter_number": number}

    def upsert_entity(
        self,
        kind: str,
        name: str,
        description: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.repository.upsert_entity(Entity(kind, name, description, state or {}))
        return {"saved": True, "name": name}

    def add_memory(
        self,
        category: str,
        label: str,
        content: str,
        chapter_number: int | None = None,
    ) -> dict[str, Any]:
        memory_id = self.repository.add_memory(category, label, content, chapter_number)
        return {"saved": True, "memory_id": memory_id}


class InProcessMemoryGateway:
    """Typed adapter used by the local runtime without bypassing MCP handlers."""

    def __init__(self, service: MemoryMCPService) -> None:
        self.service = service

    def initialize(self) -> None:
        self.service.initialize()

    def chapter_count(self) -> int:
        return self.service.chapter_count()

    def latest_chapters(self, limit: int) -> list[Chapter]:
        return [Chapter(**item) for item in self.service.latest_chapters(limit)]

    def search(self, query: str, limit: int = 12) -> list[MemoryHit]:
        return [MemoryHit(**item) for item in self.service.search_memory(query, limit)]

    def list_entities(self, names: Sequence[str] = ()) -> list[Entity]:
        return [Entity(**item) for item in self.service.list_entities(names)]

    def save_chapter(self, chapter: Chapter) -> None:
        self.service.save_chapter(chapter.number, chapter.title, chapter.content, chapter.summary)

    def upsert_entity(self, entity: Entity) -> None:
        self.service.upsert_entity(entity.kind, entity.name, entity.description, entity.state)

    def add_memory(
        self,
        category: str,
        label: str,
        content: str,
        chapter_number: int | None = None,
    ) -> int:
        result = self.service.add_memory(category, label, content, chapter_number)
        return int(result["memory_id"])

