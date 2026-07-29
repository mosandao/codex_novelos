from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class Chapter:
    number: int
    title: str
    content: str
    summary: str = ""


@dataclass(frozen=True, slots=True)
class Entity:
    kind: str
    name: str
    description: str
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryHit:
    kind: str
    label: str
    content: str
    chapter_number: int | None = None


@dataclass(frozen=True, slots=True)
class ContextPacket:
    recent_chapters: tuple[Chapter, ...]
    entities: tuple[Entity, ...]
    memories: tuple[MemoryHit, ...]
    continuity_risks: tuple[str, ...] = ()

    def to_prompt(self) -> str:
        sections: list[str] = []
        if self.recent_chapters:
            chapters = "\n".join(
                f"- Chapter {item.number}, {item.title}: {item.summary or item.content[:500]}"
                for item in self.recent_chapters
            )
            sections.append(f"RECENT CHAPTERS\n{chapters}")
        if self.entities:
            entities = "\n".join(
                f"- {item.kind} {item.name}: {item.description}; state={item.state}"
                for item in self.entities
            )
            sections.append(f"ENTITIES\n{entities}")
        if self.memories:
            memories = "\n".join(
                f"- [{item.kind}] {item.label}: {item.content}"
                for item in self.memories
            )
            sections.append(f"RELEVANT MEMORY\n{memories}")
        if self.continuity_risks:
            sections.append("CONTINUITY RISKS\n- " + "\n- ".join(self.continuity_risks))
        return "\n\n".join(sections) or "No canonical context is stored yet."


@dataclass(frozen=True, slots=True)
class ContinuationRequest:
    chapter_number: int
    goal: str
    title: str = ""
    point_of_view: str = ""
    tone: str = ""
    target_words: int = 2000
    deep_review: bool = True


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    severity: Literal["blocking", "warning", "note"]
    message: str
    excerpt: str = ""


@dataclass(frozen=True, slots=True)
class ReviewReport:
    approved: bool
    findings: tuple[ReviewFinding, ...] = ()


@dataclass(frozen=True, slots=True)
class ContinuationResult:
    chapter: Chapter
    review: ReviewReport
    saved: bool
    runtime_events: tuple[str, ...] = ()

