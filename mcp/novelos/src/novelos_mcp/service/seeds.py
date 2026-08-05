from __future__ import annotations

from typing import Any

from novelos_mcp.errors import NovelOSError
from novelos_mcp.storage import Database

from ._helpers import _id, _json, _require_text


class SeedsMixin:
    """创作种子非权威入口层。

    种子层不进 planning_assets（权威资产容器），不进依赖图，不触发 stale 传播。
    但有版本与变更留痕（is_active 机制：同一 project 同时只有一个 active 种子）。
    """

    database: Database

    def _seed_row(self, row) -> dict[str, Any]:
        result = dict(row)
        return result

    def get_creation_seed(self, project_id: str) -> dict[str, Any] | None:
        """取当前 active 种子；无种子返回 None。"""
        _require_text(project_id, "project_id")
        with self.database.read() as connection:
            self._get(connection, "projects", project_id)
            row = connection.execute(
                "SELECT * FROM creation_seeds WHERE project_id=? AND is_active=1 ORDER BY version DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return self._seed_row(row) if row is not None else None

    def update_creation_seed(
        self,
        project_id: str,
        protagonist_seed: str = "",
        world_seed: str = "",
        hook_seed: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        """迭代种子：新增 version，旧 active 置 inactive。

        不触发任何 stale 传播，不写 authority_commits。
        """
        _require_text(project_id, "project_id")
        with self.database.transaction() as connection:
            self._get(connection, "projects", project_id)
            current = connection.execute(
                "SELECT MAX(version) AS max_version FROM creation_seeds WHERE project_id=?",
                (project_id,),
            ).fetchone()
            next_version = (current["max_version"] or 0) + 1
            seed_id = _id("creation-seed")
            connection.execute(
                "UPDATE creation_seeds SET is_active=0, updated_at=CURRENT_TIMESTAMP WHERE project_id=? AND is_active=1",
                (project_id,),
            )
            connection.execute(
                """INSERT INTO creation_seeds
                   (id, project_id, version, protagonist_seed, world_seed, hook_seed, notes, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    seed_id,
                    project_id,
                    next_version,
                    protagonist_seed,
                    world_seed,
                    hook_seed,
                    notes,
                ),
            )
            row = connection.execute(
                "SELECT * FROM creation_seeds WHERE id=?",
                (seed_id,),
            ).fetchone()
            return self._seed_row(row)

    def list_creation_seeds(self, project_id: str) -> list[dict[str, Any]]:
        """列全部历史版本（留痕查阅），按版本倒序。"""
        _require_text(project_id, "project_id")
        with self.database.read() as connection:
            self._get(connection, "projects", project_id)
            rows = connection.execute(
                "SELECT * FROM creation_seeds WHERE project_id=? ORDER BY version DESC",
                (project_id,),
            ).fetchall()
        return [self._seed_row(row) for row in rows]
