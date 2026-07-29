from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, TypeVar

T = TypeVar("T")


class AgentRuntime:
    """Tracks temporary business Agent creation and deterministic cleanup."""

    def __init__(self) -> None:
        self.active: set[str] = set()
        self.events: list[str] = []

    @contextmanager
    def spawn(self, name: str, agent: T) -> Iterator[T]:
        if name in self.active:
            raise RuntimeError(f"Agent is already active: {name}")
        self.active.add(name)
        self.events.append(f"spawn:{name}")
        try:
            yield agent
        finally:
            self.active.remove(name)
            self.events.append(f"destroy:{name}")

