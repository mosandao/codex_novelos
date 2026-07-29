from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: str = "data/novelos.db"
    context_chapter_limit: int = 5
    spawn_context_builder_after: int = 20
    model_provider: str = "local"

    @classmethod
    def from_file(cls, path: str | Path | None) -> "Settings":
        if path is None:
            return cls()
        defaults = cls()
        with Path(path).open("rb") as handle:
            raw = tomllib.load(handle)
        app = raw.get("app", {})
        model = raw.get("model", {})
        return cls(
            database_path=app.get("database_path", defaults.database_path),
            context_chapter_limit=int(
                app.get("context_chapter_limit", defaults.context_chapter_limit)
            ),
            spawn_context_builder_after=int(
                app.get("spawn_context_builder_after", defaults.spawn_context_builder_after)
            ),
            model_provider=model.get("provider", defaults.model_provider),
        )
